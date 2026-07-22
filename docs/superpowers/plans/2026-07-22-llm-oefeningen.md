# Fase 1: LLM-laag en oefeninggeneratie — Implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per hoofdstuk grammatica-oefeningen laten genereren door de Claude API en die oefenen in een nieuwe oefenmodus, inclusief LLM-beoordeling van vertaalzinnen en wegstemmen van slechte oefeningen.

**Architecture:** Eén LLM-module (`app/llm.py`, enige plek die `anthropic` importeert) met gestructureerde JSON-output. Een nieuwe `exercises`-tabel + router voor genereren, oefenen en wegstemmen. Frontend volgt de bestaande patronen: hash-route, view-module, `queue.js`-wachtrij.

**Tech Stack:** FastAPI, SQLite (geen ORM, migraties in `app/migrations/`), `anthropic`-SDK, vanilla-JS zonder build-stap, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-llm-oefeningen-scans-conversatie-design.md`

## Global Constraints

- Nederlands in alle UI-teksten, commit-messages, docstrings en foutmeldingen (bestaande stijl).
- Commit-messages in de stijl `Onderwerp: beschrijving` (zie `git log`), afgesloten met:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` en de Claude-Session-regel van de sessie.
- Niets buiten `app/llm.py` importeert `anthropic`.
- Tests draaien nooit tegen de echte API: mock met `monkeypatch` (bestaande stijl, zie `tests/test_conjugate.py`).
- Default model: `claude-opus-4-8`, instelbaar via `LLM_MODEL` in `.env`; key via `ANTHROPIC_API_KEY`.
- Volledige testsuite groen na elke taak: `python -m pytest -q` en `node --test tests/js/`.

## Afwijkingen van de spec (worden in Taak 8 in de spec bijgewerkt)

1. Het aparte `POST /api/exercises/{id}/judge`-endpoint vervalt: de LLM-beoordeling van vertaalzinnen zit ín `POST /api/exercises/{id}/check`, anders wordt de statistiek dubbel bijgewerkt (check registreert "fout", judge zou daarna "goed" zeggen).
2. Generatie-endpoint is `POST /api/exercises/generate` met `chapter_id` in de body (consistent met hoe `words`/`verbs`-routers werken), niet `POST /api/chapters/{id}/exercises/generate`.
3. `complete_json` heeft geen aparte `images`-parameter; afbeeldingen gaan in fase 2 als content-blocks in `messages` mee.

---

### Taak 1: Migratie `002_exercises.sql`

**Files:**
- Create: `app/migrations/002_exercises.sql`
- Test: `tests/test_api_exercises.py` (nieuw bestand, eerste test)

**Interfaces:**
- Produces: tabel `exercises` met kolommen `id, chapter_id, type, instruction, prompt, answer, options, explanation, disabled, created_at` (zie SQL hieronder). Latere taken schrijven/lezen deze tabel.

- [ ] **Stap 1: Schrijf de falende test**

Maak `tests/test_api_exercises.py`:

```python
import sqlite3

import pytest


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def _insert_exercise(app_instance, chapter_id, **overrides):
    """Testhelper: oefening direct in de database zetten."""
    from app import db

    values = {
        "chapter_id": chapter_id,
        "type": "invullen",
        "instruction": "Vul de juiste vorm van 'ser' in",
        "prompt": "Yo ___ de Países Bajos.",
        "answer": "soy",
        "options": None,
        "explanation": "Bij 'yo' hoort 'soy'.",
    }
    values.update(overrides)
    conn = db.connect(app_instance.state.db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO exercises (chapter_id, type, instruction, prompt, answer, "
            "options, explanation) VALUES (:chapter_id, :type, :instruction, "
            ":prompt, :answer, :options, :explanation)",
            values,
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


class TestMigratie:
    def test_exercises_tabel_bestaat(self, app_instance, chapter_id):
        exercise_id = _insert_exercise(app_instance, chapter_id)
        assert exercise_id > 0

    def test_onbekend_type_wordt_geweigerd(self, app_instance, chapter_id):
        with pytest.raises(sqlite3.IntegrityError):
            _insert_exercise(app_instance, chapter_id, type="raden")

    def test_verwijderen_hoofdstuk_verwijdert_oefeningen(
        self, client, app_instance, chapter_id
    ):
        from app import db

        _insert_exercise(app_instance, chapter_id)
        client.delete(f"/api/chapters/{chapter_id}")
        conn = db.connect(app_instance.state.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) AS n FROM exercises").fetchone()["n"]
        finally:
            conn.close()
        assert count == 0
```

Let op: `chapter_id`-fixture gebruikt `client` (ingelogd) uit `tests/conftest.py`; `app_instance` komt daar ook vandaan.

- [ ] **Stap 2: Draai de test en zie hem falen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: 3× FAIL/ERROR met `sqlite3.OperationalError: no such table: exercises`.

- [ ] **Stap 3: Schrijf de migratie**

Maak `app/migrations/002_exercises.sql`:

```sql
CREATE TABLE exercises (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('invullen','vertalen','meerkeuze','herschrijven')),
    instruction TEXT NOT NULL,
    prompt TEXT NOT NULL,
    answer TEXT NOT NULL,
    options TEXT,
    explanation TEXT NOT NULL DEFAULT '',
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Geen wijziging aan `app/db.py` nodig: `migrate()` pakt alle `*.sql`-bestanden op volgorde op.

- [ ] **Stap 4: Draai de test en zie hem slagen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: 3 passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `python -m pytest -q` → alles groen.

```bash
git add app/migrations/002_exercises.sql tests/test_api_exercises.py
git commit -m "Oefeningen: exercises-tabel (migratie 002)"
```

---

### Taak 2: LLM-laag `app/llm.py`

**Files:**
- Create: `app/llm.py`
- Modify: `requirements.txt` (regel `anthropic` toevoegen)
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `llm.complete_json(system: str, messages: list[dict], schema: dict, max_tokens: int = 16000) -> dict` — roept Claude aan met gestructureerde output en geeft de geparste JSON terug.
  - `llm.LLMError(Exception)` — foutmelding in het Nederlands, geschikt om direct aan de gebruiker te tonen.
  - `llm.DEFAULT_MODEL = "claude-opus-4-8"`.

- [ ] **Stap 1: Voeg de dependency toe en installeer**

Voeg in `requirements.txt` een regel `anthropic` toe (alfabetisch hoeft niet; zet hem na `fastapi`).

Run: `pip install -r requirements-dev.txt`
Verwacht: `anthropic` wordt geïnstalleerd zonder fouten.

- [ ] **Stap 2: Schrijf de falende tests**

Maak `tests/test_llm.py`:

```python
from types import SimpleNamespace

import pytest

from app import llm


def _fake_client(monkeypatch, *, text='{"ok": true}', stop_reason="end_turn"):
    """Vervang de echte Anthropic-client door een nep-client."""
    response = SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
    )
    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return response

    monkeypatch.setattr(
        llm, "_client", lambda: SimpleNamespace(messages=FakeMessages())
    )
    return calls


SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}


def test_complete_json_parst_de_json(monkeypatch):
    _fake_client(monkeypatch, text='{"correct": true, "feedback": ""}')
    result = llm.complete_json("systeem", [{"role": "user", "content": "hoi"}], SCHEMA)
    assert result == {"correct": True, "feedback": ""}


def test_complete_json_stuurt_schema_en_model_mee(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-4-5")
    llm.complete_json("systeem", [{"role": "user", "content": "hoi"}], SCHEMA)
    assert calls[0]["model"] == "claude-haiku-4-5"
    assert calls[0]["output_config"] == {
        "format": {"type": "json_schema", "schema": SCHEMA}
    }
    assert calls[0]["system"] == "systeem"


def test_default_model(monkeypatch):
    calls = _fake_client(monkeypatch)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)
    assert calls[0]["model"] == llm.DEFAULT_MODEL


def test_ontbrekende_api_key_geeft_llmerror(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.LLMError):
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)


def test_onbruikbare_json_geeft_llmerror(monkeypatch):
    _fake_client(monkeypatch, text="dit is geen json")
    with pytest.raises(llm.LLMError):
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)


def test_weigering_geeft_llmerror(monkeypatch):
    _fake_client(monkeypatch, stop_reason="refusal")
    with pytest.raises(llm.LLMError):
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)


def test_api_fout_geeft_nederlandse_llmerror(monkeypatch):
    import anthropic

    class FakeMessages:
        def create(self, **kwargs):
            raise anthropic.APIConnectionError(request=None)

    monkeypatch.setattr(
        llm, "_client", lambda: SimpleNamespace(messages=FakeMessages())
    )
    with pytest.raises(llm.LLMError) as excinfo:
        llm.complete_json("s", [{"role": "user", "content": "x"}], SCHEMA)
    assert "verbinding" in str(excinfo.value).lower()
```

- [ ] **Stap 3: Draai de tests en zie ze falen**

Run: `python -m pytest tests/test_llm.py -q`
Verwacht: ERROR — `ModuleNotFoundError: No module named 'app.llm'` (of ImportError).

- [ ] **Stap 4: Schrijf `app/llm.py`**

```python
"""Uitwisselbaar laagje rond de Claude API.

Dit is de enige module die `anthropic` importeert; de rest van de app
kent alleen `complete_json` en `LLMError`. Model instelbaar via
LLM_MODEL in .env (default claude-opus-4-8), key via ANTHROPIC_API_KEY.
"""

import json
import os

import anthropic

DEFAULT_MODEL = "claude-opus-4-8"


class LLMError(Exception):
    """Nederlandse foutmelding die direct aan de gebruiker getoond kan worden."""


def _client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMError("ANTHROPIC_API_KEY ontbreekt in .env")
    return anthropic.Anthropic()


def complete_json(system, messages, schema, max_tokens=16000):
    """Vraag Claude om JSON volgens `schema` en geef die geparst terug."""
    try:
        response = _client().messages.create(
            model=os.environ.get("LLM_MODEL", DEFAULT_MODEL),
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.AuthenticationError as exc:
        raise LLMError("De API-sleutel is ongeldig") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError(
            "De taaldienst is even overbelast; probeer het zo opnieuw"
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("Geen verbinding met de taaldienst") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError("De taaldienst gaf een fout terug") from exc
    if response.stop_reason == "refusal":
        raise LLMError("De taaldienst weigerde dit verzoek")
    text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )
    try:
        return json.loads(text)
    except ValueError as exc:
        raise LLMError("Onbruikbaar antwoord van de taaldienst") from exc
```

Let op de foutvolgorde: `RateLimitError` en `AuthenticationError` zijn subklassen van `APIStatusError`, dus die moeten éérst gevangen worden. `_client()` staat apart zodat tests hem kunnen vervangen met `monkeypatch`.

- [ ] **Stap 5: Draai de tests en zie ze slagen**

Run: `python -m pytest tests/test_llm.py -q`
Verwacht: 7 passed. (Faalt `test_api_fout_geeft_nederlandse_llmerror` op de constructor van `APIConnectionError`, gebruik dan `anthropic.APIConnectionError(request=SimpleNamespace())`.)

- [ ] **Stap 6: Volledige suite + commit**

Run: `python -m pytest -q` → alles groen.

```bash
git add app/llm.py requirements.txt tests/test_llm.py
git commit -m "LLM-laag: complete_json rond de Claude API, model instelbaar via .env"
```

---

### Taak 3: Exercises-router — lijst en wegstemmen

**Files:**
- Create: `app/routers/exercises.py`
- Modify: `app/main.py:11` (import) en `app/main.py:57` (include_router)
- Test: `tests/test_api_exercises.py` (uitbreiden)

**Interfaces:**
- Consumes: tabel `exercises` (Taak 1), `_insert_exercise`-testhelper (Taak 1).
- Produces:
  - `GET /api/exercises?chapter_id=N` → lijst van niet-weggestemde oefeningen: `{id, chapter_id, type, instruction, prompt, answer, options (lijst of null), explanation}`.
  - `POST /api/exercises/{id}/disable` → 204, zet `disabled=1`; 404 als onbekend.
  - Router-object `router` met prefix `/api/exercises` (Taak 4 en 5 voegen endpoints toe aan ditzelfde bestand).

- [ ] **Stap 1: Schrijf de falende tests**

Voeg toe aan `tests/test_api_exercises.py`:

```python
class TestLijst:
    def test_lijst_geeft_oefeningen_met_geparste_options(
        self, client, app_instance, chapter_id
    ):
        _insert_exercise(
            app_instance, chapter_id,
            type="meerkeuze", options='["soy", "eres", "es"]',
        )
        exercises = client.get(f"/api/exercises?chapter_id={chapter_id}").json()
        assert len(exercises) == 1
        assert exercises[0]["options"] == ["soy", "eres", "es"]
        assert exercises[0]["prompt"] == "Yo ___ de Países Bajos."

    def test_options_null_zonder_meerkeuze(self, client, app_instance, chapter_id):
        _insert_exercise(app_instance, chapter_id)
        exercises = client.get(f"/api/exercises?chapter_id={chapter_id}").json()
        assert exercises[0]["options"] is None

    def test_weggestemde_oefening_staat_niet_in_de_lijst(
        self, client, app_instance, chapter_id
    ):
        exercise_id = _insert_exercise(app_instance, chapter_id)
        assert client.post(f"/api/exercises/{exercise_id}/disable").status_code == 204
        assert client.get(f"/api/exercises?chapter_id={chapter_id}").json() == []

    def test_wegstemmen_onbekende_oefening_is_404(self, client):
        assert client.post("/api/exercises/999/disable").status_code == 404
```

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: de nieuwe tests falen met 404 (route bestaat niet).

- [ ] **Stap 3: Schrijf de router en registreer hem**

Maak `app/routers/exercises.py`:

```python
import json

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_conn

router = APIRouter(prefix="/api/exercises")


@router.get("")
def list_exercises(chapter_id: int, conn=Depends(get_conn)):
    rows = conn.execute(
        "SELECT id, chapter_id, type, instruction, prompt, answer, options, "
        "explanation FROM exercises WHERE chapter_id = ? AND disabled = 0 "
        "ORDER BY id",
        (chapter_id,),
    ).fetchall()
    return [
        dict(row, options=json.loads(row["options"]) if row["options"] else None)
        for row in rows
    ]


@router.post("/{exercise_id}/disable", status_code=204)
def disable_exercise(exercise_id: int, conn=Depends(get_conn)):
    cursor = conn.execute(
        "UPDATE exercises SET disabled = 1 WHERE id = ?", (exercise_id,)
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Oefening niet gevonden")
```

In `app/main.py` regel 11 wordt:

```python
from app.routers import chapters, exercises, grammar, practice, verbs, words
```

en na `app.include_router(practice.router)`:

```python
app.include_router(exercises.router)
```

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: alles passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `python -m pytest -q` → alles groen.

```bash
git add app/routers/exercises.py app/main.py tests/test_api_exercises.py
git commit -m "Oefeningen: lijst-endpoint en wegstemmen"
```

---

### Taak 4: Check-endpoint met LLM-oordeel voor vertaalzinnen

**Files:**
- Modify: `app/routers/exercises.py`
- Test: `tests/test_api_exercises.py` (uitbreiden)

**Interfaces:**
- Consumes: `check_answer` uit `app/checking.py` (`CheckResult` met velden `result`, `correct_answer`, `matched`), `llm.complete_json` + `llm.LLMError` (Taak 2).
- Produces: `POST /api/exercises/{id}/check` met body `{"answer": str}` →
  `{"result": "correct"|"correct_accent"|"wrong", "correct_answer": str, "explanation": str, "feedback": str}`.
  `feedback` is de LLM-feedback bij vertaalzinnen (anders leeg). Statistieken gaan naar `practice_stats` met `item_type='exercise'`, `direction=<type>`.

- [ ] **Stap 1: Schrijf de falende tests**

Voeg toe aan `tests/test_api_exercises.py` (bovenaan `from app import db, llm` toevoegen aan de imports):

```python
def _stats(app_instance):
    conn = db.connect(app_instance.state.db_path)
    try:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT item_type, item_id, direction, correct, wrong "
                "FROM practice_stats"
            )
        ]
    finally:
        conn.close()


class TestCheck:
    def test_goed_antwoord(self, client, app_instance, chapter_id):
        exercise_id = _insert_exercise(app_instance, chapter_id, answer="soy")
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "soy"}
        ).json()
        assert result["result"] == "correct"
        assert result["explanation"] == "Bij 'yo' hoort 'soy'."

    def test_accentfout_blijft_soepel(self, client, app_instance, chapter_id):
        exercise_id = _insert_exercise(app_instance, chapter_id, answer="está")
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "esta"}
        ).json()
        assert result["result"] == "correct_accent"

    def test_fout_antwoord_update_statistiek(self, client, app_instance, chapter_id):
        exercise_id = _insert_exercise(app_instance, chapter_id, answer="soy")
        client.post(f"/api/exercises/{exercise_id}/check", json={"answer": "eres"})
        stats = _stats(app_instance)
        assert stats == [
            {
                "item_type": "exercise",
                "item_id": exercise_id,
                "direction": "invullen",
                "correct": 0,
                "wrong": 1,
            }
        ]

    def test_onbekende_oefening_is_404(self, client):
        assert (
            client.post("/api/exercises/999/check", json={"answer": "x"}).status_code
            == 404
        )


class TestVertalenMetLLM:
    def _vertaling(self, app_instance, chapter_id):
        return _insert_exercise(
            app_instance, chapter_id,
            type="vertalen",
            instruction="Vertaal naar het Spaans",
            prompt="Ik ben moe.",
            answer="Estoy cansado",
        )

    def test_llm_keurt_alternatieve_vertaling_goed(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)
        monkeypatch.setattr(
            llm, "complete_json",
            lambda **kwargs: {"correct": True, "feedback": ""},
        )
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Estoy cansada"}
        ).json()
        assert result["result"] == "correct"
        assert _stats(app_instance)[0]["correct"] == 1

    def test_llm_afkeuring_geeft_feedback(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)
        monkeypatch.setattr(
            llm, "complete_json",
            lambda **kwargs: {"correct": False, "feedback": "Gebruik 'estar' bij een tijdelijke toestand."},
        )
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Soy cansado"}
        ).json()
        assert result["result"] == "wrong"
        assert "estar" in result["feedback"]

    def test_lokaal_goed_antwoord_slaat_llm_over(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)

        def boom(**kwargs):
            raise AssertionError("LLM hoort niet aangeroepen te worden")

        monkeypatch.setattr(llm, "complete_json", boom)
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Estoy cansado"}
        ).json()
        assert result["result"] == "correct"

    def test_llm_storing_valt_terug_op_lokale_check(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)

        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Estoy cansada"}
        ).json()
        assert result["result"] == "wrong"
        assert result["feedback"] == ""

    def test_leeg_antwoord_gaat_niet_naar_de_llm(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)

        def boom(**kwargs):
            raise AssertionError("LLM hoort niet aangeroepen te worden")

        monkeypatch.setattr(llm, "complete_json", boom)
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": ""}
        ).json()
        assert result["result"] == "wrong"
```

Let op: de router gebruikt `from app import llm` en roept `llm.complete_json(...)` aan als attribuut, zodat `monkeypatch.setattr(llm, "complete_json", ...)` werkt.

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: nieuwe tests falen met 404 (endpoint bestaat niet).

- [ ] **Stap 3: Implementeer het check-endpoint**

Voeg toe aan `app/routers/exercises.py` (imports uitbreiden):

```python
from pydantic import BaseModel

from app import llm
from app.checking import CheckResult, check_answer
```

en onder de bestaande endpoints:

```python
class ExerciseCheck(BaseModel):
    answer: str


_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "feedback": {"type": "string"},
    },
    "required": ["correct", "feedback"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = (
    "Je beoordeelt of een leerling een Nederlandse zin correct naar het Spaans "
    "heeft vertaald. Meerdere vertalingen kunnen goed zijn; keur goed als de "
    "vertaling grammaticaal correct is en de betekenis overbrengt. Accentfouten "
    "zijn geen reden voor afkeuring. Geef bij een afkeuring in 'feedback' één "
    "korte Nederlandse zin die uitlegt wat er mis is; anders een lege string."
)


def _judge_translation(exercise, answer):
    """LLM-oordeel over een vertaling; None bij storing (dan telt de lokale check)."""
    try:
        return llm.complete_json(
            system=_JUDGE_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"Nederlandse zin: {exercise['prompt']}\n"
                    f"Voorbeeldvertaling: {exercise['answer']}\n"
                    f"Antwoord van de leerling: {answer}"
                ),
            }],
            schema=_JUDGE_SCHEMA,
            max_tokens=1000,
        )
    except llm.LLMError:
        return None


def _update_stats(conn, exercise_id, exercise_type, is_correct):
    conn.execute(
        """
        INSERT INTO practice_stats
            (item_type, item_id, direction, correct, wrong, last_practiced_at)
        VALUES ('exercise', ?, ?, ?, ?, datetime('now'))
        ON CONFLICT (item_type, item_id, direction) DO UPDATE SET
            correct = correct + excluded.correct,
            wrong = wrong + excluded.wrong,
            last_practiced_at = excluded.last_practiced_at
        """,
        (exercise_id, exercise_type, 1 if is_correct else 0, 0 if is_correct else 1),
    )
    conn.commit()


@router.post("/{exercise_id}/check")
def check_exercise(exercise_id: int, body: ExerciseCheck, conn=Depends(get_conn)):
    exercise = conn.execute(
        "SELECT id, type, prompt, answer, explanation FROM exercises WHERE id = ?",
        (exercise_id,),
    ).fetchone()
    if exercise is None:
        raise HTTPException(status_code=404, detail="Oefening niet gevonden")

    result = check_answer(exercise["answer"], body.answer)
    feedback = ""
    # Bij vertalen kunnen meerdere antwoorden goed zijn: alleen als de lokale
    # check "fout" zegt, mag de LLM het eindoordeel geven.
    if (
        result.result == "wrong"
        and exercise["type"] == "vertalen"
        and body.answer.strip()
    ):
        verdict = _judge_translation(exercise, body.answer)
        if verdict is not None:
            if verdict["correct"]:
                result = CheckResult("correct", result.correct_answer, body.answer)
            else:
                feedback = verdict["feedback"]

    _update_stats(conn, exercise_id, exercise["type"], result.result != "wrong")
    return {
        "result": result.result,
        "correct_answer": result.correct_answer,
        "explanation": exercise["explanation"],
        "feedback": feedback,
    }
```

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: alles passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `python -m pytest -q` → alles groen.

```bash
git add app/routers/exercises.py tests/test_api_exercises.py
git commit -m "Oefeningen: check-endpoint, LLM beoordeelt afgekeurde vertalingen"
```

---

### Taak 5: Generatie-endpoint

**Files:**
- Modify: `app/routers/exercises.py`
- Test: `tests/test_api_exercises.py` (uitbreiden)

**Interfaces:**
- Consumes: `llm.complete_json`/`llm.LLMError` (Taak 2); `list_rules` uit `app/routers/grammar.py` (signatuur `list_rules(chapter_id, conn)`), `list_words` uit `app/routers/words.py`, `list_verbs` uit `app/routers/verbs.py`; `chapter_or_404` uit `app/deps.py`.
- Produces: `POST /api/exercises/generate` met body `{"chapter_id": N}` → `{"created": aantal}`. Fouten: 404 onbekend hoofdstuk, 400 hoofdstuk zonder grammatica, 503 LLM-storing (detail = Nederlandse melding), 502 geen bruikbare oefeningen.

- [ ] **Stap 1: Schrijf de falende tests**

Voeg toe aan `tests/test_api_exercises.py`:

```python
@pytest.fixture
def chapter_met_lesstof(client, chapter_id):
    client.post("/api/grammar", json={
        "chapter_id": chapter_id,
        "title": "Ser en estar",
        "explanation": "Ser voor blijvend, estar voor tijdelijk.",
        "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
    })
    client.post("/api/words", json={
        "chapter_id": chapter_id, "spanish": "cansado", "dutch": "moe",
    })
    return chapter_id


def _gegenereerde_oefening(**overrides):
    exercise = {
        "type": "invullen",
        "instruction": "Vul de juiste vorm van 'estar' in",
        "prompt": "Yo ___ cansado.",
        "answer": "estoy",
        "options": [],
        "explanation": "Tijdelijke toestand: estar.",
    }
    exercise.update(overrides)
    return exercise


class TestGenereren:
    def test_genereert_en_slaat_op(
        self, client, app_instance, chapter_met_lesstof, monkeypatch
    ):
        prompts = []

        def fake(**kwargs):
            prompts.append(kwargs)
            return {"exercises": [
                _gegenereerde_oefening(),
                _gegenereerde_oefening(
                    type="meerkeuze", options=["estoy", "soy"], answer="estoy",
                ),
            ]}

        monkeypatch.setattr(llm, "complete_json", fake)
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.status_code == 200
        assert response.json() == {"created": 2}
        exercises = client.get(
            f"/api/exercises?chapter_id={chapter_met_lesstof}"
        ).json()
        assert len(exercises) == 2
        assert exercises[1]["options"] == ["estoy", "soy"]
        # De lesstof staat in de prompt naar de LLM
        content = prompts[0]["messages"][0]["content"]
        assert "Ser en estar" in content
        assert "cansado" in content

    def test_ongeldige_meerkeuze_wordt_overgeslagen(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"exercises": [
            _gegenereerde_oefening(),
            _gegenereerde_oefening(
                type="meerkeuze", options=["soy"], answer="estoy",
            ),
        ]})
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.json() == {"created": 1}

    def test_hoofdstuk_zonder_grammatica_is_400(self, client, chapter_id):
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_id}
        )
        assert response.status_code == 400

    def test_onbekend_hoofdstuk_is_404(self, client):
        assert (
            client.post(
                "/api/exercises/generate", json={"chapter_id": 999}
            ).status_code
            == 404
        )

    def test_llm_storing_is_503_met_nederlandse_melding(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Geen verbinding met de taaldienst"

    def test_geen_bruikbare_oefeningen_is_502(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        monkeypatch.setattr(
            llm, "complete_json", lambda **kwargs: {"exercises": []}
        )
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.status_code == 502
```

- [ ] **Stap 2: Draai de tests en zie ze falen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: nieuwe tests falen met 404 (endpoint bestaat niet).

- [ ] **Stap 3: Implementeer het generatie-endpoint**

Voeg toe aan `app/routers/exercises.py` (imports uitbreiden):

```python
from app.deps import chapter_or_404, get_conn  # chapter_or_404 erbij
from app.routers.grammar import list_rules
from app.routers.verbs import list_verbs
from app.routers.words import list_words
```

en de implementatie:

```python
GENERATION_COUNT = 12

_EXERCISES_SCHEMA = {
    "type": "object",
    "properties": {
        "exercises": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["invullen", "vertalen", "meerkeuze", "herschrijven"],
                    },
                    "instruction": {"type": "string"},
                    "prompt": {"type": "string"},
                    "answer": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                },
                "required": [
                    "type", "instruction", "prompt",
                    "answer", "options", "explanation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["exercises"],
    "additionalProperties": False,
}

_GENERATE_SYSTEM = (
    "Je maakt Spaanse grammatica-oefeningen voor een Nederlandstalige beginner. "
    "Baseer elke oefening op de gegeven grammaticaregels en gebruik zoveel "
    "mogelijk de gegeven woordenschat. Vier typen:\n"
    "- invullen: prompt is een Spaanse zin met precies één gat, geschreven als "
    "drie underscores (___); answer is wat er in het gat hoort.\n"
    "- vertalen: prompt is een Nederlandse zin; answer is de Spaanse vertaling. "
    "Meerdere goede vertalingen scheid je met ';'.\n"
    "- meerkeuze: prompt is een Spaanse zin met een gat (___); options bevat 3 "
    "of 4 mogelijkheden waarvan er precies één juist is; answer is exact de "
    "juiste optie.\n"
    "- herschrijven: instruction zegt hoe de zin moet worden omgezet (bijv. "
    "naar meervoud of een andere persoon); prompt is de bronzin; answer de "
    "omgezette zin.\n"
    "instruction is altijd een korte Nederlandse opdracht. explanation is één "
    "korte Nederlandse zin die de regel achter het antwoord uitlegt. options "
    "is bij andere typen dan meerkeuze een lege lijst. Houd de zinnen kort en "
    "op beginnersniveau."
)


class GenerateRequest(BaseModel):
    chapter_id: int


def _lesson_context(conn, chapter_id):
    parts = ["Grammaticaregels:"]
    for rule in list_rules(chapter_id, conn):
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


def _valid_exercise(item):
    if not item["prompt"].strip() or not item["answer"].strip():
        return False
    if item["type"] == "meerkeuze":
        options = [o.strip() for o in item["options"] if o.strip()]
        return len(options) >= 2 and item["answer"].strip() in options
    return True


@router.post("/generate")
def generate_exercises(body: GenerateRequest, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    if not list_rules(body.chapter_id, conn):
        raise HTTPException(
            status_code=400,
            detail="Dit hoofdstuk heeft nog geen grammatica om oefeningen op te baseren",
        )
    context = _lesson_context(conn, body.chapter_id)
    try:
        data = llm.complete_json(
            system=_GENERATE_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"{context}\n\nMaak {GENERATION_COUNT} oefeningen, "
                    "gemengd over de vier typen."
                ),
            }],
            schema=_EXERCISES_SCHEMA,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    created = 0
    for item in data.get("exercises", []):
        if not _valid_exercise(item):
            continue
        conn.execute(
            "INSERT INTO exercises (chapter_id, type, instruction, prompt, "
            "answer, options, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                body.chapter_id,
                item["type"],
                item["instruction"].strip(),
                item["prompt"].strip(),
                item["answer"].strip(),
                json.dumps(item["options"], ensure_ascii=False)
                if item["type"] == "meerkeuze" else None,
                item["explanation"].strip(),
            ),
        )
        created += 1
    conn.commit()
    if created == 0:
        raise HTTPException(
            status_code=502, detail="De taaldienst gaf geen bruikbare oefeningen"
        )
    return {"created": created}
```

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `python -m pytest tests/test_api_exercises.py -q`
Verwacht: alles passed.

- [ ] **Stap 5: Volledige suite + commit**

Run: `python -m pytest -q` → alles groen.

```bash
git add app/routers/exercises.py tests/test_api_exercises.py
git commit -m "Oefeningen: genereren per hoofdstuk op basis van de lesstof"
```

---

### Taak 6: Hoofdstukscherm — teller en genereerknop

**Files:**
- Modify: `app/routers/chapters.py:14-25` (`list_chapters`-query)
- Modify: `app/static/js/views/chapter.js` (nieuwe kaart "Oefeningen")
- Test: `tests/test_api_chapters.py` (uitbreiden)

**Interfaces:**
- Consumes: `POST /api/exercises/generate` (Taak 5), tabel `exercises`.
- Produces: `GET /api/chapters` bevat per hoofdstuk `exercise_count` (aantal niet-weggestemde oefeningen). Route `#/h/{id}/oefen/oefeningen` wordt in Taak 7 aangesloten.

- [ ] **Stap 1: Schrijf de falende backend-test**

Voeg toe aan `tests/test_api_chapters.py`:

```python
def test_chapter_telt_alleen_actieve_oefeningen(client, app_instance):
    from app import db

    chapter_id = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
    conn = db.connect(app_instance.state.db_path)
    try:
        for _ in range(2):
            cursor = conn.execute(
                "INSERT INTO exercises (chapter_id, type, instruction, prompt, "
                "answer) VALUES (?, 'invullen', 'Vul in', 'Yo ___.', 'soy')",
                (chapter_id,),
            )
        conn.commit()
        weggestemd = cursor.lastrowid
    finally:
        conn.close()
    client.post(f"/api/exercises/{weggestemd}/disable")
    chapter = client.get("/api/chapters").json()[0]
    assert chapter["exercise_count"] == 1
```

- [ ] **Stap 2: Draai de test en zie hem falen**

Run: `python -m pytest tests/test_api_chapters.py -q`
Verwacht: FAIL met `KeyError: 'exercise_count'`.

- [ ] **Stap 3: Breid de query uit**

In `app/routers/chapters.py` in `list_chapters` een subselect toevoegen na de `grammar_count`-regel:

```sql
(SELECT COUNT(*) FROM grammar_rules g WHERE g.chapter_id = c.id) AS grammar_count,
(SELECT COUNT(*) FROM exercises e WHERE e.chapter_id = c.id AND e.disabled = 0) AS exercise_count
```

- [ ] **Stap 4: Draai de tests en zie ze slagen**

Run: `python -m pytest tests/test_api_chapters.py -q` → alles passed.

- [ ] **Stap 5: Voeg de kaart toe aan het hoofdstukscherm**

In `app/static/js/views/chapter.js`, binnen `renderChapterHub`, vóór de `setChildren(view, ...)`-aanroep dit blok toevoegen:

```js
const generateStatus = el('p', {class: 'muted', style: 'margin-top:0.5rem'});
const generateButton = el('button', {
  onclick: async () => {
    generateButton.disabled = true;
    generateStatus.textContent = 'Bezig met genereren… dit kan een minuut duren.';
    try {
      const {created} = await api('/api/exercises/generate', {
        method: 'POST',
        body: {chapter_id: chapterId},
      });
      generateStatus.textContent = `${created} oefeningen toegevoegd.`;
      await renderChapterHub(view, chapterId);
    } catch (err) {
      generateButton.disabled = false;
      generateStatus.textContent = `Genereren mislukte: ${err.message}`;
    }
  },
}, '✨ Genereer oefeningen');
```

en in de `setChildren(view, ...)`-lijst, ná de kaart "Grammatica", deze kaart:

```js
el(
  'div',
  {class: 'card'},
  el('h2', {}, 'Oefeningen'),
  el('p', {class: 'muted'},
    chapter.exercise_count
      ? `${chapter.exercise_count} oefeningen op basis van de lesstof van dit hoofdstuk.`
      : 'Nog geen oefeningen — genereer ze op basis van de grammatica van dit hoofdstuk.'),
  el('div', {class: 'row'},
    chapter.exercise_count
      ? el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/oefen/oefeningen`}, '⌨️ Oefenen')
      : null,
    generateButton,
  ),
  generateStatus,
),
```

- [ ] **Stap 6: Volledige suite + commit**

Run: `python -m pytest -q` en `node --test tests/js/` → alles groen.

```bash
git add app/routers/chapters.py app/static/js/views/chapter.js tests/test_api_chapters.py
git commit -m "Hoofdstukscherm: oefeningen-kaart met teller en genereerknop"
```

---

### Taak 7: Oefenview

**Files:**
- Create: `app/static/js/views/practice-exercises.js`
- Modify: `app/static/js/app.js:9-31` (import + route)

**Interfaces:**
- Consumes: `GET /api/exercises?chapter_id=`, `POST /api/exercises/{id}/check`, `POST /api/exercises/{id}/disable` (Taken 3-4); `api`, `el`, `setChildren` uit `api.js`; `createQueue`, `shuffle` uit `queue.js`.
- Produces: route `#/h/{id}/oefen/oefeningen` → `renderPracticeExercises(view, chapterId)`.

- [ ] **Stap 1: Schrijf de view**

Maak `app/static/js/views/practice-exercises.js`:

```js
import {api, el, setChildren} from '../api.js';
import {createQueue, shuffle} from '../queue.js';

export async function renderPracticeExercises(view, chapterId) {
  const exercises = await api(`/api/exercises?chapter_id=${chapterId}`);
  const backLink = el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, '← Hoofdstuk'));

  if (!exercises.length) {
    setChildren(view, backLink,
      el('p', {class: 'muted'},
        'Dit hoofdstuk heeft nog geen oefeningen. Genereer ze op het hoofdstukscherm.'));
    return;
  }

  const container = el('div', {});
  setChildren(view, backLink, container);
  const queue = createQueue(shuffle(exercises));
  const disabledIds = new Set();

  function next() {
    if (!container.isConnected) return;
    // Weggestemde oefeningen die nog in de wachtrij zaten overslaan
    while (queue.current && disabledIds.has(queue.current.id)) queue.correct();
    if (queue.done) { renderSummary(); return; }
    renderQuestion(queue.current);
  }

  function progressBar() {
    const {mastered, total} = queue.progress;
    return el('div', {class: 'practice-progress'},
      `${mastered} van ${total} `, el('span', {class: 'sol'}, '●'),
      ` nog ${total - mastered}`);
  }

  function check(exercise, answer) {
    return api(`/api/exercises/${exercise.id}/check`, {
      method: 'POST',
      body: {answer},
    });
  }

  function renderQuestion(exercise) {
    if (exercise.type === 'meerkeuze') renderChoice(exercise);
    else renderTyped(exercise);
  }

  function questionCard(exercise, ...children) {
    return el('div', {class: 'practice-card'},
      el('div', {class: 'practice-hint'}, exercise.instruction),
      el('div', {class: 'practice-word'}, exercise.prompt),
      ...children,
    );
  }

  /* ── Typen: invullen, vertalen, herschrijven ── */

  function renderTyped(exercise) {
    const input = el('input', {
      type: 'text', autocapitalize: 'off', autocomplete: 'off',
      placeholder: 'Antwoord…', 'aria-label': 'Antwoord',
    });
    const feedback = el('div', {});
    let answered = false;

    const answerForm = el('form', {
      onsubmit: async (e) => {
        e.preventDefault();
        if (answered) return;
        const answer = input.value.trim();
        if (!answer) return;
        answered = true;
        input.readOnly = true;
        const result = await check(exercise, answer);
        input.classList.add(result.result === 'wrong' ? 'check-fout' : 'check-goed');
        showResult(exercise, result, feedback);
      },
    }, input);

    setChildren(container, progressBar(), questionCard(exercise, answerForm), feedback);
    input.focus();
  }

  /* ── Meerkeuze ── */

  function renderChoice(exercise) {
    const feedback = el('div', {});
    let answered = false;
    const buttons = exercise.options.map((option) =>
      el('button', {
        class: 'btn-big',
        onclick: async () => {
          if (answered) return;
          answered = true;
          const result = await check(exercise, option);
          for (const b of buttons) {
            b.disabled = true;
            if (b.textContent === result.correct_answer) b.classList.add('check-goed');
          }
          if (result.result === 'wrong') {
            const chosen = buttons.find((b) => b.textContent === option);
            chosen.classList.add('check-fout');
          }
          showResult(exercise, result, feedback);
        },
      }, option),
    );
    setChildren(container, progressBar(),
      questionCard(exercise, el('div', {class: 'row', style: 'margin-top:0.75rem'}, ...buttons)),
      feedback);
  }

  /* ── Resultaat en wegstemmen ── */

  function disableButton(exercise) {
    return el('button', {
      class: 'muted',
      style: 'font-size:0.85rem',
      onclick: async () => {
        await api(`/api/exercises/${exercise.id}/disable`, {method: 'POST'});
        disabledIds.add(exercise.id);
        next();
      },
    }, '🗑️ Slechte oefening');
  }

  function showResult(exercise, result, feedback) {
    const explanation = result.explanation
      ? el('p', {class: 'muted'}, result.explanation) : null;
    if (result.result === 'correct') {
      setChildren(feedback,
        el('div', {class: 'feedback goed'}, '¡Muy bien!'), explanation);
      queue.correct();
      setTimeout(next, explanation ? 1600 : 700);
      return;
    }
    const continueButton = el('button', {class: 'btn-primary btn-big', onclick: next}, 'Verder');
    if (result.result === 'correct_accent') {
      setChildren(feedback,
        el('div', {class: 'feedback accent'},
          'Goed! Maar let op het accent: ',
          el('span', {class: 'answer'}, result.correct_answer)),
        explanation, el('div', {class: 'row'}, continueButton, disableButton(exercise)),
      );
      queue.correct();
    } else {
      setChildren(feedback,
        el('div', {class: 'feedback fout'},
          'Helaas — het juiste antwoord is ',
          el('span', {class: 'answer'}, result.correct_answer)),
        result.feedback ? el('p', {class: 'muted'}, result.feedback) : null,
        explanation, el('div', {class: 'row'}, continueButton, disableButton(exercise)),
      );
      queue.wrong();
    }
    continueButton.focus();
  }

  function renderSummary() {
    const {total, wrong} = queue.progress;
    setChildren(container,
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-word'}, '¡Listo!'),
        el('p', {}, `${total} oefeningen gedaan, ${queue.firstTryCorrect} in één keer goed.`),
        wrong ? el('p', {class: 'muted'}, `${wrong}× een fout antwoord.`) : null,
        el('div', {class: 'row', style: 'margin-top:1rem'},
          el('button', {
            class: 'btn-primary btn-big',
            onclick: () => renderPracticeExercises(view, chapterId),
          }, 'Nog een keer'),
          el('a', {class: 'btn btn-big', href: `#/h/${chapterId}`}, 'Klaar'),
        ),
      ),
    );
  }

  next();
}
```

- [ ] **Stap 2: Sluit de route aan**

In `app/static/js/app.js` de import toevoegen:

```js
import {renderPracticeExercises} from './views/practice-exercises.js';
```

en in de `routes`-lijst, na de werkwoorden-oefenroute:

```js
[
  /^h\/(\d+)\/oefen\/oefeningen$/,
  (id) => renderPracticeExercises(view, +id),
],
```

- [ ] **Stap 3: Volledige suite + commit**

Run: `python -m pytest -q` en `node --test tests/js/` → alles groen.

```bash
git add app/static/js/views/practice-exercises.js app/static/js/app.js
git commit -m "Oefenen: nieuwe oefenmodus voor gegenereerde oefeningen"
```

---

### Taak 8: Afronding — documentatie, spec bijwerken, verificatie in de echte UI

**Files:**
- Modify: `README.md` (configuratie-sectie)
- Modify: `docs/superpowers/specs/2026-07-22-llm-oefeningen-scans-conversatie-design.md` (afwijkingen verwerken)

**Interfaces:** geen — documentatie en verificatie.

- [ ] **Stap 1: Documenteer de configuratie**

Voeg in `README.md`, bij de bestaande uitleg over `.env`, toe:

```markdown
Voor de LLM-functies (oefeningen genereren, vertaalbeoordeling):

    ANTHROPIC_API_KEY=sk-ant-...   # verplicht voor LLM-functies
    LLM_MODEL=claude-opus-4-8      # optioneel, dit is de default

Zonder key blijft de rest van de app gewoon werken; alleen genereren
geeft dan een foutmelding en vertaalzinnen vallen terug op de lokale check.
```

- [ ] **Stap 2: Werk de spec bij**

In `docs/superpowers/specs/2026-07-22-llm-oefeningen-scans-conversatie-design.md`:
- Vervang in de tabel onder "Oefenen" de vertalen-rij door: `eerst lokaal tegen opgeslagen antwoord; alleen bij "fout" beoordeelt Claude (goed/fout + korte uitleg) binnen hetzelfde check-endpoint`.
- Vervang `POST /api/chapters/{id}/exercises/generate` door `POST /api/exercises/generate` (met `chapter_id` in de body).
- Verwijder in de LLM-laag-sectie `images=None` uit de signatuur en voeg toe: "afbeeldingen gaan in fase 2 als content-blocks in `messages` mee".

- [ ] **Stap 3: Draai alles**

Run: `python -m pytest -q` en `node --test tests/js/`
Verwacht: alles groen.

- [ ] **Stap 4: Verifieer in de echte UI**

Gebruik de project-skill `verify` (draait de app lokaal en controleert via de echte web-UI):
- Hoofdstuk met grammatica → "✨ Genereer oefeningen" → teller loopt op (vereist een geldige `ANTHROPIC_API_KEY` in `.env`; zonder key: controleer dat de nette foutmelding verschijnt).
- Oefenen: elk van de vier typen beantwoorden, goed én fout; uitleg en feedback zichtbaar; wegstemmen haalt de oefening uit de rotatie en verlaagt de teller op het hoofdstukscherm.

- [ ] **Stap 5: Commit**

```bash
git add README.md docs/superpowers/specs/2026-07-22-llm-oefeningen-scans-conversatie-design.md
git commit -m "Oefeningen: documentatie en spec-afwijkingen bijgewerkt"
```
