# Samen oefenen over meerdere hoofdstukken — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoofdstukken selecteren (of alles) en met alle stof samen oefenen: woorden, werkwoorden, LLM-oefeningen en gesprek.

**Architecture:** Bestaande endpoints (`GET /api/practice/items`, `GET /api/exercises`) accepteren naast `chapter_id` een `chapter_ids`-kommalijst via een gedeelde resolver in `app/deps.py`. Een nieuw `POST /api/conversation` bundelt de lesstof van meerdere hoofdstukken met naam-koppen; de gedeelde beurt-logica wordt een interne functie die beide gesprek-endpoints gebruiken. De vier oefen-views krijgen een `chapterIds`-array in plaats van één id; een nieuw scherm `#/samen` (combined.js) biedt hoofdstuk-vinkjes (onthouden in localStorage) en dezelfde oefenkaarten.

**Tech Stack:** FastAPI + SQLite (geen ORM), vanilla-JS frontend zonder build-stap, pytest (LLM gemockt via monkeypatch).

**Spec:** `docs/superpowers/specs/2026-08-06-samen-oefenen-design.md`

## Global Constraints

- Commit-messages in het Nederlands, afgesloten met `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Tests: `.venv/bin/python -m pytest tests/` (pytest alleen in de venv); JS: `node --test 'tests/js/*.mjs'`.
- UI-teksten in het Nederlands.
- `chapter_id`/`chapter_ids`: precies één verplicht; 422 bij beide/geen van beide of een lege/niet-numerieke lijst; 404 ("Hoofdstuk niet gevonden") als een id niet bestaat; itemvolgorde = volgorde van de meegegeven lijst.
- Bestaande per-hoofdstuk-routes en het bestaande `POST /api/chapters/{id}/conversation` blijven werken.

---

### Task 1: Backend — chapter_ids op practice/items en exercises

**Files:**
- Modify: `app/deps.py`
- Modify: `app/routers/practice.py:33-39` (functie `practice_items`)
- Modify: `app/routers/exercises.py:17-30` (functie `list_exercises`)
- Test: `tests/test_api_practice.py`, `tests/test_api_exercises.py`

**Interfaces:**
- Consumes: bestaande `chapter_or_404(conn, chapter_id)` in `app/deps.py`; fixtures `client`, `chapter_id` en `FORMS` in de testbestanden; `list_words(chapter_id, conn)` / `list_verbs(chapter_id, conn)`.
- Produces: `resolve_chapter_ids(conn, chapter_id, chapter_ids) -> list[int]` in `app/deps.py` (Task 2 gebruikt deze NIET — die valideert via pydantic-body); `GET /api/practice/items?type=...&chapter_ids=1,2` en `GET /api/exercises?chapter_ids=1,2` → gecombineerde lijsten in lijst-volgorde. Task 3 roept beide met `chapter_ids` aan.

- [ ] **Step 1: Schrijf de falende tests**

Onderaan `tests/test_api_practice.py`:

```python
class TestChapterIds:
    def test_combineert_woorden_van_meerdere_hoofdstukken(self, client, chapter_id):
        tweede = client.post("/api/chapters", json={"name": "H2"}).json()["id"]
        client.post("/api/words", json={
            "chapter_id": chapter_id, "spanish": "casa", "dutch": "huis"})
        client.post("/api/words", json={
            "chapter_id": tweede, "spanish": "coche", "dutch": "auto"})
        items = client.get(
            f"/api/practice/items?type=words&chapter_ids={tweede},{chapter_id}"
        ).json()
        # Volgorde van de meegegeven lijst
        assert [w["spanish"] for w in items] == ["coche", "casa"]

    def test_chapter_ids_met_onbekend_id_is_404(self, client, chapter_id):
        response = client.get(
            f"/api/practice/items?type=words&chapter_ids={chapter_id},999"
        )
        assert response.status_code == 404

    def test_beide_of_geen_parameters_is_422(self, client, chapter_id):
        beide = client.get(
            f"/api/practice/items?type=words&chapter_id={chapter_id}"
            f"&chapter_ids={chapter_id}"
        )
        geen = client.get("/api/practice/items?type=words")
        assert beide.status_code == 422
        assert geen.status_code == 422

    def test_lege_of_rare_lijst_is_422(self, client, chapter_id):
        assert client.get(
            "/api/practice/items?type=words&chapter_ids="
        ).status_code == 422
        assert client.get(
            "/api/practice/items?type=words&chapter_ids=1,abc"
        ).status_code == 422

    def test_chapter_id_blijft_werken(self, client, chapter_id, word_id):
        items = client.get(
            f"/api/practice/items?chapter_id={chapter_id}&type=words"
        ).json()
        assert len(items) == 1
```

Onderaan `tests/test_api_exercises.py` (gebruik de bestaande fixtures/helpers van dat bestand om een oefening in de database te zetten; staat daar al een insert-helper of -patroon, volg dat dan — anders direct via `app.db.connect(app_instance.state.db_path)` zoals in `tests/test_api_chapters.py::test_chapter_telt_alleen_actieve_oefeningen`):

```python
def _insert_exercise(app_instance, chapter_id, prompt):
    from app import db

    conn = db.connect(app_instance.state.db_path)
    try:
        conn.execute(
            "INSERT INTO exercises (chapter_id, type, instruction, prompt, "
            "answer) VALUES (?, 'invullen', 'Vul in', ?, 'soy')",
            (chapter_id, prompt),
        )
        conn.commit()
    finally:
        conn.close()


class TestChapterIds:
    def test_combineert_oefeningen_in_lijstvolgorde(self, client, app_instance):
        eerste = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
        tweede = client.post("/api/chapters", json={"name": "H2"}).json()["id"]
        _insert_exercise(app_instance, eerste, "Yo ___ (1).")
        _insert_exercise(app_instance, tweede, "Yo ___ (2).")
        body = client.get(f"/api/exercises?chapter_ids={tweede},{eerste}").json()
        assert [e["prompt"] for e in body] == ["Yo ___ (2).", "Yo ___ (1)."]

    def test_onbekend_id_is_404_en_beide_params_is_422(self, client):
        eerste = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
        assert client.get("/api/exercises?chapter_ids=999").status_code == 404
        assert client.get(
            f"/api/exercises?chapter_id={eerste}&chapter_ids={eerste}"
        ).status_code == 422
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `.venv/bin/python -m pytest tests/test_api_practice.py tests/test_api_exercises.py -q`
Expected: de nieuwe tests FALEN (422 van FastAPI's verplichte `chapter_id`, of verkeerde respons); bestaande tests slagen.

- [ ] **Step 3: Implementeer de resolver en beide endpoints**

1. In `app/deps.py`, onder `chapter_or_404`:

```python
def resolve_chapter_ids(conn, chapter_id, chapter_ids):
    """Eén chapter_id óf een kommalijst chapter_ids naar een lijst ids.

    Precies één van beide is verplicht (422), elke id moet bestaan (404);
    de volgorde van de meegegeven lijst blijft behouden.
    """
    from fastapi import HTTPException

    if (chapter_id is None) == (chapter_ids is None):
        raise HTTPException(
            status_code=422, detail="Geef chapter_id óf chapter_ids op"
        )
    if chapter_id is not None:
        ids = [chapter_id]
    else:
        parts = [p.strip() for p in chapter_ids.split(",")]
        if not parts or not all(p.isdigit() for p in parts):
            raise HTTPException(
                status_code=422,
                detail="chapter_ids moet een kommalijst van ids zijn",
            )
        ids = [int(p) for p in parts]
    for cid in ids:
        chapter_or_404(conn, cid)
    return ids
```

2. In `app/routers/practice.py`: import uitbreiden (`from app.deps import get_conn, resolve_chapter_ids`) en `practice_items` vervangen door:

```python
@router.get("/items")
def practice_items(
    type: Literal["words", "verbs"],
    chapter_id: int | None = None,
    chapter_ids: str | None = None,
    conn=Depends(get_conn),
):
    ids = resolve_chapter_ids(conn, chapter_id, chapter_ids)
    lister = list_words if type == "words" else list_verbs
    items = []
    for cid in ids:
        items.extend(lister(cid, conn))
    return items
```

3. In `app/routers/exercises.py`: import uitbreiden (`from app.deps import get_conn, resolve_chapter_ids` — laat bestaande imports staan) en `list_exercises` vervangen door:

```python
@router.get("")
def list_exercises(
    chapter_id: int | None = None,
    chapter_ids: str | None = None,
    conn=Depends(get_conn),
):
    ids = resolve_chapter_ids(conn, chapter_id, chapter_ids)
    exercises = []
    for cid in ids:
        rows = conn.execute(
            "SELECT id, chapter_id, type, instruction, prompt, answer, "
            "options, explanation FROM exercises "
            "WHERE chapter_id = ? AND disabled = 0 ORDER BY id",
            (cid,),
        ).fetchall()
        exercises.extend(
            dict(row, options=json.loads(row["options"]) if row["options"] else None)
            for row in rows
        )
    return exercises
```

Let op: als een bestaande test faalt omdat een onbekende `chapter_id` vroeger een lege lijst gaf en nu 404, is dat de bedoelde gedragsverandering — pas die test aan en meld het in je report.

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `.venv/bin/python -m pytest tests/test_api_practice.py tests/test_api_exercises.py -q`
Expected: alles PASS.

- [ ] **Step 5: Draai de hele suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: alles PASS.

- [ ] **Step 6: Commit**

```bash
git add app/deps.py app/routers/practice.py app/routers/exercises.py tests/test_api_practice.py tests/test_api_exercises.py
git commit -m "Oefenen: items en oefeningen over meerdere hoofdstukken

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Backend — POST /api/conversation over meerdere hoofdstukken

**Files:**
- Modify: `app/lesstof.py`
- Modify: `app/routers/conversation.py`
- Modify: `app/main.py` (router-registratie)
- Test: `tests/test_api_conversation.py`

**Interfaces:**
- Consumes: `lesson_context(conn, chapter_id)` (bestaand in `app/lesstof.py`); `chapter_or_404` uit `app.deps`; test-idioom `_fake(...)` en fixture `chapter_id` in `tests/test_api_conversation.py`.
- Produces: `combined_context(conn, chapter_ids) -> str` in `app/lesstof.py`; `POST /api/conversation` met body `{"chapter_ids": [int, ...], "messages": [...]}` → `{"correction": str, "reply": str}` (zelfde vorm als het bestaande endpoint); 404 bij onbekend id, 422 bij lege lijst, 400 als de hele selectie geen lesstof heeft. Task 3 roept dit endpoint aan bij meerdere ids.

- [ ] **Step 1: Schrijf de falende tests**

Onderaan `tests/test_api_conversation.py`:

```python
class TestSamenGesprek:
    def _tweede_hoofdstuk(self, client, naam="H2"):
        cid = client.post("/api/chapters", json={"name": naam}).json()["id"]
        client.post("/api/words", json={
            "chapter_id": cid, "spanish": "coche", "dutch": "auto",
        })
        return cid

    def test_bundelt_lesstof_met_naamkoppen(self, client, chapter_id, monkeypatch):
        tweede = self._tweede_hoofdstuk(client)
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(aanroepen=aanroepen))
        response = client.post("/api/conversation", json={
            "chapter_ids": [chapter_id, tweede], "messages": [],
        })
        assert response.status_code == 200
        assert response.json()["reply"] == "¡Hola! ¿Cómo estás?"
        systeem = aanroepen[0]["system"]
        assert "# H1" in systeem
        assert "# H2" in systeem
        assert "Ser en estar" in systeem
        assert "coche" in systeem
        # H1-kop staat vóór H2-kop (volgorde van de lijst)
        assert systeem.index("# H1") < systeem.index("# H2")

    def test_onbekend_id_is_404_en_lege_lijst_is_422(self, client, chapter_id):
        assert client.post("/api/conversation", json={
            "chapter_ids": [999], "messages": [],
        }).status_code == 404
        assert client.post("/api/conversation", json={
            "chapter_ids": [], "messages": [],
        }).status_code == 422

    def test_selectie_zonder_lesstof_is_400(self, client, monkeypatch):
        leeg = client.post("/api/chapters", json={"name": "Leeg"}).json()["id"]
        monkeypatch.setattr(llm, "complete_json", _fake())
        response = client.post("/api/conversation", json={
            "chapter_ids": [leeg], "messages": [],
        })
        assert response.status_code == 400

    def test_hoofdstuk_zonder_lesstof_krijgt_geen_kop(
        self, client, chapter_id, monkeypatch
    ):
        leeg = client.post("/api/chapters", json={"name": "LeegHoofdstuk"}).json()["id"]
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(aanroepen=aanroepen))
        client.post("/api/conversation", json={
            "chapter_ids": [chapter_id, leeg], "messages": [],
        })
        assert "LeegHoofdstuk" not in aanroepen[0]["system"]
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `.venv/bin/python -m pytest tests/test_api_conversation.py -q`
Expected: nieuwe tests FALEN met 404 (route bestaat niet); bestaande slagen.

- [ ] **Step 3: Implementeer combined_context en het endpoint**

1. In `app/lesstof.py`, onderaan (import bovenaan niet nodig — sqlite-row-access volstaat):

```python
def combined_context(conn, chapter_ids):
    """Lesstof van meerdere hoofdstukken, elk onder een kop met de naam.

    Hoofdstukken zonder lesstof worden overgeslagen.
    """
    parts = []
    for chapter_id in chapter_ids:
        row = conn.execute(
            "SELECT name FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        context = lesson_context(conn, chapter_id)
        if row and context:
            parts.append(f"# {row['name']}\n{context}")
    return "\n\n".join(parts)
```

2. In `app/routers/conversation.py`:

- Import uitbreiden: `from app.lesstof import combined_context, lesson_context`.
- De beurt-logica van `conversation_turn` (vanaf `if body.messages:` t/m de `return`) verhuist naar een interne functie:

```python
def _turn(lesstof, body):
    if body.messages:
        if body.messages[-1].role != "user":
            raise HTTPException(
                status_code=400,
                detail="Het laatste bericht moet van de leerling zijn",
            )
        # Assistent-beurten gaan terug in het formaat waarin het model ze gaf
        # (reply + correction op het voorafgaande leerling-bericht), zodat het
        # ziet welke correcties al gegeven zijn en die niet herhaalt.
        messages = []
        last_correction = ""
        for turn in body.messages:
            if turn.role == "user":
                last_correction = turn.correction
                messages.append({"role": "user", "content": turn.text})
            else:
                messages.append({
                    "role": "assistant",
                    "content": json.dumps(
                        {"reply": turn.text, "correction": last_correction},
                        ensure_ascii=False,
                    ),
                })
                last_correction = ""
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
    if len(correction) > MAX_CORRECTION_LENGTH:
        correction = ""
    return {"correction": correction, "reply": reply}
```

- `conversation_turn` wordt daarmee:

```python
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
    return _turn(lesstof, body)
```

- Nieuw model en nieuwe router (de bestaande `router` heeft prefix `/api/chapters`; het nieuwe endpoint hangt op `/api`):

```python
combined_router = APIRouter(prefix="/api")


class CombinedConversationRequest(ConversationRequest):
    chapter_ids: list[int] = Field(min_length=1)


@combined_router.post("/conversation")
def combined_conversation_turn(
    body: CombinedConversationRequest, conn=Depends(get_conn)
):
    for chapter_id in body.chapter_ids:
        chapter_or_404(conn, chapter_id)
    lesstof = combined_context(conn, body.chapter_ids)
    if not lesstof:
        raise HTTPException(
            status_code=400,
            detail="De gekozen hoofdstukken hebben nog geen lesstof om over te praten",
        )
    return _turn(lesstof, body)
```

3. In `app/main.py`, na `app.include_router(conversation.router)`:

```python
    app.include_router(conversation.combined_router)
```

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `.venv/bin/python -m pytest tests/test_api_conversation.py -q`
Expected: alles PASS.

- [ ] **Step 5: Draai de hele suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: alles PASS.

- [ ] **Step 6: Commit**

```bash
git add app/lesstof.py app/routers/conversation.py app/main.py tests/test_api_conversation.py
git commit -m "Gesprek: nieuw endpoint over meerdere hoofdstukken

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Frontend — oefen-views en routes op chapterIds

**Files:**
- Modify: `app/static/js/app.js:20-44` (routetabel)
- Modify: `app/static/js/views/practice-words.js:6-14`
- Modify: `app/static/js/views/practice-verbs.js:11-19`
- Modify: `app/static/js/views/practice-exercises.js:4-13`
- Modify: `app/static/js/views/conversation.js:14-78` (kop, terugknop, endpoint, opslag-key)

**Interfaces:**
- Consumes: `GET /api/practice/items?type=...&chapter_ids=...` en `GET /api/exercises?chapter_ids=...` (Task 1); `POST /api/conversation` met `{chapter_ids, messages}` (Task 2).
- Produces: view-signaturen die Task 4 aanroept via routes: `renderPracticeWords(view, chapterIds, direction, mode)`, `renderPracticeVerbs(view, chapterIds, mode)`, `renderPracticeExercises(view, chapterIds)`, `renderConversation(view, chapterIds)` — `chapterIds` is altijd een array van ints. Routes: `#/oefen/<ids>/woorden/(es_nl|nl_es)/(typen|spraak)`, `#/oefen/<ids>/werkwoorden/(typen|spraak)`, `#/oefen/<ids>/oefeningen`, `#/gesprek/<ids>` met `<ids>` = `\d+(?:,\d+)*`. Route `#/samen` bestaat pas na Task 4 — de terugknop mag er al naar wijzen.

- [ ] **Step 1: Pas de vier views aan**

Gedeeld patroon (in elke view): de parameter heet voortaan `chapterIds` (array), de API-call gebruikt `chapter_ids=${chapterIds.join(',')}`, en de terugknop is:

```js
  const single = chapterIds.length === 1;
  const backLink = el('p', {}, el('a', {
    href: single ? `#/h/${chapterIds[0]}` : '#/samen', class: 'muted',
  }, single ? '← Hoofdstuk' : '← Samen oefenen'));
```

1. `practice-words.js` — kop van de functie wordt:

```js
export async function renderPracticeWords(view, chapterIds, direction, mode) {
  const words = await api(`/api/practice/items?chapter_ids=${chapterIds.join(',')}&type=words`);
  const single = chapterIds.length === 1;
  const backLink = el('p', {}, el('a', {
    href: single ? `#/h/${chapterIds[0]}` : '#/samen', class: 'muted',
  }, single ? '← Hoofdstuk' : '← Samen oefenen'));

  if (!words.length) {
    setChildren(view, backLink,
      el('p', {class: 'muted'}, 'Nog geen woorden om te oefenen in deze selectie.'));
    return;
  }
```

De "Nog een keer"-knop in `renderSummary` roept `renderPracticeWords(view, chapterIds, direction, mode)` aan (zelfde naam als de nieuwe parameter).

2. `practice-verbs.js` — zelfde patroon:

```js
export async function renderPracticeVerbs(view, chapterIds, mode) {
  const verbs = await api(`/api/practice/items?chapter_ids=${chapterIds.join(',')}&type=verbs`);
  const single = chapterIds.length === 1;
  const backLink = el('p', {}, el('a', {
    href: single ? `#/h/${chapterIds[0]}` : '#/samen', class: 'muted',
  }, single ? '← Hoofdstuk' : '← Samen oefenen'));

  if (!verbs.length) {
    setChildren(view, backLink,
      el('p', {class: 'muted'}, 'Nog geen werkwoorden om te oefenen in deze selectie.'));
    return;
  }
```

"Nog een keer" → `renderPracticeVerbs(view, chapterIds, mode)`.

3. `practice-exercises.js` — zelfde patroon:

```js
export async function renderPracticeExercises(view, chapterIds) {
  const exercises = await api(`/api/exercises?chapter_ids=${chapterIds.join(',')}`);
  const single = chapterIds.length === 1;
  const backLink = el('p', {}, el('a', {
    href: single ? `#/h/${chapterIds[0]}` : '#/samen', class: 'muted',
  }, single ? '← Hoofdstuk' : '← Samen oefenen'));

  if (!exercises.length) {
    setChildren(view, backLink,
      el('p', {class: 'muted'},
        'Nog geen oefeningen in deze selectie. Genereer ze op het hoofdstukscherm.'));
    return;
  }
```

Controleer of deze view verderop nog een "opnieuw"-pad heeft dat de functie zelf aanroept en geef daar `chapterIds` door.

4. `conversation.js` — de kop van de functie wordt:

```js
export async function renderConversation(view, chapterIds) {
  const single = chapterIds.length === 1;
  const chapters = await api('/api/chapters');
  const chapter = single ? chapters.find((c) => c.id === chapterIds[0]) : null;
  if (single && !chapter) { location.hash = '#/'; return; }

  // De server slaat niets op; de geschiedenis staat lokaal in de browser
  // ({role, text, correction?}) en overleeft zo een refresh
  const gesprekKey = `spaans-gesprek-${chapterIds.join('-')}`;
```

(De bestaande key voor één hoofdstuk was `spaans-gesprek-${chapterId}`; met `join('-')` blijft die voor één id identiek, dus lopende gesprekken blijven bewaard.)

De kop-regels in `setChildren(view, ...)` worden:

```js
    el('p', {}, el('a', {
      href: single ? `#/h/${chapterIds[0]}` : '#/samen', class: 'muted',
    }, single ? `← ${chapter.name}` : '← Samen oefenen')),
    el('h1', {}, single ? 'Gesprek' : 'Gesprek — samen oefenen'),
```

En de intro-tekst: bij meerdere hoofdstukken "Praat in het Spaans over de lesstof van de gekozen hoofdstukken. Correcties verschijnen onder je bericht." (bij één blijft de bestaande zin).

De API-call in `requestTurn` wordt:

```js
      const {correction, reply} = await api(
        single ? `/api/chapters/${chapterIds[0]}/conversation` : '/api/conversation',
        // Correcties gaan mee, zodat het model ziet wat al behandeld is
        {method: 'POST', body: {
          ...(single ? {} : {chapter_ids: chapterIds}),
          messages: history.map(({role, text, correction}) =>
            correction ? {role, text, correction} : {role, text}),
        }},
      );
```

- [ ] **Step 2: Pas de routetabel aan**

In `app/static/js/app.js`: de bestaande vier oefen/gesprek-routes geven `[+id]` door, en er komen vier meervoudsroutes bij. De relevante regels worden:

```js
  [/^h\/(\d+)\/gesprek$/, (id) => renderConversation(view, [+id])],
  [
    /^h\/(\d+)\/oefen\/woorden\/(es_nl|nl_es)\/(typen|spraak)$/,
    (id, direction, mode) => renderPracticeWords(view, [+id], direction, mode),
  ],
  [
    /^h\/(\d+)\/oefen\/werkwoorden\/(typen|spraak)$/,
    (id, mode) => renderPracticeVerbs(view, [+id], mode),
  ],
  [
    /^h\/(\d+)\/oefen\/oefeningen$/,
    (id) => renderPracticeExercises(view, [+id]),
  ],
  [
    /^oefen\/(\d+(?:,\d+)*)\/woorden\/(es_nl|nl_es)\/(typen|spraak)$/,
    (ids, direction, mode) => renderPracticeWords(view, ids.split(',').map(Number), direction, mode),
  ],
  [
    /^oefen\/(\d+(?:,\d+)*)\/werkwoorden\/(typen|spraak)$/,
    (ids, mode) => renderPracticeVerbs(view, ids.split(',').map(Number), mode),
  ],
  [
    /^oefen\/(\d+(?:,\d+)*)\/oefeningen$/,
    (ids) => renderPracticeExercises(view, ids.split(',').map(Number)),
  ],
  [/^gesprek\/(\d+(?:,\d+)*)$/, (ids) => renderConversation(view, ids.split(',').map(Number))],
```

- [ ] **Step 3: Verifieer in de echte UI**

Gebruik de projectskill `verify` (testinstantie op poort 8765, wachtwoord `verifytest`). Zaai via de API twee hoofdstukken met elk één woord (bijv. "casa/huis" en "coche/auto"). Met playwright:

1. Open `#/oefen/1,2/woorden/es_nl/typen`: controleer dat de oefening start, de terugknop "← Samen oefenen" toont, en dat je (na de eerste vraag beantwoorden met wat er staat) uiteindelijk beide woorden voorbij ziet komen (of: dat `/api/practice/items?chapter_ids=1,2&type=words` er twee geeft — dat volstaat als bewijs, de view schudt).
2. Open `#/h/1/oefen/woorden/es_nl/typen`: bestaande route werkt, terugknop "← Hoofdstuk", antwoord "huis" wordt goedgekeurd (nakijken werkt dus nog).
3. Controleer in de serverlog of via de netwerkrespons dat `#/gesprek/1,2` een POST naar `/api/conversation` doet (zonder LLM-key geeft die 503 met nette foutmelding in de UI — dat bewijst de juiste route; meld wat je zag).

Stop daarna de testinstantie (pkill in een los commando, patroon `'[u]vicorn.*8765'`, zonder die tekenreeks elders op de regel).

- [ ] **Step 4: Draai de JS-tests (regressie)**

Run: `node --test 'tests/js/*.mjs'`
Expected: alles PASS.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/app.js app/static/js/views/practice-words.js app/static/js/views/practice-verbs.js app/static/js/views/practice-exercises.js app/static/js/views/conversation.js
git commit -m "Oefen-views: werken op een selectie van hoofdstukken

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Frontend — scherm "Samen oefenen" (#/samen)

**Files:**
- Create: `app/static/js/views/combined.js`
- Modify: `app/static/js/app.js` (import + route `#/samen`)
- Modify: `app/static/js/views/chapters.js` (knop naar `#/samen`)

**Interfaces:**
- Consumes: routes uit Task 3 (`#/oefen/<ids>/...` en `#/gesprek/<ids>`); `GET /api/chapters` (bestaand: `[{id, name, position, word_count, verb_count, grammar_count, exercise_count, example_count}]`); helpers `api`, `el`, `setChildren` uit `../api.js`.
- Produces: `renderCombined(view)` in `combined.js`; route `#/samen`; localStorage-key `spaans-samen-selectie` (JSON-array van hoofdstuk-ids).

- [ ] **Step 1: Maak combined.js**

```js
import {api, el, setChildren} from '../api.js';

const SELECTIE_KEY = 'spaans-samen-selectie';

function loadSelectie(chapters) {
  try {
    const bewaard = JSON.parse(localStorage.getItem(SELECTIE_KEY));
    if (Array.isArray(bewaard)) {
      const bestaand = bewaard.filter((id) => chapters.some((c) => c.id === id));
      if (bestaand.length) return new Set(bestaand);
    }
  } catch { /* kapotte opslag telt als geen selectie */ }
  return new Set(chapters.map((c) => c.id));
}

export async function renderCombined(view) {
  const chapters = await api('/api/chapters');
  if (!chapters.length) { location.hash = '#/'; return; }
  const selectie = loadSelectie(chapters);
  const persist = () =>
    localStorage.setItem(SELECTIE_KEY, JSON.stringify([...selectie]));

  let direction = 'es_nl';
  const cards = el('div', {});

  function ids() {
    // In hoofdstuk-volgorde, niet in aanvink-volgorde
    return chapters.filter((c) => selectie.has(c.id)).map((c) => c.id);
  }

  function telling(veld) {
    return chapters
      .filter((c) => selectie.has(c.id))
      .reduce((som, c) => som + c[veld], 0);
  }

  const alleBox = el('input', {type: 'checkbox', 'aria-label': 'Alle hoofdstukken'});
  const boxes = new Map();

  function syncAlleBox() {
    alleBox.checked = selectie.size === chapters.length;
  }

  alleBox.addEventListener('change', () => {
    selectie.clear();
    if (alleBox.checked) for (const c of chapters) selectie.add(c.id);
    for (const [id, box] of boxes) box.checked = selectie.has(id);
    persist();
    renderCards();
  });

  const kiezer = el('div', {class: 'card'},
    el('label', {style: 'display:flex; gap:0.5rem; align-items:center; font-weight:600'},
      alleBox, 'Alles'),
    ...chapters.map((chapter) => {
      const box = el('input', {type: 'checkbox', 'aria-label': chapter.name});
      box.checked = selectie.has(chapter.id);
      boxes.set(chapter.id, box);
      box.addEventListener('change', () => {
        if (box.checked) selectie.add(chapter.id);
        else selectie.delete(chapter.id);
        persist();
        syncAlleBox();
        renderCards();
      });
      return el('label', {style: 'display:flex; gap:0.5rem; align-items:center; margin-top:0.4rem'},
        box,
        el('span', {class: 'grow'}, chapter.name),
        el('span', {class: 'counts'},
          `${chapter.word_count} w · ${chapter.verb_count} ww · ${chapter.exercise_count} oef`),
      );
    }),
  );
  syncAlleBox();

  function startKnop(label, maakHash, aantal) {
    const leeg = !ids().length || !aantal;
    return el('button', {
      class: 'btn btn-big',
      disabled: leeg ? '' : null,
      onclick: () => { if (!leeg) location.hash = maakHash(ids().join(',')); },
    }, label);
  }

  function renderCards() {
    const dirButtons = {};
    const toggleDirection = el('div', {class: 'row', role: 'group', 'aria-label': 'Richting'},
      ...[['es_nl', 'Spaans → Nederlands'], ['nl_es', 'Nederlands → Spaans']]
        .map(([value, label]) => {
          const btn = el('button', {
            class: value === direction ? 'btn-primary' : '',
            onclick: () => {
              direction = value;
              for (const [v, b] of Object.entries(dirButtons)) {
                b.className = v === direction ? 'btn-primary' : '';
              }
            },
          }, label);
          dirButtons[value] = btn;
          return btn;
        }));

    setChildren(cards,
      ids().length ? null : el('p', {class: 'muted'}, 'Selecteer minstens één hoofdstuk om te oefenen.'),
      el('div', {class: 'card'},
        el('h2', {}, `Woorden (${telling('word_count')})`),
        toggleDirection,
        el('div', {class: 'row', style: 'margin-top:0.75rem'},
          startKnop('⌨️ Typen', (ids) => `#/oefen/${ids}/woorden/${direction}/typen`, telling('word_count')),
          startKnop('🎙️ Spraak', (ids) => `#/oefen/${ids}/woorden/${direction}/spraak`, telling('word_count')),
        ),
      ),
      el('div', {class: 'card'},
        el('h2', {}, `Werkwoorden (${telling('verb_count')})`),
        el('div', {class: 'row'},
          startKnop('⌨️ Typen', (ids) => `#/oefen/${ids}/werkwoorden/typen`, telling('verb_count')),
          startKnop('🎙️ Spraak', (ids) => `#/oefen/${ids}/werkwoorden/spraak`, telling('verb_count')),
        ),
      ),
      el('div', {class: 'card'},
        el('h2', {}, `Oefeningen (${telling('exercise_count')})`),
        el('div', {class: 'row'},
          startKnop('⌨️ Oefenen', (ids) => `#/oefen/${ids}/oefeningen`, telling('exercise_count')),
        ),
      ),
      el('div', {class: 'card'},
        el('h2', {}, 'Gesprek'),
        el('p', {class: 'muted'}, 'Conversatie over de lesstof van de gekozen hoofdstukken.'),
        el('div', {class: 'row'},
          startKnop('💬 Gesprek starten', (ids) => `#/gesprek/${ids}`,
            telling('word_count') + telling('verb_count') + telling('grammar_count')),
        ),
      ),
    );
  }

  renderCards();
  setChildren(view,
    el('p', {}, el('a', {href: '#/', class: 'muted'}, '← Hoofdstukken')),
    el('h1', {}, 'Samen oefenen'),
    el('div', {class: 'eyebrow'}, 'Hoofdstukken'),
    kiezer,
    el('div', {class: 'eyebrow'}, 'Oefenen'),
    cards,
  );
}
```

- [ ] **Step 2: Route en knop**

1. In `app/static/js/app.js`: import toevoegen en route (bovenin de tabel, bij de andere niet-hoofdstukroutes):

```js
import {renderCombined} from './views/combined.js';
```

```js
  [/^samen$/, () => renderCombined(view)],
```

2. In `app/static/js/views/chapters.js`: in de `setChildren(view, ...)`-aanroep, direct na het formulier:

```js
    chapters.length >= 2
      ? el('p', {style: 'margin-top:0.75rem'},
          el('a', {class: 'btn', href: '#/samen'}, '🎯 Samen oefenen'))
      : null,
```

- [ ] **Step 3: Verifieer in de echte UI**

Met de verify-skill (testinstantie op 8765; zaai twee hoofdstukken met elk één woord en één werkwoord via de API):

1. Hoofdscherm toont "🎯 Samen oefenen"; klik erop.
2. `#/samen`: beide hoofdstukken aangevinkt (default alles), tellers kloppen (Woorden (2), Werkwoorden (2)).
3. Vink hoofdstuk 2 uit → teller wordt Woorden (1); herlaad de pagina → selectie is onthouden.
4. Vink alles weer aan, klik "⌨️ Typen" bij Woorden → oefening start op `#/oefen/1,2/woorden/es_nl/typen` en `/api/practice/items` geeft twee woorden; terugknop is "← Samen oefenen".
5. Zonder selectie (alles uitgevinkt): knoppen zijn disabled.

Stop daarna de testinstantie (pkill in een los commando, patroon `'[u]vicorn.*8765'`).

- [ ] **Step 4: Draai de JS-tests (regressie)**

Run: `node --test 'tests/js/*.mjs'`
Expected: alles PASS.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/views/combined.js app/static/js/app.js app/static/js/views/chapters.js
git commit -m "Samen oefenen: selectiescherm voor meerdere hoofdstukken

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
