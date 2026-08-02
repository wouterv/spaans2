# Hoofdstukken handmatig sorteren — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De volgorde van hoofdstukken handmatig kunnen aanpassen met ▲/▼-knopjes per rij.

**Architecture:** De `chapters`-tabel heeft al een `position`-kolom en `GET /api/chapters` sorteert al op `position, id`. Er komt één nieuw endpoint (`POST /api/chapters/{id}/move`) dat het hoofdstuk met z'n buurman verwisselt en álle posities hernummert naar 1..n (zelfherstellend voor de oude default `position = 0`). De frontend (`chapters.js`) krijgt per rij ▲/▼-icoon-knopjes die dit endpoint aanroepen en de lijst opnieuw renderen.

**Tech Stack:** FastAPI + SQLite (geen ORM), vanilla-JS frontend zonder build-stap, pytest.

**Spec:** `docs/superpowers/specs/2026-08-02-hoofdstukken-sorteren-design.md`

## Global Constraints

- Commit-messages in het Nederlands, afgesloten met `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Tests draaien met `.venv/bin/python -m pytest tests/` (pytest zit alleen in de venv).
- UI-teksten en aria-labels in het Nederlands.
- Foutdetail bij 404 exact: `"Hoofdstuk niet gevonden"` (consistent met de bestaande endpoints).

---

### Task 1: Backend — move-endpoint

**Files:**
- Modify: `app/routers/chapters.py`
- Test: `tests/test_api_chapters.py`

**Interfaces:**
- Consumes: bestaande fixture `client` (FastAPI TestClient, ingelogd) en `app_instance` uit `tests/conftest.py`; bestaande tabel `chapters(id, name, position)`.
- Produces: `POST /api/chapters/{chapter_id}/move`, body `{"direction": "up"|"down"}` → 200 `{"id": int, "position": int}` (positie is 1-gebaseerd na hernummeren), 404 bij onbekend id, 422 bij ongeldige direction. Task 2 roept dit endpoint aan.

- [ ] **Step 1: Schrijf de falende tests**

Voeg onderaan `tests/test_api_chapters.py` toe:

```python
def _chapter_names(client):
    return [c["name"] for c in client.get("/api/chapters").json()]


def test_move_chapter_up(client):
    client.post("/api/chapters", json={"name": "Uno"})
    dos = client.post("/api/chapters", json={"name": "Dos"}).json()["id"]
    response = client.post(f"/api/chapters/{dos}/move", json={"direction": "up"})
    assert response.status_code == 200
    assert response.json() == {"id": dos, "position": 1}
    assert _chapter_names(client) == ["Dos", "Uno"]


def test_move_chapter_down(client):
    uno = client.post("/api/chapters", json={"name": "Uno"}).json()["id"]
    client.post("/api/chapters", json={"name": "Dos"})
    response = client.post(f"/api/chapters/{uno}/move", json={"direction": "down"})
    assert response.status_code == 200
    assert _chapter_names(client) == ["Dos", "Uno"]


def test_move_at_edges_changes_nothing(client):
    uno = client.post("/api/chapters", json={"name": "Uno"}).json()["id"]
    dos = client.post("/api/chapters", json={"name": "Dos"}).json()["id"]
    up = client.post(f"/api/chapters/{uno}/move", json={"direction": "up"})
    down = client.post(f"/api/chapters/{dos}/move", json={"direction": "down"})
    assert up.status_code == 200
    assert down.status_code == 200
    assert _chapter_names(client) == ["Uno", "Dos"]


def test_move_missing_chapter_is_404(client):
    response = client.post("/api/chapters/999/move", json={"direction": "up"})
    assert response.status_code == 404


def test_move_invalid_direction_is_422(client):
    chapter = client.post("/api/chapters", json={"name": "Uno"}).json()["id"]
    response = client.post(f"/api/chapters/{chapter}/move", json={"direction": "sideways"})
    assert response.status_code == 422


def test_move_herstelt_gelijke_posities(client, app_instance):
    # Oude hoofdstukken kunnen allemaal position 0 hebben (de oude default);
    # één verplaatsing hernummert alles naar 1..n.
    from app import db

    conn = db.connect(app_instance.state.db_path)
    try:
        for name in ("A", "B", "C"):
            conn.execute(
                "INSERT INTO chapters (name, position) VALUES (?, 0)", (name,)
            )
        conn.commit()
    finally:
        conn.close()
    ids = {c["name"]: c["id"] for c in client.get("/api/chapters").json()}
    client.post(f"/api/chapters/{ids['C']}/move", json={"direction": "up"})
    chapters = client.get("/api/chapters").json()
    assert [c["name"] for c in chapters] == ["A", "C", "B"]
    assert [c["position"] for c in chapters] == [1, 2, 3]
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `.venv/bin/python -m pytest tests/test_api_chapters.py -q`
Expected: de zes nieuwe tests FALEN met status 404/405 (endpoint bestaat niet); de bestaande tests slagen.

- [ ] **Step 3: Implementeer het endpoint**

In `app/routers/chapters.py`: breid de imports uit en voeg het endpoint toe ná `create_chapter`.

Bovenaan (regel 1-4) wordt de import-sectie:

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_conn
```

Nieuw model onder `ChapterIn`:

```python
class MoveRequest(BaseModel):
    direction: Literal["up", "down"]
```

Nieuw endpoint:

```python
@router.post("/{chapter_id}/move")
def move_chapter(chapter_id: int, body: MoveRequest, conn=Depends(get_conn)):
    ids = [
        row["id"]
        for row in conn.execute("SELECT id FROM chapters ORDER BY position, id")
    ]
    if chapter_id not in ids:
        raise HTTPException(status_code=404, detail="Hoofdstuk niet gevonden")
    index = ids.index(chapter_id)
    neighbour = index - 1 if body.direction == "up" else index + 1
    if 0 <= neighbour < len(ids):
        ids[index], ids[neighbour] = ids[neighbour], ids[index]
    # Hernummeren naar 1..n herstelt ook oude rijen die allemaal op 0 staan
    conn.executemany(
        "UPDATE chapters SET position = ? WHERE id = ?",
        list(enumerate(ids, start=1)),
    )
    conn.commit()
    return {"id": chapter_id, "position": ids.index(chapter_id) + 1}
```

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `.venv/bin/python -m pytest tests/test_api_chapters.py -q`
Expected: alles PASS.

- [ ] **Step 5: Draai de hele suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: alles PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/chapters.py tests/test_api_chapters.py
git commit -m "Hoofdstukken: move-endpoint voor handmatig sorteren

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Frontend — ▲/▼-knopjes in de hoofdstukkenlijst

**Files:**
- Modify: `app/static/js/views/chapters.js`

**Interfaces:**
- Consumes: `POST /api/chapters/{chapter_id}/move` met body `{"direction": "up"|"down"}` (Task 1); helpers `api` en `el` uit `../api.js`.
- Produces: geen — dit is het eindpunt van de feature.

Er zijn geen JS-tests per view in dit project; verificatie gebeurt in Step 2 via de echte UI (verify-skill).

- [ ] **Step 1: Voeg de knopjes toe**

In `app/static/js/views/chapters.js`: de map-callback over `chapters` krijgt een tweede parameter `index`, en vóór de bestaande ✏️-knop komen twee nieuwe knopjes. De relevante regels worden:

```js
    ...chapters.map((chapter, index) =>
      el(
        'li',
        {},
        el(
          'a',
          {class: 'grow', href: `#/h/${chapter.id}`},
          el('strong', {}, chapter.name),
        ),
        el(
          'span',
          {class: 'counts'},
          `${chapter.word_count} w · ${chapter.verb_count} ww · ${chapter.grammar_count} gr`,
        ),
        el('button', {
          class: 'icon-btn',
          title: 'Omhoog',
          'aria-label': `Verplaats ${chapter.name} omhoog`,
          // el() gebruikt setAttribute: null wordt overgeslagen, '' zet het attribuut
          disabled: index === 0 ? '' : null,
          onclick: async () => {
            await api(`/api/chapters/${chapter.id}/move`, {
              method: 'POST',
              body: {direction: 'up'},
            });
            renderChapters(view);
          },
        }, '▲'),
        el('button', {
          class: 'icon-btn',
          title: 'Omlaag',
          'aria-label': `Verplaats ${chapter.name} omlaag`,
          disabled: index === chapters.length - 1 ? '' : null,
          onclick: async () => {
            await api(`/api/chapters/${chapter.id}/move`, {
              method: 'POST',
              body: {direction: 'down'},
            });
            renderChapters(view);
          },
        }, '▼'),
```

(De bestaande ✏️- en 🗑️-knoppen blijven ongewijzigd daarachter staan.)

- [ ] **Step 2: Verifieer in de echte UI**

Gebruik de projectskill `verify` (testinstantie op poort 8765, wachtwoord `verifytest`):
maak drie hoofdstukken ("Uno", "Dos", "Tres"), klik ▼ bij "Uno" en controleer
dat de volgorde "Dos, Uno, Tres" wordt; controleer dat ▲ bij de bovenste en
▼ bij de onderste rij disabled zijn; herlaad de pagina en controleer dat de
volgorde bewaard blijft. Stop daarna de testinstantie
(`pkill -f '[u]vicorn.*8765'` in een los commando zonder de tekenreeks
"uvicorn...8765" elders op de regel, anders raakt pkill z'n eigen shell).

- [ ] **Step 3: Draai de JS-tests (regressie)**

Run: `node --test 'tests/js/*.mjs'`
Expected: alles PASS (chapters.js heeft geen eigen tests; dit is een regressiecheck).

- [ ] **Step 4: Commit**

```bash
git add app/static/js/views/chapters.js
git commit -m "Hoofdstukken: sorteren met ▲/▼-knopjes in de lijst

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
