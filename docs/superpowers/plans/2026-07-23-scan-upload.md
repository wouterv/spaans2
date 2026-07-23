# Fase 2: Scan-upload met nakijkscherm — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gescande lesboek-pagina's uploaden per hoofdstuk; Claude (vision) zet ze om naar grammaticaregels die de gebruiker in een nakijkscherm bewerkt en daarna opslaat als gewone `grammar_rules`.

**Architecture:** De frontend verkleint afbeeldingen in de browser (canvas, max 2000 px) en stuurt ze als base64-JSON naar één nieuw endpoint (`POST /api/chapters/{id}/lessons/extract`) dat via `llm.complete_json` een voorstel teruggeeft — er wordt níéts opgeslagen. Het nakijkscherm (nieuwe view) toont bewerkbare regel-kaarten en slaat bij akkoord elke regel op via het bestaande `POST /api/grammar`-endpoint.

**Tech Stack:** FastAPI, bestaande `app/llm.py` (Claude vision via image content-blocks), vanilla-JS (canvas-resize, geen build-stap), pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-llm-oefeningen-scans-conversatie-design.md` (sectie "Fase 2 — Scan-upload")

## Global Constraints

- Nederlands in alle UI-teksten, commit-messages, docstrings en foutmeldingen (bestaande stijl).
- Commit-messages in de stijl `Onderwerp: beschrijving`, afgesloten met:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` en de Claude-Session-regel van de sessie.
- Niets buiten `app/llm.py` importeert `anthropic`; afbeeldingen gaan als content-blocks in `messages` mee (spec).
- Tests draaien nooit tegen de echte API: mock `llm.complete_json` met `monkeypatch`.
- Scans worden niet op de server bewaard; het extract-endpoint schrijft niets naar de database.
- Volledige testsuite groen na elke taak: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'` (mét glob-quotes; kale map faalt).

---

### Taak 1: Extract-endpoint

**Files:**
- Create: `app/routers/lessons.py`
- Modify: `app/main.py:11` (import) en de router-registraties (na `exercises.router`)
- Test: `tests/test_api_lessons.py` (nieuw)

**Interfaces:**
- Consumes: `llm.complete_json(system, messages, schema, max_tokens=16000)` en `llm.LLMError` uit `app/llm.py`; `chapter_or_404(conn, chapter_id)` uit `app/deps.py`; `get_conn` uit `app/deps.py`.
- Produces: `POST /api/chapters/{chapter_id}/lessons/extract` met body
  `{"images": [{"media_type": "image/jpeg"|"image/png"|"image/webp", "data": "<base64>"}]}` (1–10 stuks) →
  `{"rules": [{"title": str, "explanation": str, "examples": [{"spanish": str, "dutch": str}]}]}`.
  Fouten: 404 onbekend hoofdstuk, 422 lege/te lange lijst of verkeerd media_type (Pydantic), 400 ongeldige base64 of afbeelding te groot, 503 LLM-storing (Nederlandse detail), 502 geen lesstof herkend.
  Module-constante `MAX_IMAGE_BYTES = 8_000_000` (testbaar via monkeypatch).

- [ ] **Stap 1: Schrijf de falende tests**

Maak `tests/test_api_lessons.py`:

```python
import base64

import pytest

from app import llm
from app.routers import lessons

GELDIGE_DATA = base64.b64encode(b"nep-afbeelding-bytes").decode()


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def _body(n=1, media_type="image/jpeg", data=GELDIGE_DATA):
    return {"images": [{"media_type": media_type, "data": data}] * n}


def _regel(**overrides):
    regel = {
        "title": "Ser en estar",
        "explanation": "Ser voor blijvend, estar voor tijdelijk.",
        "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
    }
    regel.update(overrides)
    return regel


class TestExtract:
    def test_geeft_regels_terug_en_slaat_niets_op(
        self, client, chapter_id, monkeypatch
    ):
        aanroepen = []

        def fake(**kwargs):
            aanroepen.append(kwargs)
            return {"rules": [_regel()]}

        monkeypatch.setattr(llm, "complete_json", fake)
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body(n=2)
        )
        assert response.status_code == 200
        assert response.json() == {"rules": [_regel()]}
        # De afbeeldingen zitten als image-content-blocks in het bericht
        content = aanroepen[0]["messages"][0]["content"]
        image_blocks = [b for b in content if b["type"] == "image"]
        assert len(image_blocks) == 2
        assert image_blocks[0]["source"] == {
            "type": "base64", "media_type": "image/jpeg", "data": GELDIGE_DATA,
        }
        assert content[-1]["type"] == "text"
        # Er is niets in de database beland
        assert client.get(f"/api/grammar?chapter_id={chapter_id}").json() == []

    def test_lege_titel_en_leeg_voorbeeld_worden_gefilterd(
        self, client, chapter_id, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"rules": [
            _regel(),
            _regel(title="   "),
            _regel(examples=[
                {"spanish": "  ", "dutch": "leeg"},
                {"spanish": "Soy Wouter", "dutch": "Ik ben Wouter"},
            ]),
        ]})
        rules = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        ).json()["rules"]
        assert len(rules) == 2
        assert rules[1]["examples"] == [
            {"spanish": "Soy Wouter", "dutch": "Ik ben Wouter"}
        ]

    def test_onbekend_hoofdstuk_is_404(self, client, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"rules": []})
        assert (
            client.post("/api/chapters/999/lessons/extract", json=_body()).status_code
            == 404
        )

    def test_zonder_afbeeldingen_is_422(self, client, chapter_id):
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json={"images": []}
        )
        assert response.status_code == 422

    def test_verkeerd_bestandstype_is_422(self, client, chapter_id):
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract",
            json=_body(media_type="application/pdf"),
        )
        assert response.status_code == 422

    def test_ongeldige_base64_is_400(self, client, chapter_id):
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract",
            json=_body(data="dit is geen base64!!!"),
        )
        assert response.status_code == 400

    def test_te_grote_afbeelding_is_400(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(lessons, "MAX_IMAGE_BYTES", 4)
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 400
        assert "te groot" in response.json()["detail"]

    def test_llm_storing_is_503(self, client, chapter_id, monkeypatch):
        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Geen verbinding met de taaldienst"

    def test_geen_regels_herkend_is_502(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"rules": []})
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 502
```

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_lessons.py -q`
Verwacht: ImportError (`app.routers.lessons` bestaat niet).

- [ ] **Stap 3: Schrijf de router en registreer hem**

Maak `app/routers/lessons.py`:

```python
"""Scan-upload: lesboek-pagina's laten uitlezen door de LLM (vision).

Het extract-endpoint geeft alleen een voorstel terug; opslaan gebeurt
pas na het nakijken, via het bestaande /api/grammar-endpoint.
"""

import base64
import binascii
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import llm
from app.deps import chapter_or_404, get_conn

router = APIRouter(prefix="/api/chapters")

MAX_IMAGE_BYTES = 8_000_000

_RULES_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "explanation": {"type": "string"},
                    "examples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "spanish": {"type": "string"},
                                "dutch": {"type": "string"},
                            },
                            "required": ["spanish", "dutch"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "explanation", "examples"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rules"],
    "additionalProperties": False,
}

_EXTRACT_SYSTEM = (
    "Je leest foto's of scans van pagina's uit een Spaans lesboek voor "
    "Nederlandstaligen. Zet de leerstof om naar grammaticaregels: een korte "
    "Nederlandse titel, een beknopte Nederlandse uitleg in eigen woorden, en "
    "de Spaanse voorbeeldzinnen van de pagina met hun Nederlandse vertaling "
    "(vertaal zelf als de vertaling er niet bij staat). Neem alleen leerstof "
    "over: sla invuloefeningen, opgaven en paginanummers over. Verzin geen "
    "regels die niet op de pagina staan. Splits verschillende onderwerpen in "
    "aparte regels."
)


class ImageIn(BaseModel):
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(min_length=1)


class ExtractRequest(BaseModel):
    images: list[ImageIn] = Field(min_length=1, max_length=10)


def _validate_images(images):
    for image in images:
        try:
            raw = base64.b64decode(image.data, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Ongeldige afbeelding")
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Afbeelding is te groot (max 8 MB na verkleinen)",
            )


def _clean_rules(data):
    rules = []
    for rule in data.get("rules", []):
        title = rule["title"].strip()
        if not title:
            continue
        examples = [
            {"spanish": ex["spanish"].strip(), "dutch": ex["dutch"].strip()}
            for ex in rule["examples"]
            if ex["spanish"].strip()
        ]
        rules.append(
            {"title": title, "explanation": rule["explanation"].strip(),
             "examples": examples}
        )
    return rules


@router.post("/{chapter_id}/lessons/extract")
def extract_lesson(chapter_id: int, body: ExtractRequest, conn=Depends(get_conn)):
    chapter_or_404(conn, chapter_id)
    _validate_images(body.images)
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image.media_type,
                "data": image.data,
            },
        }
        for image in body.images
    ]
    content.append({
        "type": "text",
        "text": "Zet de lesstof op deze pagina('s) om naar grammaticaregels.",
    })
    try:
        data = llm.complete_json(
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": content}],
            schema=_RULES_SCHEMA,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    rules = _clean_rules(data)
    if not rules:
        raise HTTPException(
            status_code=502, detail="Geen lesstof herkend in de scan(s)"
        )
    return {"rules": rules}
```

In `app/main.py` de import op regel 11 uitbreiden:

```python
from app.routers import chapters, exercises, grammar, lessons, practice, verbs, words
```

en na `app.include_router(exercises.router)`:

```python
app.include_router(lessons.router)
```

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest tests/test_api_lessons.py -q`
Verwacht: 9 passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` → alles groen.

```bash
git add app/routers/lessons.py app/main.py tests/test_api_lessons.py
git commit -m "Scan-upload: extract-endpoint leest lesboek-pagina's via de LLM"
```

---

### Taak 2: Upload- en nakijkscherm

**Files:**
- Create: `app/static/js/views/lesson-upload.js`
- Modify: `app/static/js/app.js` (import + route)
- Modify: `app/static/js/views/chapter.js` (knop in de Grammatica-kaart)

**Interfaces:**
- Consumes: `POST /api/chapters/{id}/lessons/extract` (Taak 1); bestaand `POST /api/grammar` met body `{chapter_id, title, explanation, examples: [{spanish, dutch}]}`; helpers `api`, `el`, `setChildren` uit `api.js` (`api()` gooit bij fouten een `Error` met de Nederlandse detail-tekst).
- Produces: route `#/h/{id}/les-uploaden` → `renderLessonUpload(view, chapterId)`.

- [ ] **Stap 1: Schrijf de view**

Maak `app/static/js/views/lesson-upload.js`:

```js
import {api, el, setChildren} from '../api.js';

const MAX_DIM = 2000;

// Verklein in de browser (scheelt upload en API-kosten) en geef base64 terug
async function fileToImagePayload(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_DIM / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
  return {media_type: 'image/jpeg', data: dataUrl.split(',')[1]};
}

export async function renderLessonUpload(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  const container = el('div', {});
  setChildren(view, 
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Les uploaden'),
    container,
  );

  /* ── Stap 1: scans kiezen en laten uitlezen ── */

  function renderUploadStep() {
    const fileInput = el('input', {
      type: 'file', accept: 'image/*', multiple: '',
      'aria-label': 'Scans van de les',
    });
    const preview = el('div', {class: 'row', style: 'flex-wrap:wrap; gap:0.5rem'});
    const status = el('p', {class: 'muted'});
    const readButton = el('button', {class: 'btn-primary btn-big', disabled: ''},
      '📖 Lees les');

    fileInput.addEventListener('change', () => {
      setChildren(preview, ...[...fileInput.files].map((file) => {
        const img = el('img', {
          src: URL.createObjectURL(file), alt: file.name,
          style: 'max-height:120px; max-width:120px; border-radius:6px',
        });
        img.addEventListener('load', () => URL.revokeObjectURL(img.src));
        return img;
      }));
      readButton.disabled = fileInput.files.length === 0;
    });

    readButton.addEventListener('click', async () => {
      readButton.disabled = true;
      fileInput.disabled = true;
      status.textContent = 'Scans worden gelezen… dit kan een minuut duren.';
      try {
        const images = [];
        for (const file of fileInput.files) images.push(await fileToImagePayload(file));
        const {rules} = await api(`/api/chapters/${chapterId}/lessons/extract`, {
          method: 'POST', body: {images},
        });
        renderReviewStep(rules);
      } catch (err) {
        status.textContent = `Lezen mislukte: ${err.message}`;
        readButton.disabled = false;
        fileInput.disabled = false;
      }
    });

    setChildren(container, 
      el('div', {class: 'card'},
        el('p', {class: 'muted'},
          'Kies één of meer foto’s of scans van de les. Na het uitlezen kun je alles nakijken en aanpassen voordat het wordt opgeslagen.'),
        fileInput, preview,
        el('div', {class: 'row', style: 'margin-top:0.75rem'}, readButton),
        status,
      ),
    );
  }

  /* ── Stap 2: nakijken, bewerken en opslaan ── */

  function renderReviewStep(rules) {
    const editorsWrap = el('div', {});
    const status = el('p', {class: 'muted'});

    function exampleRow(spanish = '', dutch = '') {
      const row = el('div', {class: 'row', style: 'margin-bottom:0.4rem'},
        el('input', {
          type: 'text', value: spanish, autocapitalize: 'off',
          'aria-label': 'Voorbeeld (Spaans)', 'data-es': '',
        }),
        el('input', {
          type: 'text', value: dutch, autocapitalize: 'off',
          'aria-label': 'Voorbeeld (Nederlands)', 'data-nl': '',
        }),
        el('button', {
          class: 'icon-btn fixed', type: 'button', title: 'Voorbeeld verwijderen',
          onclick: () => row.remove(),
        }, '✖️'),
      );
      return row;
    }

    function ruleEditor(rule) {
      const titleInput = el('input', {
        type: 'text', value: rule.title, 'aria-label': 'Titel',
      });
      const explanationInput = el('textarea', {rows: '4', 'aria-label': 'Uitleg'});
      explanationInput.value = rule.explanation;
      const examplesWrap = el('div', {},
        ...rule.examples.map((ex) => exampleRow(ex.spanish, ex.dutch)));
      const card = el('div', {class: 'card', 'data-rule': ''},
        el('div', {class: 'row'},
          el('label', {class: 'grow'}, 'Titel'),
          el('button', {
            class: 'icon-btn fixed', type: 'button', title: 'Regel verwijderen',
            onclick: () => card.remove(),
          }, '🗑️'),
        ),
        titleInput,
        el('label', {style: 'margin-top:0.6rem'}, 'Uitleg'), explanationInput,
        el('label', {style: 'margin-top:0.6rem'}, 'Voorbeelden'), examplesWrap,
        el('button', {
          class: 'btn-ghost fixed', type: 'button',
          onclick: () => examplesWrap.append(exampleRow()),
        }, '+ voorbeeld'),
      );
      card.readRule = () => ({
        title: titleInput.value.trim(),
        explanation: explanationInput.value.trim(),
        examples: [...examplesWrap.children]
          .map((row) => ({
            spanish: row.querySelector('[data-es]').value.trim(),
            dutch: row.querySelector('[data-nl]').value.trim(),
          }))
          .filter((example) => example.spanish),
      });
      return card;
    }

    setChildren(editorsWrap, ...rules.map(ruleEditor));

    const saveButton = el('button', {
      class: 'btn-primary btn-big',
      onclick: async () => {
        const payloads = [...editorsWrap.querySelectorAll('[data-rule]')]
          .map((card) => card.readRule())
          .filter((rule) => rule.title);
        if (!payloads.length) {
          status.textContent = 'Er is niets om op te slaan.';
          return;
        }
        saveButton.disabled = true;
        try {
          for (const payload of payloads) {
            await api('/api/grammar', {
              method: 'POST', body: {chapter_id: chapterId, ...payload},
            });
          }
          location.hash = `#/h/${chapterId}/grammatica`;
        } catch (err) {
          saveButton.disabled = false;
          status.textContent = `Opslaan mislukte: ${err.message}`;
        }
      },
    }, '💾 Alles opslaan');

    setChildren(container, 
      el('p', {class: 'muted'},
        `${rules.length} regel${rules.length === 1 ? '' : 's'} gelezen — kijk na, pas aan en sla op.`),
      editorsWrap,
      el('div', {class: 'row', style: 'margin-top:0.75rem'},
        saveButton,
        el('button', {class: 'btn-ghost', onclick: renderUploadStep}, '📷 Opnieuw'),
      ),
      status,
    );
  }

  renderUploadStep();
}
```

- [ ] **Stap 2: Sluit de route en de knop aan**

In `app/static/js/app.js` de import toevoegen:

```js
import {renderLessonUpload} from './views/lesson-upload.js';
```

en in de `routes`-lijst, na de `lezen`-route:

```js
[/^h\/(\d+)\/les-uploaden$/, (id) => renderLessonUpload(view, +id)],
```

In `app/static/js/views/chapter.js`, in de kaart "Grammatica", de rij uitbreiden met de uploadknop:

```js
el(
  'div',
  {class: 'card'},
  el('h2', {}, 'Grammatica'),
  el('div', {class: 'row'},
    el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/lezen`}, '📖 Lezen & luisteren'),
    el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/les-uploaden`}, '📷 Les uploaden')),
),
```

- [ ] **Stap 3: Volledige suite + commit**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'` → alles groen.

```bash
git add app/static/js/views/lesson-upload.js app/static/js/app.js app/static/js/views/chapter.js
git commit -m "Scan-upload: upload- en nakijkscherm voor gescande lessen"
```

---

### Taak 3: Afronding — README en verificatie in de echte UI

**Files:**
- Modify: `README.md` (één zin bij de LLM-functies)

**Interfaces:** geen — documentatie en verificatie.

- [ ] **Stap 1: README bijwerken**

In `README.md`, in de bestaande LLM-sectie, "oefeningen genereren, vertaalbeoordeling" uitbreiden naar "oefeningen genereren, vertaalbeoordeling, scans uitlezen".

- [ ] **Stap 2: Draai alles**

Run: `/home/wouter/spaans/.venv/bin/python -m pytest -q` en `node --test 'tests/js/*.mjs'`
Verwacht: alles groen.

- [ ] **Stap 3: Verifieer in de echte UI**

Gebruik de project-skill `verify` (testinstantie op poort 8765, los van productie):
- Maak met PIL een test-"lespagina" (witte achtergrond, leesbare tekst met een grammaticaregel en twee voorbeeldzinnen) en sla die op als JPEG in de scratchpad.
- Hoofdstukscherm → "📷 Les uploaden" → bestand kiezen → thumbnail zichtbaar → "📖 Lees les".
- De testinstantie gebruikt de echte API-key uit `.env` — dit is één echte vision-aanroep (kost enkele centen) en bewijst de hele keten end-to-end.
- Nakijkscherm: controleer dat de regel uit de testafbeelding herkend is, pas de titel aan, verwijder/voeg een voorbeeld toe, klik "💾 Alles opslaan".
- Controleer dat je op het grammatica-invoerscherm belandt en de regel daar staat, en dat de teller op het hoofdstukscherm is opgehoogd.
- Foutpad: upload met een kapotte key (of tijdelijk hernoemde env-var) hoeft niet apart — het 503-pad is al door pytest gedekt; controleer in de UI alleen dat een mislukte extractie de knop weer vrijgeeft (bijv. door de testinstantie zonder key te starten als dat eenvoudig kan, anders overslaan).

- [ ] **Stap 4: Commit**

```bash
git add README.md
git commit -m "Scan-upload: README bijgewerkt"
```
