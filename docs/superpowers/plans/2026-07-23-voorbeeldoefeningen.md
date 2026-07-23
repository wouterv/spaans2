# Voorbeeldoefeningen uit het boek — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gescande oefenpagina's uit het boek verwerken tot bewaarde "voorbeeldoefeningen" per hoofdstuk, die de oefeninggenerator sturen ("maak oefeningen zoals deze") en meegaan in het gesprek.

**Architecture:** Nieuwe tabel + CRUD-router (`example_exercises` / `app/routers/examples.py`). Het bestaande extract-endpoint herkent voortaan uitleg én opgaven (schema met `rules` + `examples`). `lesson_context` krijgt een vierde sectie, waardoor generator en gesprek de voorbeelden automatisch zien; de generator-guard versoepelt naar "grammatica óf voorbeeldoefeningen". Het nakijkscherm krijgt een tweede sectie; een klein beheerscherm met teller-rij maakt terugkijken/verwijderen/handmatig toevoegen mogelijk.

**Tech Stack:** FastAPI, SQLite (migratie 003), bestaande `app/llm.py`, vanilla-JS, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-voorbeeldoefeningen-design.md`

## Global Constraints

- Nederlands in alle UI-teksten, commit-messages, docstrings en foutmeldingen.
- Commit-messages in de stijl `Onderwerp: beschrijving`, afgesloten met:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` en de Claude-Session-regel van de sessie.
- Niets buiten `app/llm.py` importeert `anthropic`; tests mocken `llm.complete_json` met `monkeypatch`.
- Het extract-endpoint slaat níéts op; scans worden niet bewaard.
- Volledige testsuite groen na elke taak: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'` (mét glob-quotes).

---

### Taak 1: Migratie en examples-router

**Files:**
- Create: `app/migrations/003_example_exercises.sql`
- Create: `app/routers/examples.py`
- Modify: `app/main.py` (import + include_router)
- Test: `tests/test_api_examples.py` (nieuw)

**Interfaces:**
- Produces:
  - Tabel `example_exercises (id, chapter_id, text, created_at)` met cascade-delete.
  - `GET /api/examples?chapter_id=N` → `[{id, chapter_id, text}]` (functienaam `list_examples(chapter_id, conn)` — Taak 3 importeert die).
  - `POST /api/examples` body `{chapter_id, text}` → 201 `{id}`; 404 onbekend hoofdstuk; 422 lege tekst.
  - `DELETE /api/examples/{id}` → 204; 404 onbekend.

- [ ] **Stap 1: Schrijf de falende tests**

Maak `tests/test_api_examples.py`:

```python
import pytest


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


class TestExamples:
    def test_aanmaken_en_lijst(self, client, chapter_id):
        response = client.post("/api/examples", json={
            "chapter_id": chapter_id,
            "text": "Completa: Yo ___ (ser) de Holanda.",
        })
        assert response.status_code == 201
        example_id = response.json()["id"]
        examples = client.get(f"/api/examples?chapter_id={chapter_id}").json()
        assert examples == [{
            "id": example_id,
            "chapter_id": chapter_id,
            "text": "Completa: Yo ___ (ser) de Holanda.",
        }]

    def test_tekst_wordt_gestript(self, client, chapter_id):
        client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "  Traduce: ik ben moe.  ",
        })
        examples = client.get(f"/api/examples?chapter_id={chapter_id}").json()
        assert examples[0]["text"] == "Traduce: ik ben moe."

    def test_lege_tekst_is_422(self, client, chapter_id):
        response = client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "",
        })
        assert response.status_code == 422

    def test_onbekend_hoofdstuk_is_404(self, client):
        response = client.post("/api/examples", json={
            "chapter_id": 999, "text": "Completa: ___",
        })
        assert response.status_code == 404

    def test_verwijderen(self, client, chapter_id):
        example_id = client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "Completa: ___",
        }).json()["id"]
        assert client.delete(f"/api/examples/{example_id}").status_code == 204
        assert client.get(f"/api/examples?chapter_id={chapter_id}").json() == []

    def test_verwijderen_onbekend_is_404(self, client):
        assert client.delete("/api/examples/999").status_code == 404

    def test_hoofdstuk_verwijderen_verwijdert_voorbeelden(self, client, app_instance, chapter_id):
        from app import db

        client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "Completa: ___",
        })
        client.delete(f"/api/chapters/{chapter_id}")
        conn = db.connect(app_instance.state.db_path)
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM example_exercises"
            ).fetchone()["n"]
        finally:
            conn.close()
        assert count == 0
```

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_examples.py -q`
Verwacht: FAIL/ERROR (`no such table: example_exercises`, daarna 404-routes).

- [ ] **Stap 3: Implementeer migratie en router**

Maak `app/migrations/003_example_exercises.sql`:

```sql
CREATE TABLE example_exercises (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Maak `app/routers/examples.py`:

```python
"""Voorbeeldoefeningen: opgaven uit het boek als input voor generatie en gesprek."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import chapter_or_404, get_conn

router = APIRouter(prefix="/api/examples")


class ExampleIn(BaseModel):
    chapter_id: int
    text: str = Field(min_length=1)


@router.get("")
def list_examples(chapter_id: int, conn=Depends(get_conn)):
    rows = conn.execute(
        "SELECT id, chapter_id, text FROM example_exercises "
        "WHERE chapter_id = ? ORDER BY id",
        (chapter_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("", status_code=201)
def create_example(body: ExampleIn, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    cursor = conn.execute(
        "INSERT INTO example_exercises (chapter_id, text) VALUES (?, ?)",
        (body.chapter_id, body.text.strip()),
    )
    conn.commit()
    return {"id": cursor.lastrowid}


@router.delete("/{example_id}", status_code=204)
def delete_example(example_id: int, conn=Depends(get_conn)):
    cursor = conn.execute(
        "DELETE FROM example_exercises WHERE id = ?", (example_id,)
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Voorbeeld niet gevonden")
```

In `app/main.py`: `examples` toevoegen aan de bestaande import
(`from app.routers import (chapters, conversation, examples, exercises, ...)`)
en na `app.include_router(conversation.router)`:

```python
app.include_router(examples.router)
```

Let op: `text` met alleen spaties (bijv. `"   "`) passeert `min_length=1` maar zou leeg opgeslagen worden. Schrijf `create_example` daarom exact zo:

```python
@router.post("", status_code=201)
def create_example(body: ExampleIn, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Tekst is verplicht")
    cursor = conn.execute(
        "INSERT INTO example_exercises (chapter_id, text) VALUES (?, ?)",
        (body.chapter_id, text),
    )
    conn.commit()
    return {"id": cursor.lastrowid}
```

(vervangt de eerdere `create_example` uit het codeblok hierboven).

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_examples.py -q`
Verwacht: 7 passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` → alles groen.

```bash
git add app/migrations/003_example_exercises.sql app/routers/examples.py app/main.py tests/test_api_examples.py
git commit -m "Voorbeeldoefeningen: tabel en CRUD-endpoints"
```

---

### Taak 2: Extractie herkent ook opgaven

**Files:**
- Modify: `app/routers/lessons.py`
- Test: `tests/test_api_lessons.py` (bestaande tests aanpassen + nieuwe)

**Interfaces:**
- Consumes: bestaand extract-endpoint (zie `app/routers/lessons.py`).
- Produces: respons wordt `{"rules": [...], "examples": [str, ...]}`; 502 alleen als beide leeg.

- [ ] **Stap 1: Pas de tests aan en voeg nieuwe toe**

In `tests/test_api_lessons.py`:

1. In `test_geeft_regels_terug_en_slaat_niets_op`: de assert
   `assert response.json() == {"rules": [_regel()]}` wordt
   `assert response.json() == {"rules": [_regel()], "examples": []}`.
2. In `test_geen_regels_herkend_is_502`: de mock geeft nu
   `{"rules": [], "examples": []}` terug (naam van de test mag blijven).
3. Nieuwe tests, toevoegen aan de klasse `TestExtract`:

```python
    def test_gemengde_pagina_geeft_regels_en_voorbeelden(
        self, client, chapter_id, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {
            "rules": [_regel()],
            "examples": ["Completa: Yo ___ (ser) de Holanda.", "  ", "Traduce: ik ben moe."],
        })
        body = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        ).json()
        assert body["rules"] == [_regel()]
        # Lege items eruit, rest gestript
        assert body["examples"] == [
            "Completa: Yo ___ (ser) de Holanda.", "Traduce: ik ben moe.",
        ]

    def test_alleen_opgaven_is_geen_502(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {
            "rules": [], "examples": ["Completa: Tú ___ (estar) cansado."],
        })
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 200
        assert response.json()["rules"] == []

    def test_extractieprompt_vraagt_ook_om_opgaven(
        self, client, chapter_id, monkeypatch
    ):
        aanroepen = []

        def fake(**kwargs):
            aanroepen.append(kwargs)
            return {"rules": [_regel()], "examples": []}

        monkeypatch.setattr(llm, "complete_json", fake)
        client.post(f"/api/chapters/{chapter_id}/lessons/extract", json=_body())
        assert "voorbeeldoefening" in aanroepen[0]["system"].lower()
```

Let op: andere bestaande mocks in dit bestand geven `{"rules": [...]}` zonder
`examples`-sleutel terug; de implementatie moet daarom `data.get("examples", [])`
gebruiken zodat die tests blijven werken.

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_lessons.py -q`
Verwacht: de aangepaste en nieuwe tests falen (respons mist `examples`).

- [ ] **Stap 3: Implementeer**

In `app/routers/lessons.py`:

1. In `_RULES_SCHEMA` binnen `"properties"` naast `"rules"` toevoegen, en
   `"required"` wordt `["rules", "examples"]`:

```python
        "examples": {
            "type": "array",
            "items": {"type": "string"},
        },
```

2. `_EXTRACT_SYSTEM` vervangen door:

```python
_EXTRACT_SYSTEM = (
    "Je leest foto's of scans van pagina's uit een Spaans lesboek voor "
    "Nederlandstaligen. Een pagina kan uitleg bevatten, oefenopgaven, of "
    "beide. Zet beide om:\n"
    "- Uitleg wordt een grammaticaregel (rules): een korte Nederlandse "
    "titel, een beknopte Nederlandse uitleg in eigen woorden, en de Spaanse "
    "voorbeeldzinnen van de pagina met hun Nederlandse vertaling (vertaal "
    "zelf als de vertaling er niet bij staat).\n"
    "- Elke oefenopgave wordt een voorbeeldoefening (examples): neem de "
    "opgave letterlijk over als één tekst, inclusief de opdracht erboven en "
    "het antwoord als dat afgedrukt staat.\n"
    "Sla paginanummers en kopteksten over. Verzin niets dat niet op de "
    "pagina staat. Splits verschillende onderwerpen in aparte regels."
)
```

3. Na `_clean_rules` een helper toevoegen en het endpoint aanpassen:

```python
def _clean_examples(data):
    return [ex.strip() for ex in data.get("examples", []) if ex.strip()]
```

en in `extract_lesson` (het slot van de functie):

```python
    rules = _clean_rules(data)
    examples = _clean_examples(data)
    if not rules and not examples:
        raise HTTPException(
            status_code=502, detail="Geen lesstof herkend in de scan(s)"
        )
    return {"rules": rules, "examples": examples}
```

4. De tekstregel in de user-content ("Zet de lesstof op deze pagina('s) om
   naar grammaticaregels.") wordt: `"Zet de lesstof op deze pagina('s) om
   naar grammaticaregels en voorbeeldoefeningen."`

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_lessons.py -q`
Verwacht: 12 passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` → alles groen.

```bash
git add app/routers/lessons.py tests/test_api_lessons.py
git commit -m "Scan-upload: extractie herkent ook oefenopgaven als voorbeeldoefeningen"
```

---

### Taak 3: Voorbeelden in lesstof en generator

**Files:**
- Modify: `app/lesstof.py`
- Modify: `app/routers/exercises.py` (guard + generatie-instructie)
- Test: `tests/test_lesstof.py` en `tests/test_api_exercises.py` (uitbreiden)

**Interfaces:**
- Consumes: `list_examples(chapter_id, conn)` uit `app/routers/examples.py` (Taak 1).
- Produces: `lesson_context` bevat sectie `"Voorbeeldoefeningen uit het boek:"` als er voorbeelden zijn. Generator: 400 alleen als grammatica én voorbeelden ontbreken (detail: `"Dit hoofdstuk heeft nog geen grammatica of voorbeeldoefeningen om oefeningen op te baseren"`).

- [ ] **Stap 1: Schrijf de falende tests**

Toevoegen aan `tests/test_lesstof.py` in `TestLessonContext`:

```python
    def test_voorbeeldoefeningen_sectie(self, client, app_instance, chapter_id):
        client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "Completa: Yo ___ (ser) de Holanda.",
        })
        context = _context(app_instance, chapter_id)
        assert "Voorbeeldoefeningen uit het boek:" in context
        assert "- Completa: Yo ___ (ser) de Holanda." in context

    def test_geen_voorbeelden_geen_sectie(self, client, app_instance, chapter_id):
        client.post("/api/words", json={
            "chapter_id": chapter_id, "spanish": "sol", "dutch": "zon",
        })
        assert "Voorbeeldoefeningen" not in _context(app_instance, chapter_id)
```

Toevoegen aan `tests/test_api_exercises.py` in `TestGenereren`:

```python
    def test_alleen_voorbeeldoefeningen_is_genoeg(
        self, client, chapter_id, monkeypatch
    ):
        client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "Completa: Yo ___ (ser) de Holanda.",
        })
        prompts = []

        def fake(**kwargs):
            prompts.append(kwargs)
            return {"exercises": [_gegenereerde_oefening()]}

        monkeypatch.setattr(llm, "complete_json", fake)
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_id}
        )
        assert response.status_code == 200
        # De voorbeelden zitten in de prompt en de stijl-instructie in de systeemprompt
        assert "Completa: Yo ___" in prompts[0]["messages"][0]["content"]
        assert "kopieer ze niet letterlijk" in prompts[0]["system"]
```

(De bestaande `test_hoofdstuk_zonder_grammatica_is_400` blijft geldig: een
leeg hoofdstuk heeft ook geen voorbeelden.)

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_lesstof.py tests/test_api_exercises.py -q`
Verwacht: de drie nieuwe tests falen (sectie ontbreekt; generate geeft 400).

- [ ] **Stap 3: Implementeer**

In `app/lesstof.py`: import uitbreiden met
`from app.routers.examples import list_examples` en aan het einde van
`lesson_context`, ná het werkwoorden-blok en vóór de `return`:

```python
    examples = list_examples(chapter_id, conn)
    if examples:
        parts.append("\nVoorbeeldoefeningen uit het boek:")
        parts.extend(f"- {ex['text']}" for ex in examples)
```

In `app/routers/exercises.py`:

1. Import toevoegen: `from app.routers.examples import list_examples`.
2. De guard in `generate_exercises` wordt:

```python
    if not list_rules(body.chapter_id, conn) and not list_examples(
        body.chapter_id, conn
    ):
        raise HTTPException(
            status_code=400,
            detail="Dit hoofdstuk heeft nog geen grammatica of "
            "voorbeeldoefeningen om oefeningen op te baseren",
        )
```

3. Aan `_GENERATE_SYSTEM` (na de zin over afleidbare antwoorden) toevoegen:

```python
    " Staan er voorbeeldoefeningen uit het boek in de lesstof: maak "
    "oefeningen in dezelfde stijl en over dezelfde stof, maar kopieer ze "
    "niet letterlijk."
```

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_lesstof.py tests/test_api_exercises.py -q`
Verwacht: alles passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` → alles groen.

```bash
git add app/lesstof.py app/routers/exercises.py tests/test_lesstof.py tests/test_api_exercises.py
git commit -m "Lesstof: voorbeeldoefeningen sturen generator en gesprek"
```

---

### Taak 4: Frontend — nakijkscherm, beheerscherm en teller

**Files:**
- Modify: `app/routers/chapters.py` (`example_count`-subselect)
- Modify: `app/static/js/views/lesson-upload.js` (tweede sectie + opslaan)
- Create: `app/static/js/views/examples-entry.js`
- Modify: `app/static/js/app.js` (import + route)
- Modify: `app/static/js/views/chapter.js` (Invoer-rij)
- Test: `tests/test_api_chapters.py` (uitbreiden)

**Interfaces:**
- Consumes: `GET/POST/DELETE /api/examples` (Taak 1), extract-respons `{rules, examples}` (Taak 2).
- Produces: `GET /api/chapters` bevat `example_count`; route `#/h/{id}/voorbeelden` → `renderExamplesEntry(view, chapterId)`.

- [ ] **Stap 1: Schrijf de falende backend-test**

Toevoegen aan `tests/test_api_chapters.py`:

```python
def test_chapter_telt_voorbeeldoefeningen(client):
    chapter_id = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
    client.post("/api/examples", json={
        "chapter_id": chapter_id, "text": "Completa: ___",
    })
    chapter = client.get("/api/chapters").json()[0]
    assert chapter["example_count"] == 1
```

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_chapters.py -q`
Verwacht: FAIL met `KeyError: 'example_count'`.

- [ ] **Stap 2: Breid de chapters-query uit**

In `app/routers/chapters.py`, in `list_chapters`, na de `exercise_count`-regel:

```sql
(SELECT COUNT(*) FROM example_exercises x WHERE x.chapter_id = c.id) AS example_count
```

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_chapters.py -q` → passed.

- [ ] **Stap 3: Nakijkscherm — tweede sectie**

In `app/static/js/views/lesson-upload.js`:

1. De aanroep `renderReviewStep(rules)` in de leesknop-handler wordt:

```js
        const {rules, examples} = await api(`/api/chapters/${chapterId}/lessons/extract`, {
          method: 'POST', body: {images},
        });
        renderReviewStep(rules, examples);
```

2. `renderReviewStep(rules)` wordt `renderReviewStep(rules, examples)`. Binnen
   de functie, na de bestaande `ruleEditor`-definitie, toevoegen:

```js
    function exampleEditor(text) {
      const textInput = el('textarea', {rows: '3', 'aria-label': 'Opgave'});
      textInput.value = text;
      const card = el('div', {class: 'card', 'data-example': ''},
        el('div', {class: 'row'},
          el('label', {class: 'grow'}, 'Opgave'),
          el('button', {
            class: 'icon-btn fixed', type: 'button', title: 'Voorbeeld verwijderen',
            onclick: () => card.remove(),
          }, '🗑️'),
        ),
        textInput,
      );
      card.readExample = () => textInput.value.trim();
      return card;
    }

    const examplesEditorsWrap = el('div', {}, ...examples.map(exampleEditor));
```

3. De opslaan-handler wordt (volledige vervanging van de `onclick`):

```js
      onclick: async () => {
        const ruleCards = [...editorsWrap.querySelectorAll('[data-rule]')];
        const rulePayloads = ruleCards.map((card) => card.readRule());
        const exampleCards = [...examplesEditorsWrap.querySelectorAll('[data-example]')];
        const exampleTexts = exampleCards.map((card) => card.readExample());
        if (!rulePayloads.some((rule) => rule.title) && !exampleTexts.some(Boolean)) {
          status.textContent = 'Er is niets om op te slaan.';
          return;
        }
        saveButton.disabled = true;
        againButton.disabled = true;
        try {
          for (const [i, card] of ruleCards.entries()) {
            if (rulePayloads[i].title) {
              await api('/api/grammar', {
                method: 'POST', body: {chapter_id: chapterId, ...rulePayloads[i]},
              });
              card.remove();
            }
          }
          for (const [i, card] of exampleCards.entries()) {
            if (exampleTexts[i]) {
              await api('/api/examples', {
                method: 'POST', body: {chapter_id: chapterId, text: exampleTexts[i]},
              });
              card.remove();
            }
          }
          location.hash = `#/h/${chapterId}`;
        } catch (err) {
          saveButton.disabled = false;
          againButton.disabled = false;
          status.textContent =
            `Opslaan mislukte: ${err.message}. Het al opgeslagen deel is uit de lijst gehaald — controleer de rest en probeer opnieuw.`;
        }
      },
```

4. Het slot van `renderReviewStep` (de `setChildren(container, ...)`) wordt:

```js
    const teller = [
      rules.length ? `${rules.length} regel${rules.length === 1 ? '' : 's'}` : null,
      examples.length ? `${examples.length} voorbeeldoefening${examples.length === 1 ? '' : 'en'}` : null,
    ].filter(Boolean).join(' en ');

    setChildren(container,
      el('p', {class: 'muted'}, `${teller} gelezen — kijk na, pas aan en sla op.`),
      editorsWrap,
      examples.length ? el('div', {class: 'eyebrow'}, 'Voorbeeldoefeningen') : null,
      examplesEditorsWrap,
      el('div', {class: 'row', style: 'margin-top:0.75rem'},
        el('button', {
          class: 'btn-ghost fixed', type: 'button',
          onclick: () => examplesEditorsWrap.append(exampleEditor('')),
        }, '+ voorbeeldoefening'),
        saveButton,
        againButton,
      ),
      status,
    );
```

- [ ] **Stap 4: Beheerscherm**

Maak `app/static/js/views/examples-entry.js`:

```js
import {api, el, setChildren} from '../api.js';

export async function renderExamplesEntry(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  const textInput = el('textarea', {
    rows: '3', 'aria-label': 'Opgave',
    placeholder: 'Completa: Yo ___ (ser) de Holanda.',
  });

  const form = el('form', {
    class: 'card',
    onsubmit: async (e) => {
      e.preventDefault();
      const text = textInput.value.trim();
      if (!text) return;
      await api('/api/examples', {
        method: 'POST', body: {chapter_id: chapterId, text},
      });
      textInput.value = '';
      textInput.focus();
      await refreshList();
    },
  },
    el('label', {}, 'Nieuwe voorbeeldoefening'), textInput,
    el('div', {class: 'row', style: 'margin-top:0.5rem'},
      el('span', {class: 'muted', style: 'font-size:0.8rem; align-self:center; flex:1'},
        'Opgaven uit het boek sturen de oefeningen-generator en het gesprek.'),
      el('button', {class: 'btn-primary fixed', type: 'submit'}, 'Toevoegen'),
    ),
  );

  const listWrap = el('div', {});

  async function refreshList() {
    const examples = await api(`/api/examples?chapter_id=${chapterId}`);
    setChildren(listWrap,
      el('div', {class: 'eyebrow'}, `${examples.length} voorbeeldoefeningen`),
      examples.length
        ? el('div', {}, ...examples.map(exampleCard))
        : el('p', {class: 'muted'},
            'Nog geen voorbeeldoefeningen — scan een oefenpagina via "Les uploaden" of voeg er hierboven één toe.'),
    );
  }

  function exampleCard(example) {
    return el('div', {class: 'card'},
      el('div', {style: 'display:flex; align-items:baseline; gap:0.6rem'},
        el('p', {style: 'flex:1; white-space:pre-wrap; margin:0'}, example.text),
        el('button', {
          class: 'icon-btn', title: 'Verwijderen', 'aria-label': 'Verwijder voorbeeld',
          onclick: async () => {
            if (confirm('Dit voorbeeld verwijderen?')) {
              await api(`/api/examples/${example.id}`, {method: 'DELETE'});
              refreshList();
            }
          },
        }, '🗑️'),
      ),
    );
  }

  setChildren(view,
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Voorbeeldoefeningen'),
    form,
    listWrap,
  );
  await refreshList();
}
```

- [ ] **Stap 5: Route en Invoer-rij**

In `app/static/js/app.js` de import toevoegen:

```js
import {renderExamplesEntry} from './views/examples-entry.js';
```

en in de `routes`-lijst, na de `grammatica`-route:

```js
[/^h\/(\d+)\/voorbeelden$/, (id) => renderExamplesEntry(view, +id)],
```

In `app/static/js/views/chapter.js`, in het Invoer-lijstje na de Grammatica-rij:

```js
el('li', {},
  el('a', {class: 'grow', href: `#/h/${chapterId}/voorbeelden`}, 'Voorbeeldoefeningen'),
  el('span', {class: 'counts'}, String(chapter.example_count))),
```

- [ ] **Stap 6: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'` → alles groen.

```bash
git add app/routers/chapters.py app/static/js/views/lesson-upload.js app/static/js/views/examples-entry.js app/static/js/app.js app/static/js/views/chapter.js tests/test_api_chapters.py
git commit -m "Voorbeeldoefeningen: nakijksectie, beheerscherm en teller"
```

---

### Taak 5: Verificatie in de echte UI

**Files:** geen (alleen verificatie).

- [ ] **Stap 1: Draai alles**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'`
Verwacht: alles groen.

- [ ] **Stap 2: Verifieer in de echte UI**

Gebruik de project-skill `verify` (testinstantie op poort 8765):
- Maak met PIL een testpagina met uitleg (een grammaticaregel + voorbeeldzinnen) én twee genummerde oefenopgaven eronder; sla op als JPEG in de scratchpad.
- Hoofdstukscherm → "📷 Les uploaden" → testpagina → "📖 Lees les" (echte vision-aanroep).
- Nakijkscherm: beide secties zichtbaar; pas een opgave aan; "💾 Alles opslaan" → terug op het hoofdstukscherm; Invoer-rij "Voorbeeldoefeningen" toont de teller.
- Beheerscherm: `#/h/{id}/voorbeelden` — lijst klopt, voeg handmatig een voorbeeld toe, verwijder er één.
- Generator-guard: maak een twééde hoofdstuk met alléén een handmatig voorbeeld (geen grammatica) en klik "✨ Genereer oefeningen" — verwacht: generatie slaagt (echte aanroep) in plaats van de oude 400-melding.
- Controleer dat de gegenereerde oefeningen qua stof aansluiten op het voorbeeld.
