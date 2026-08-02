# Werkwoorden uit les-scans — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Les-scans herkennen ook werkwoorden die de les aanbiedt; na nakijken (met automatisch opgehaalde presente-vormen) worden ze als oefenbare werkwoorden opgeslagen.

**Architecture:** Het bestaande `POST /api/chapters/{id}/lessons/extract` (één vision-call) geeft naast `rules` en `examples` een derde array `verbs` terug, gededupliceerd tegen de werkwoorden die al in het hoofdstuk staan. Het nakijkscherm (`lesson-upload.js`) toont per werkwoord een bewerkbare kaart, haalt de zes presente-vormen op via het bestaande `GET /api/verbs/conjugate` (Wiktionary) en slaat op via het bestaande `POST /api/verbs`. Geen migratie, geen nieuwe endpoints.

**Tech Stack:** FastAPI + SQLite (geen ORM), vanilla-JS frontend zonder build-stap, pytest (LLM gemockt via `monkeypatch`).

**Spec:** `docs/superpowers/specs/2026-08-02-werkwoorden-uit-les-scan-design.md`

## Global Constraints

- Commit-messages in het Nederlands, afgesloten met `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Tests draaien met `.venv/bin/python -m pytest tests/` (pytest zit alleen in de venv); JS-tests met `node --test 'tests/js/*.mjs'`.
- UI-teksten in het Nederlands.
- Alleen de tijd "presente".
- De respons van lessons/extract wordt `{rules, examples, verbs}`; de 502-guard "Geen lesstof herkend in de scan(s)" treedt alleen op als alle drie leeg zijn.

---

### Task 1: Backend — verbs in lessons/extract

**Files:**
- Modify: `app/routers/lessons.py`
- Test: `tests/test_api_lessons.py`

**Interfaces:**
- Consumes: bestaande fixtures `client` en `chapter_id` in `tests/test_api_lessons.py`; bestaande helpers `_body()` en `_regel()` daar; tabel `verbs(chapter_id, infinitive_es, translation_nl)`; `POST /api/verbs` (bestaand) om in een test een bestaand werkwoord aan te maken.
- Produces: `POST /api/chapters/{chapter_id}/lessons/extract` → 200 `{"rules": [...], "examples": [...], "verbs": [{"infinitive_es": str, "translation_nl": str}]}`. Infinitieven zijn gestript en lowercased; items zonder infinitief of vertaling vervallen; werkwoorden die al in het hoofdstuk staan (hoofdletterongevoelig op infinitief) én dubbelen binnen het voorstel zijn eruit gefilterd. Task 2 gebruikt deze respons.

- [ ] **Step 1: Schrijf de falende tests**

In `tests/test_api_lessons.py`. Eerst twee bestaande plekken aanpassen aan de nieuwe respons-vorm:

1. In `test_geeft_regels_terug_en_slaat_niets_op` (regel ~45):

```python
        assert response.json() == {"rules": [_regel()], "examples": [], "verbs": []}
```

2. In `test_geen_regels_herkend_is_502` (regel ~123) de mock ongewijzigd laten (geen `verbs`-sleutel — `.get` vangt dat op); de test blijft 502 verwachten.

Dan onderaan het bestand een nieuwe testklasse (met een vormen-helper op moduleniveau, onder `_regel`):

```python
_FORMS = {
    "yo": "hablo", "tu": "hablas", "el": "habla",
    "nosotros": "hablamos", "vosotros": "habláis", "ellos": "hablan",
}


class TestExtractVerbs:
    def test_geeft_werkwoorden_terug_en_slaat_niets_op(
        self, client, chapter_id, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {
            "rules": [], "examples": [], "verbs": [
                {"infinitive_es": " Hablar ", "translation_nl": " praten "},
                {"infinitive_es": "", "translation_nl": "leeg"},
                {"infinitive_es": "comer", "translation_nl": "  "},
            ],
        })
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 200
        assert response.json()["verbs"] == [
            {"infinitive_es": "hablar", "translation_nl": "praten"}
        ]
        # Er is niets opgeslagen: nakijken gebeurt in de frontend
        assert client.get(f"/api/verbs?chapter_id={chapter_id}").json() == []

    def test_bestaande_werkwoorden_worden_gefilterd(
        self, client, chapter_id, monkeypatch
    ):
        client.post("/api/verbs", json={
            "chapter_id": chapter_id, "infinitive_es": "Hablar",
            "translation_nl": "praten", "forms": _FORMS,
        })
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {
            "rules": [], "examples": [], "verbs": [
                {"infinitive_es": "hablar", "translation_nl": "praten"},
                {"infinitive_es": "comer", "translation_nl": "eten"},
            ],
        })
        verbs = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        ).json()["verbs"]
        assert verbs == [{"infinitive_es": "comer", "translation_nl": "eten"}]

    def test_dubbel_herkend_werkwoord_telt_een_keer(
        self, client, chapter_id, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {
            "rules": [], "examples": [], "verbs": [
                {"infinitive_es": "hablar", "translation_nl": "praten"},
                {"infinitive_es": " HABLAR ", "translation_nl": "spreken"},
            ],
        })
        verbs = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        ).json()["verbs"]
        assert verbs == [{"infinitive_es": "hablar", "translation_nl": "praten"}]

    def test_alleen_werkwoorden_is_geen_502(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {
            "rules": [], "examples": [],
            "verbs": [{"infinitive_es": "ser", "translation_nl": "zijn"}],
        })
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 200

    def test_prompt_vraagt_om_aangeboden_werkwoorden(
        self, client, chapter_id, monkeypatch
    ):
        aanroepen = []

        def fake(**kwargs):
            aanroepen.append(kwargs)
            return {"rules": [_regel()], "examples": [], "verbs": []}

        monkeypatch.setattr(llm, "complete_json", fake)
        client.post(f"/api/chapters/{chapter_id}/lessons/extract", json=_body())
        systeem = aanroepen[0]["system"].lower()
        assert "werkwoord" in systeem
        assert "infinitief" in systeem
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `.venv/bin/python -m pytest tests/test_api_lessons.py -q`
Expected: `test_geeft_regels_terug_en_slaat_niets_op` en de vijf nieuwe tests FALEN (geen `verbs` in respons / prompt); de rest slaagt.

- [ ] **Step 3: Implementeer de backend-uitbreiding**

In `app/routers/lessons.py`:

1. In `_RULES_SCHEMA`: in `properties` (na `"examples"`) toevoegen en `"required"` uitbreiden:

```python
        "verbs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "infinitive_es": {"type": "string"},
                    "translation_nl": {"type": "string"},
                },
                "required": ["infinitive_es", "translation_nl"],
                "additionalProperties": False,
            },
        },
```

```python
    "required": ["rules", "examples", "verbs"],
```

2. `_EXTRACT_SYSTEM`: de bullet-lijst uitbreiden — na de examples-bullet ("- Elke oefenopgave ...") deze regel toevoegen:

```python
    "- Biedt de pagina expliciet werkwoorden aan — in een woordenlijstje "
    "met vertaling, een vervoegingstabel of duidelijk als nieuwe stof — "
    "dan worden dat werkwoorden (verbs): de infinitief voluit geschreven "
    "(reflexieve werkwoorden mét -se, zoals 'levantarse') met de "
    "Nederlandse vertaling (vertaal zelf als die er niet bij staat). Neem "
    "geen werkwoorden over die alleen in lopende tekst of voorbeeldzinnen "
    "voorkomen.\n"
```

3. Onder `_clean_examples` een nieuwe functie:

```python
def _clean_verbs(data, existing):
    """Werkwoorden uit het LLM-antwoord, zonder lege kanten en zonder
    werkwoorden die al in het hoofdstuk staan (of dubbel herkend zijn)."""
    seen = set(existing)
    verbs = []
    for verb in data.get("verbs", []):
        infinitive = verb["infinitive_es"].strip().lower()
        translation = verb["translation_nl"].strip()
        if infinitive and translation and infinitive not in seen:
            seen.add(infinitive)
            verbs.append(
                {"infinitive_es": infinitive, "translation_nl": translation}
            )
    return verbs
```

4. In `extract_lesson`: de tekst-prompt aanpassen, bestaande werkwoorden ophalen, verbs schoonmaken, guard en respons uitbreiden. De tekstregel wordt:

```python
    content.append({
        "type": "text",
        "text": "Zet de lesstof op deze pagina('s) om naar grammaticaregels, "
                "voorbeeldoefeningen en werkwoorden.",
    })
```

En na `examples = _clean_examples(data)`:

```python
    existing = {
        row["infinitive_es"].strip().lower()
        for row in conn.execute(
            "SELECT infinitive_es FROM verbs WHERE chapter_id = ?", (chapter_id,)
        )
    }
    verbs = _clean_verbs(data, existing)
    if not rules and not examples and not verbs:
        raise HTTPException(
            status_code=502, detail="Geen lesstof herkend in de scan(s)"
        )
    return {"rules": rules, "examples": examples, "verbs": verbs}
```

(De oude `if not rules and not examples:`-guard en `return` vervallen.)

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `.venv/bin/python -m pytest tests/test_api_lessons.py -q`
Expected: alles PASS.

- [ ] **Step 5: Draai de hele suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: alles PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/lessons.py tests/test_api_lessons.py
git commit -m "Les-scan: aangeboden werkwoorden herkennen in extract

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Frontend — werkwoord-kaarten op het nakijkscherm

**Files:**
- Modify: `app/static/js/views/lesson-upload.js`

**Interfaces:**
- Consumes: `POST /api/chapters/{id}/lessons/extract` → `{rules, examples, verbs}` (Task 1); `GET /api/verbs/conjugate?infinitive=...` → `{tense, forms}` of 404/503 (bestaand); `POST /api/verbs` met `{chapter_id, infinitive_es, translation_nl, tense, forms}` waar alle zes vormen verplicht niet-leeg zijn (bestaand); `export const PERSONS = [['yo','yo'], ['tu','tú'], ...]` uit `./verbs-entry.js` (bestaand); helpers `api`, `el`, `saveConcept`, `loadConcept`, `clearConcept` (bestaand in dit bestand).
- Produces: geen — eindpunt van de feature.

Er zijn geen JS-tests per view; verificatie gebeurt in Step 2 via de echte UI.

- [ ] **Step 1: Implementeer de werkwoord-sectie**

Alle wijzigingen in `app/static/js/views/lesson-upload.js`:

1. Import bovenaan uitbreiden:

```js
import {PERSONS} from './verbs-entry.js';
```

2. In `renderUploadStep`: de concept-banner-knop en de extract-callback geven verbs door:

```js
              onclick: () => renderReviewStep(
                concept.data.rules, concept.data.examples, concept.data.verbs || []),
```

```js
      extract: async (images) => {
        const {rules, examples, verbs} = await api(`/api/chapters/${chapterId}/lessons/extract`, {
          method: 'POST', body: {images},
        });
        saveConcept(conceptKey, {rules, examples, verbs});
        renderReviewStep(rules, examples, verbs);
      },
```

3. `renderReviewStep` krijgt een derde parameter:

```js
  function renderReviewStep(rules, examples, verbs) {
```

4. Onder `exampleEditor` een nieuwe editor. Een kaart zonder `forms` in het concept haalt de vormen één keer op; daarna staan ze (ook leeg, na een mislukte lookup) in het concept en wordt er niet opnieuw opgehaald:

```js
    function verbEditor(verb) {
      const infinitiveInput = el('input', {
        type: 'text', value: verb.infinitive_es, autocapitalize: 'off',
        'aria-label': 'Infinitief (Spaans)', 'data-inf': '',
      });
      const translationInput = el('input', {
        type: 'text', value: verb.translation_nl, autocapitalize: 'off',
        'aria-label': 'Vertaling (Nederlands)', 'data-vert': '',
      });
      const formInputs = {};
      for (const [key, label] of PERSONS) {
        formInputs[key] = el('input', {
          type: 'text', value: verb.forms?.[key] || '', autocapitalize: 'off',
          'aria-label': label, placeholder: label,
        });
      }
      const formStatus = el('p', {class: 'muted', style: 'font-size:0.8rem; margin:0.5rem 0 0'});
      const card = el('div', {class: 'card', 'data-verb': ''},
        el('div', {class: 'row'},
          el('label', {class: 'grow'}, 'Werkwoord (presente)'),
          el('button', {
            class: 'icon-btn fixed', type: 'button', title: 'Werkwoord verwijderen',
            onclick: () => card.remove(),
          }, '🗑️'),
        ),
        el('div', {class: 'row'},
          el('div', {}, el('label', {}, 'Infinitief'), infinitiveInput),
          el('div', {}, el('label', {}, 'Vertaling'), translationInput),
        ),
        el('div', {class: 'row', style: 'margin-top:0.75rem'},
          ...PERSONS.slice(0, 3).map(([key, label]) =>
            el('div', {}, el('label', {}, label), formInputs[key])),
        ),
        el('div', {class: 'row', style: 'margin-top:0.75rem'},
          ...PERSONS.slice(3).map(([key, label]) =>
            el('div', {}, el('label', {}, label), formInputs[key])),
        ),
        formStatus,
      );
      card.readVerb = () => ({
        infinitive_es: infinitiveInput.value.trim(),
        translation_nl: translationInput.value.trim(),
        forms: Object.fromEntries(
          PERSONS.map(([key]) => [key, formInputs[key].value.trim()]),
        ),
      });
      card.setStatus = (text) => { formStatus.textContent = text; };
      if (!verb.forms) {
        formStatus.textContent = 'Vervoegingen ophalen…';
        api(`/api/verbs/conjugate?infinitive=${encodeURIComponent(verb.infinitive_es)}`)
          .then((result) => {
            for (const [key] of PERSONS) {
              if (!formInputs[key].value.trim()) formInputs[key].value = result.forms[key];
            }
            formStatus.textContent = 'Vervoegingen opgehaald van Wiktionary — controleer ze even';
            persist();
          })
          .catch((err) => {
            formStatus.textContent = `Vervoegingen niet gevonden (${err.message}) — vul ze zelf in`;
            persist();
          });
      } else if (PERSONS.some(([key]) => !verb.forms[key])) {
        formStatus.textContent = 'Nog niet alle vormen ingevuld';
      }
      return card;
    }

    const verbsEditorsWrap = el('div', {}, ...verbs.map(verbEditor));
```

(Plaats de `const verbsEditorsWrap`-regel direct onder de bestaande `const examplesEditorsWrap`-regel.)

5. `persist` bewaart ook de werkwoorden, en de listeners gelden ook voor de nieuwe sectie:

```js
    function persist() {
      saveConcept(conceptKey, {
        rules: [...editorsWrap.querySelectorAll('[data-rule]')].map((c) => c.readRule()),
        examples: [...examplesEditorsWrap.querySelectorAll('[data-example]')].map((c) => c.readExample()),
        verbs: [...verbsEditorsWrap.querySelectorAll('[data-verb]')].map((c) => c.readVerb()),
      });
    }
```

```js
    verbsEditorsWrap.addEventListener('input', persist);
    verbsEditorsWrap.addEventListener('click', () => setTimeout(persist, 0));
```

6. In de `saveButton`-handler: kaarten lezen, lege-check uitbreiden en na de examples-lus de werkwoorden opslaan. Bovenaan de handler (naast de bestaande reads):

```js
        const verbCards = [...verbsEditorsWrap.querySelectorAll('[data-verb]')];
        const verbPayloads = verbCards.map((card) => card.readVerb());
```

De lege-check wordt:

```js
        if (!rulePayloads.some((rule) => rule.title) && !exampleTexts.some(Boolean)
            && !verbPayloads.some((verb) => verb.infinitive_es)) {
```

Na de examples-`for`-lus, binnen dezelfde `try`:

```js
          let incompleet = 0;
          for (const [i, card] of verbCards.entries()) {
            const verb = verbPayloads[i];
            if (!verb.infinitive_es || !verb.translation_nl
                || PERSONS.some(([key]) => !verb.forms[key])) {
              incompleet += 1;
              card.setStatus('Nog niet compleet — vul infinitief, vertaling en alle zes vormen in');
              continue;
            }
            await api('/api/verbs', {
              method: 'POST',
              body: {chapter_id: chapterId, tense: 'presente', ...verb},
            });
            card.remove();
          }
          if (incompleet) {
            persist();
            saveButton.disabled = false;
            againButton.disabled = false;
            status.textContent = `${incompleet} werkwoord${incompleet === 1 ? ' is' : 'en zijn'} nog niet compleet — aanvullen en opnieuw opslaan.`;
            return;
          }
          clearConcept(conceptKey);
          location.hash = `#/h/${chapterId}`;
```

(De bestaande `clearConcept(...)` en `location.hash = ...` regels vervangen door dit blok.)

7. De teller en de sectie-kop. De teller wordt:

```js
    const teller = [
      rules.length ? `${rules.length} regel${rules.length === 1 ? '' : 's'}` : null,
      examples.length ? `${examples.length} voorbeeldoefening${examples.length === 1 ? '' : 'en'}` : null,
      verbs.length ? `${verbs.length} werkwoord${verbs.length === 1 ? '' : 'en'}` : null,
    ].filter(Boolean).join(' en ');
```

En in de `setChildren(container, ...)`-aanroep, tussen `examplesEditorsWrap` en de knoppen-rij:

```js
      verbs.length ? el('div', {class: 'eyebrow'}, 'Werkwoorden') : null,
      verbsEditorsWrap,
```

- [ ] **Step 2: Verifieer in de echte UI**

Gebruik de projectskill `verify` (testinstantie op poort 8765, wachtwoord `verifytest`). De extract-stap heeft een LLM-key nodig; omzeil die door het concept direct te zaaien. Met playwright, na inloggen en het aanmaken van een hoofdstuk (id 1):

1. Zet via `page.evaluate` een concept in localStorage:
   `localStorage.setItem('spaans-les-concept-1', JSON.stringify({at: '2026-08-02T12:00:00Z', data: {rules: [], examples: [], verbs: [{infinitive_es: 'hablar', translation_nl: 'praten'}]}}))`
2. Navigeer naar `#/h/1/les-uploaden` (route bevestigd in `app/static/js/app.js:29`) en klik "✏️ Verdergaan met nakijken".
3. Controleer: een kaart "Werkwoord (presente)" met infinitief "hablar"; na even wachten zijn de zes vormvelden gevuld via Wiktionary (yo = "hablo") en meldt de kaart "Vervoegingen opgehaald…".
4. Klik "💾 Alles opslaan"; controleer dat je op het hoofdstukscherm belandt en dat `GET /api/verbs?chapter_id=1` één werkwoord "hablar" met complete presente-vormen bevat.
5. Incompleet-pad: zaai nogmaals een concept met een werkwoord waarvan Wiktionary niets weet (bijv. `infinitive_es: 'xyzzyar'`), open het nakijkscherm, wacht op de foutmelding op de kaart, klik opslaan en controleer dat de kaart blijft staan met de melding "Nog niet compleet …" en de statusregel "1 werkwoord is nog niet compleet …".

Stop daarna de testinstantie (pkill in een los commando, patroon `'[u]vicorn.*8765'`, zonder die tekenreeks elders op de regel).

- [ ] **Step 3: Draai de JS-tests (regressie)**

Run: `node --test 'tests/js/*.mjs'`
Expected: alles PASS.

- [ ] **Step 4: Commit**

```bash
git add app/static/js/views/lesson-upload.js
git commit -m "Les-scan: herkende werkwoorden nakijken en opslaan

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
