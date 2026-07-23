# Fase 3: Conversatiemodus — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een live gesprek in het Spaans per hoofdstuk — spreken én typen — waarbij Claude als gesprekspartner stuurt richting de lesstof en per beurt een korte Nederlandse correctie geeft op wat de leerling zei.

**Architecture:** Eén stateless endpoint (`POST /api/chapters/{id}/conversation`): de frontend stuurt per beurt de hele geschiedenis mee, de backend bouwt een systeemprompt uit de lesstof (gedeelde helper, verplaatst uit de exercises-router) en vraagt Claude om gestructureerd `{correction, reply}`. De systeemprompt wordt gecachet (prompt-caching) om kosten per beurt te drukken. Het chatscherm hergebruikt de bestaande spraaklaag (`speech.js`): microfoon vult het invoerveld, antwoorden worden voorgelezen. Er wordt niets opgeslagen.

**Tech Stack:** FastAPI, bestaande `app/llm.py` (uitgebreid met `cache_system`), vanilla-JS + Web Speech API, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-llm-oefeningen-scans-conversatie-design.md` (sectie "Fase 3 — Conversatie")

## Global Constraints

- Nederlands in alle UI-teksten, commit-messages, docstrings en foutmeldingen (bestaande stijl); het gesprek zelf is in het Spaans, correcties in het Nederlands.
- Commit-messages in de stijl `Onderwerp: beschrijving`, afgesloten met:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` en de Claude-Session-regel van de sessie.
- Niets buiten `app/llm.py` importeert `anthropic`.
- Tests draaien nooit tegen de echte API: mock `llm.complete_json` met `monkeypatch`.
- Server blijft stateless: gesprekken worden niet opgeslagen (spec).
- Volledige testsuite groen na elke taak: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'` (mét glob-quotes; kale map faalt).

## Ontwerpkeuzes bovenop de spec (klein, hier vastgelegd)

1. **Claude opent het gesprek**: een lege geschiedenis is toegestaan; de backend stuurt dan intern één instructie-bericht zodat de gesprekspartner begint met een begroeting en openingsvraag. De `correction` is dan altijd leeg.
2. **Microfoon vult het invoerveld** in plaats van direct verzenden: spraakherkenning verstaat weleens iets verkeerd, zo kan de leerling corrigeren vóór verzenden.
3. **Lesstof-helper gedeeld**: `_lesson_context` verhuist van `app/routers/exercises.py` naar `app/lesstof.py` (tweede consument; secties alleen als ze gevuld zijn, lege string als er niets is).

---

### Taak 1: Fundament — gedeelde lesstof-helper en prompt-caching in de LLM-laag

**Files:**
- Create: `app/lesstof.py`
- Modify: `app/routers/exercises.py` (verwijder `_lesson_context`, importeer de helper)
- Modify: `app/llm.py` (nieuwe parameter `cache_system`)
- Test: `tests/test_lesstof.py` (nieuw), `tests/test_llm.py` (uitbreiden)

**Interfaces:**
- Consumes: `list_rules(chapter_id, conn)` uit `app/routers/grammar.py`, `list_words`/`list_verbs` uit de words/verbs-routers.
- Produces:
  - `lesstof.lesson_context(conn, chapter_id) -> str` — grammatica, woorden en werkwoorden als platte tekst; secties alleen als ze gevuld zijn; `""` als het hoofdstuk leeg is.
  - `llm.complete_json(system, messages, schema, max_tokens=16000, cache_system=False)` — bij `cache_system=True` gaat `system` als tekstblok met `cache_control: {"type": "ephemeral"}` mee.

- [ ] **Stap 1: Schrijf de falende tests**

Maak `tests/test_lesstof.py`:

```python
import pytest

from app import db
from app.lesstof import lesson_context


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def _context(app_instance, chapter_id):
    conn = db.connect(app_instance.state.db_path)
    try:
        return lesson_context(conn, chapter_id)
    finally:
        conn.close()


class TestLessonContext:
    def test_leeg_hoofdstuk_geeft_lege_string(self, client, app_instance, chapter_id):
        assert _context(app_instance, chapter_id) == ""

    def test_alle_secties_gevuld(self, client, app_instance, chapter_id):
        client.post("/api/grammar", json={
            "chapter_id": chapter_id, "title": "Ser en estar",
            "explanation": "Ser voor blijvend.",
            "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
        })
        client.post("/api/words", json={
            "chapter_id": chapter_id, "spanish": "cansado", "dutch": "moe",
        })
        client.post("/api/verbs", json={
            "chapter_id": chapter_id, "infinitive_es": "estar",
            "translation_nl": "zijn",
            "forms": {"yo": "estoy", "tu": "estás", "el": "está",
                      "nosotros": "estamos", "vosotros": "estáis",
                      "ellos": "están"},
        })
        context = _context(app_instance, chapter_id)
        assert "Grammaticaregels:" in context
        assert "## Ser en estar" in context
        assert "- Estoy cansado — Ik ben moe" in context
        assert "Woordenschat:" in context
        assert "- cansado — moe" in context
        assert "Werkwoorden:" in context
        assert "- estar — zijn" in context

    def test_alleen_woorden_geen_grammatica_kop(self, client, app_instance, chapter_id):
        client.post("/api/words", json={
            "chapter_id": chapter_id, "spanish": "sol", "dutch": "zon",
        })
        context = _context(app_instance, chapter_id)
        assert "Grammaticaregels:" not in context
        assert "Woordenschat:" in context
```

Voeg toe aan `tests/test_llm.py` (de helper `_fake_client` en `SCHEMA` bestaan daar al):

```python
def test_cache_system_stuurt_cache_control_mee(monkeypatch):
    calls = _fake_client(monkeypatch)
    llm.complete_json(
        "systeem", [{"role": "user", "content": "hoi"}], SCHEMA, cache_system=True
    )
    assert calls[0]["system"] == [{
        "type": "text",
        "text": "systeem",
        "cache_control": {"type": "ephemeral"},
    }]


def test_zonder_cache_system_blijft_system_een_string(monkeypatch):
    calls = _fake_client(monkeypatch)
    llm.complete_json("systeem", [{"role": "user", "content": "hoi"}], SCHEMA)
    assert calls[0]["system"] == "systeem"
```

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_lesstof.py tests/test_llm.py -q`
Verwacht: ImportError voor `app.lesstof`; de cache-test faalt op TypeError (onbekende parameter).

- [ ] **Stap 3: Implementeer**

Maak `app/lesstof.py`:

```python
"""Lesstof van een hoofdstuk als platte tekst, voor LLM-prompts."""

from app.routers.grammar import list_rules
from app.routers.verbs import list_verbs
from app.routers.words import list_words


def lesson_context(conn, chapter_id):
    """Grammatica, woorden en werkwoorden; secties alleen als ze gevuld zijn."""
    parts = []
    rules = list_rules(chapter_id, conn)
    if rules:
        parts.append("Grammaticaregels:")
        for rule in rules:
            parts.append(f"## {rule['title']}\n{rule['explanation']}")
            parts.extend(
                f"- {ex['spanish']} — {ex['dutch']}" for ex in rule["examples"]
            )
    words = list_words(chapter_id, conn)
    if words:
        parts.append("\nWoordenschat:")
        parts.extend(f"- {w['spanish']} — {w['dutch']}" for w in words)
    verbs = list_verbs(chapter_id, conn)
    if verbs:
        parts.append("\nWerkwoorden:")
        parts.extend(
            f"- {v['infinitive_es']} — {v['translation_nl']}" for v in verbs
        )
    return "\n".join(parts)
```

In `app/routers/exercises.py`: verwijder de functie `_lesson_context` en de imports `list_rules`/`list_words`/`list_verbs` **als die nergens anders in het bestand gebruikt worden** (let op: `list_rules` wordt óók gebruikt in `generate_exercises` voor de grammatica-guard — die import blijft dus staan). Voeg toe: `from app.lesstof import lesson_context` en vervang de aanroep `_lesson_context(conn, body.chapter_id)` door `lesson_context(conn, body.chapter_id)`.

In `app/llm.py`, wijzig de signatuur en het system-argument:

```python
def complete_json(system, messages, schema, max_tokens=16000, cache_system=False):
    """Vraag Claude om JSON volgens `schema` en geef die geparst terug.

    Met cache_system=True wordt de systeemprompt gecachet (prompt-caching):
    goedkoper wanneer dezelfde prompt per beurt opnieuw meegaat (conversatie).
    """
    if cache_system:
        system = [{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }]
```

(de rest van de functie blijft ongewijzigd; `system=system` gaat al mee in de aanroep).

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_lesstof.py tests/test_llm.py tests/test_api_exercises.py -q`
Verwacht: alles passed (de bestaande generate-tests bewijzen dat de verhuizing niets brak).

- [ ] **Stap 5: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` → alles groen.

```bash
git add app/lesstof.py app/routers/exercises.py app/llm.py tests/test_lesstof.py tests/test_llm.py
git commit -m "Lesstof-helper gedeeld en prompt-caching optie in de LLM-laag"
```

---

### Taak 2: Conversation-endpoint

**Files:**
- Create: `app/routers/conversation.py`
- Modify: `app/main.py` (import + include_router)
- Test: `tests/test_api_conversation.py` (nieuw)

**Interfaces:**
- Consumes: `llm.complete_json(..., cache_system=True)` en `llm.LLMError`; `lesstof.lesson_context(conn, chapter_id)`; `chapter_or_404`/`get_conn` uit `app/deps.py`.
- Produces: `POST /api/chapters/{chapter_id}/conversation` met body
  `{"messages": [{"role": "user"|"assistant", "text": str}, ...]}` (mag leeg zijn; max 100; tekst 1–4000 tekens) →
  `{"correction": str, "reply": str}` (`correction` leeg als er niets te verbeteren valt of bij een gespreksopening).
  Fouten: 404 onbekend hoofdstuk, 400 laatste bericht niet van de leerling of hoofdstuk zonder lesstof, 422 ongeldige body, 503 LLM-storing, 502 leeg antwoord.

- [ ] **Stap 1: Schrijf de falende tests**

Maak `tests/test_api_conversation.py`:

```python
import pytest

from app import llm


@pytest.fixture
def chapter_id(client):
    chapter_id = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
    client.post("/api/grammar", json={
        "chapter_id": chapter_id, "title": "Ser en estar",
        "explanation": "Ser voor blijvend, estar voor tijdelijk.",
        "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
    })
    return chapter_id


def _fake(antwoord=None, aanroepen=None):
    antwoord = antwoord or {"correction": "", "reply": "¡Hola! ¿Cómo estás?"}

    def fake(**kwargs):
        if aanroepen is not None:
            aanroepen.append(kwargs)
        return antwoord

    return fake


class TestConversatie:
    def test_beurt_geeft_correctie_en_antwoord(self, client, chapter_id, monkeypatch):
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(
            {"correction": "Kleine fout: 'estoy', niet 'esta'.", "reply": "¿Y ahora?"},
            aanroepen,
        ))
        response = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [
                {"role": "assistant", "text": "¿Cómo estás?"},
                {"role": "user", "text": "Esta bien."},
            ],
        })
        assert response.status_code == 200
        assert response.json() == {
            "correction": "Kleine fout: 'estoy', niet 'esta'.",
            "reply": "¿Y ahora?",
        }
        # Geschiedenis is één-op-één doorgegeven
        assert aanroepen[0]["messages"] == [
            {"role": "assistant", "content": "¿Cómo estás?"},
            {"role": "user", "content": "Esta bien."},
        ]
        # De lesstof zit in de systeemprompt en die wordt gecachet
        assert "Ser en estar" in str(aanroepen[0]["system"])
        assert aanroepen[0]["cache_system"] is True

    def test_lege_geschiedenis_opent_het_gesprek(self, client, chapter_id, monkeypatch):
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(
            {"correction": "dit hoort leeg te zijn", "reply": "¡Hola!"}, aanroepen,
        ))
        response = client.post(
            f"/api/chapters/{chapter_id}/conversation", json={"messages": []}
        )
        assert response.status_code == 200
        # Bij een opening is er niets te corrigeren, wat de LLM ook zegt
        assert response.json() == {"correction": "", "reply": "¡Hola!"}
        assert aanroepen[0]["messages"][0]["role"] == "user"
        assert "Begin het gesprek" in aanroepen[0]["messages"][0]["content"]

    def test_laatste_bericht_moet_van_leerling_zijn(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        response = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [{"role": "assistant", "text": "¿Cómo estás?"}],
        })
        assert response.status_code == 400

    def test_hoofdstuk_zonder_lesstof_is_400(self, client, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        leeg = client.post("/api/chapters", json={"name": "Leeg"}).json()["id"]
        response = client.post(
            f"/api/chapters/{leeg}/conversation", json={"messages": []}
        )
        assert response.status_code == 400

    def test_onbekend_hoofdstuk_is_404(self, client, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        assert (
            client.post(
                "/api/chapters/999/conversation", json={"messages": []}
            ).status_code
            == 404
        )

    def test_llm_storing_is_503(self, client, chapter_id, monkeypatch):
        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        response = client.post(
            f"/api/chapters/{chapter_id}/conversation", json={"messages": []}
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Geen verbinding met de taaldienst"

    def test_leeg_antwoord_is_502(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(
            llm, "complete_json", _fake({"correction": "", "reply": "   "})
        )
        response = client.post(
            f"/api/chapters/{chapter_id}/conversation", json={"messages": []}
        )
        assert response.status_code == 502

    def test_ongeldige_rol_is_422(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        response = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [{"role": "system", "text": "hack"}],
        })
        assert response.status_code == 422
```

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_conversation.py -q`
Verwacht: alle tests falen met 404 (route bestaat niet).

- [ ] **Stap 3: Implementeer de router en registreer hem**

Maak `app/routers/conversation.py`:

```python
"""Conversatie: gesprek in het Spaans over de lesstof van een hoofdstuk.

Stateless: de frontend stuurt per beurt de hele geschiedenis mee en er
wordt niets opgeslagen (spec). De systeemprompt met lesstof wordt gecachet.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import llm
from app.deps import chapter_or_404, get_conn
from app.lesstof import lesson_context

router = APIRouter(prefix="/api/chapters")

_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "correction": {"type": "string"},
        "reply": {"type": "string"},
    },
    "required": ["correction", "reply"],
    "additionalProperties": False,
}

_SYSTEM_TEMPLATE = (
    "Je bent een geduldige Spaanse gesprekspartner voor een Nederlandstalige "
    "beginner. Voer een natuurlijk gesprek in eenvoudig Spaans met korte "
    "zinnen en stuur het gesprek richting de lesstof hieronder: gebruik de "
    "grammatica en woordenschat van dit hoofdstuk en stel vragen die de "
    "leerling uitnodigen die ook te gebruiken.\n\n"
    "Geef per beurt twee velden terug:\n"
    "- correction: alleen als het laatste bericht van de leerling een echte "
    "fout bevat één korte Nederlandse verbetering; anders een lege string. "
    "Accent- en interpunctiefouten verbeter je niet.\n"
    "- reply: jouw Spaanse antwoord dat het gesprek voortzet, afgesloten met "
    "een vraag terug. Maximaal twee korte zinnen.\n\n"
    "Lesstof van dit hoofdstuk:\n{lesstof}"
)

_OPENING = (
    "Begin het gesprek met een korte Spaanse begroeting en één eenvoudige "
    "openingsvraag over de lesstof."
)


class TurnIn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class ConversationRequest(BaseModel):
    messages: list[TurnIn] = Field(default=[], max_length=100)


@router.post("/{chapter_id}/conversation")
def conversation_turn(
    chapter_id: int, body: ConversationRequest, conn=Depends(get_conn)
):
    chapter_or_404(conn, chapter_id)
    lesstof = lesson_context(conn, chapter_id)
    if not lesstof:
        raise HTTPException(
            status_code=400,
            detail="Dit hoofdstuk heeft nog geen lesstof om over te praten",
        )
    if body.messages:
        if body.messages[-1].role != "user":
            raise HTTPException(
                status_code=400,
                detail="Het laatste bericht moet van de leerling zijn",
            )
        messages = [
            {"role": turn.role, "content": turn.text} for turn in body.messages
        ]
    else:
        messages = [{"role": "user", "content": _OPENING}]
    try:
        data = llm.complete_json(
            system=_SYSTEM_TEMPLATE.format(lesstof=lesstof),
            messages=messages,
            schema=_TURN_SCHEMA,
            cache_system=True,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    reply = data["reply"].strip()
    if not reply:
        raise HTTPException(
            status_code=502, detail="Geen antwoord van de gesprekspartner"
        )
    # Bij een gespreksopening valt er niets te corrigeren
    correction = data["correction"].strip() if body.messages else ""
    return {"correction": correction, "reply": reply}
```

In `app/main.py` de import uitbreiden (alfabetisch):

```python
from app.routers import (
    chapters, conversation, exercises, grammar, lessons, practice, verbs, words,
)
```

en na `app.include_router(lessons.router)`:

```python
app.include_router(conversation.router)
```

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_conversation.py -q`
Verwacht: 8 passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` → alles groen.

```bash
git add app/routers/conversation.py app/main.py tests/test_api_conversation.py
git commit -m "Conversatie: endpoint voor gespreksbeurten op basis van de lesstof"
```

---

### Taak 3: Chatscherm

**Files:**
- Create: `app/static/js/views/conversation.js`
- Modify: `app/static/js/app.js` (import + route)
- Modify: `app/static/js/views/chapter.js` (kaart "Gesprek")
- Modify: `app/static/style.css` (chat-stijlen, onderaan toevoegen)

**Interfaces:**
- Consumes: `POST /api/chapters/{id}/conversation` (Taak 2); `api`, `el`, `setChildren` uit `api.js`; `LANG`, `canListen`, `listen`, `speak`, `stopListening` uit `speech.js` (bestaand: `listen(lang)` geeft een lijst alternatieven of `null`; `speak(text, lang)` wacht tot het voorlezen klaar is).
- Produces: route `#/h/{id}/gesprek` → `renderConversation(view, chapterId)`.

- [ ] **Stap 1: Voeg de chat-stijlen toe**

Onderaan `app/static/style.css`:

```css
/* Gesprek */
.chat { display: flex; flex-direction: column; gap: 0.6rem; margin: 1rem 0; }
.bubble { max-width: 85%; padding: 0.6rem 0.9rem; border-radius: var(--radius); white-space: pre-wrap; }
.bubble.leerling { align-self: flex-end; background: var(--sol-zacht); }
.bubble.partner { align-self: flex-start; background: var(--card); border: 1px solid var(--line); font-family: var(--serif); font-size: 1.1rem; }
.bubble .correctie { display: block; margin-top: 0.4rem; font-family: var(--sans); font-size: 0.85rem; color: var(--rojo); }
.bubble.wachten { color: var(--muted); font-style: italic; }
.chat-invoer { display: flex; gap: 0.5rem; }
.chat-invoer input { flex: 1; }
```

- [ ] **Stap 2: Schrijf de view**

Maak `app/static/js/views/conversation.js`:

```js
import {api, el, setChildren} from '../api.js';
import {LANG, canListen, listen, speak, stopListening} from '../speech.js';

export async function renderConversation(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  // Geschiedenis leeft alleen in dit scherm; de server slaat niets op
  const history = [];
  const chat = el('div', {class: 'chat'});
  const status = el('p', {class: 'muted'});

  const input = el('input', {
    type: 'text', autocapitalize: 'off', autocomplete: 'off',
    placeholder: 'Antwoord in het Spaans…', 'aria-label': 'Jouw bericht',
  });
  const sendButton = el('button', {class: 'btn-primary', type: 'submit'}, 'Stuur');
  const micButton = canListen()
    ? el('button', {type: 'button', title: 'Spreek je antwoord in'}, '🎙️')
    : null;

  const inputRow = el('form', {
    class: 'chat-invoer',
    onsubmit: (e) => { e.preventDefault(); sendTurn(); },
  }, input, micButton, sendButton);

  setChildren(view, 
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Gesprek'),
    el('p', {class: 'muted'}, 'Praat in het Spaans over de lesstof van dit hoofdstuk. Correcties verschijnen onder je bericht.'),
    chat, inputRow, status,
  );

  function bubble(role, text) {
    const node = el('div', {class: `bubble ${role}`}, text);
    chat.append(node);
    node.scrollIntoView({block: 'end', behavior: 'smooth'});
    return node;
  }

  function setBusy(busy) {
    input.disabled = busy;
    sendButton.disabled = busy;
    if (micButton) micButton.disabled = busy;
  }

  async function requestTurn() {
    setBusy(true);
    const waiting = bubble('partner wachten', '…');
    try {
      const {correction, reply} = await api(
        `/api/chapters/${chapterId}/conversation`,
        {method: 'POST', body: {messages: history}},
      );
      waiting.remove();
      if (correction) {
        const lastUser = [...chat.querySelectorAll('.bubble.leerling')].at(-1);
        lastUser?.append(el('span', {class: 'correctie'}, `✏️ ${correction}`));
      }
      history.push({role: 'assistant', text: reply});
      bubble('partner', reply);
      status.textContent = '';
      setBusy(false);
      input.focus();
      await speak(reply, LANG.es);
    } catch (err) {
      waiting.remove();
      status.textContent = `Er ging iets mis: ${err.message}`;
      // Mislukte beurt: laatste leerling-bericht terug het invoerveld in
      const last = history.at(-1);
      if (last?.role === 'user') {
        history.pop();
        [...chat.querySelectorAll('.bubble.leerling')].at(-1)?.remove();
        input.value = last.text;
      }
      setBusy(false);
      input.focus();
    }
  }

  function sendTurn() {
    const text = input.value.trim();
    if (!text || input.disabled) return;
    stopListening();
    history.push({role: 'user', text});
    bubble('leerling', text);
    input.value = '';
    requestTurn();
  }

  micButton?.addEventListener('click', async () => {
    micButton.disabled = true;
    micButton.textContent = '👂';
    const heard = await listen(LANG.es);
    micButton.textContent = '🎙️';
    micButton.disabled = input.disabled;
    if (heard?.[0]) {
      input.value = heard[0];
      input.focus();
    } else {
      status.textContent = 'Ik heb niets gehoord — probeer opnieuw of typ je antwoord.';
    }
  });

  // Claude opent het gesprek
  requestTurn();
}
```

- [ ] **Stap 3: Sluit de route en de kaart aan**

In `app/static/js/app.js` de import toevoegen:

```js
import {renderConversation} from './views/conversation.js';
```

en in de `routes`-lijst, na de `les-uploaden`-route:

```js
[/^h\/(\d+)\/gesprek$/, (id) => renderConversation(view, +id)],
```

In `app/static/js/views/chapter.js`, ná de kaart "Oefeningen", deze kaart toevoegen:

```js
el(
  'div',
  {class: 'card'},
  el('h2', {}, 'Gesprek'),
  el('p', {class: 'muted'},
    'Oefen conversatie in het Spaans over de lesstof, met directe correcties.'),
  el('div', {class: 'row'},
    el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/gesprek`}, '💬 Gesprek starten')),
),
```

- [ ] **Stap 4: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'` → alles groen.

```bash
git add app/static/js/views/conversation.js app/static/js/app.js app/static/js/views/chapter.js app/static/style.css
git commit -m "Gesprek: chatscherm met spraak, voorlezen en directe correcties"
```

---

### Taak 4: Afronding — README en verificatie in de echte UI

**Files:**
- Modify: `README.md` (LLM-functies-zin uitbreiden)

**Interfaces:** geen — documentatie en verificatie.

- [ ] **Stap 1: README bijwerken**

In `README.md`: "Voor de LLM-functies (oefeningen genereren, vertaalbeoordeling, scans uitlezen):" → "... (oefeningen genereren, vertaalbeoordeling, scans uitlezen, conversatie):".

- [ ] **Stap 2: Draai alles**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'`
Verwacht: alles groen.

- [ ] **Stap 3: Verifieer in de echte UI**

Gebruik de project-skill `verify` (testinstantie op poort 8765):
- Maak een hoofdstuk met een grammaticaregel en enkele woorden (via de API).
- Hoofdstukscherm → kaart "Gesprek" → "💬 Gesprek starten".
- Verwacht: Claude opent het gesprek in het Spaans (echte API-aanroep, centen).
- Typ een Spaans antwoord mét een bewuste fout (bijv. "Yo es Wouter") → verstuur.
- Verwacht: een Nederlandse correctie (✏️) onder je bericht, en een Spaans vervolg dat het gesprek voortzet.
- Typ nog een correcte beurt → verwacht: géén correctie.
- Foutpad: controleer dat na een mislukte beurt (bijv. testinstantie zonder key, of simpelweg door de foutafhandeling te vertrouwen op de pytest-dekking) het bericht terug in het invoerveld komt — als dit lastig te ensceneren is, volstaat de pytest-dekking van het 503-pad plus een codeleescontrole.
- Spraak (TTS/microfoon) is in een headless browser niet te testen; controleer alleen dat het scherm zonder JS-fouten laadt met en zonder `SpeechRecognition` (headless Chrome heeft die meestal niet — de micknop hoort dan te ontbreken).

- [ ] **Stap 4: Commit**

```bash
git add README.md
git commit -m "Gesprek: README bijgewerkt"
```
