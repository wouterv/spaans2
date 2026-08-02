def test_list_starts_empty(client):
    response = client.get("/api/chapters")
    assert response.status_code == 200
    assert response.json() == []


def test_create_chapter(client):
    response = client.post("/api/chapters", json={"name": "Hoofdstuk 1"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Hoofdstuk 1"
    assert body["id"] > 0


def test_chapters_keep_creation_order(client):
    client.post("/api/chapters", json={"name": "Uno"})
    client.post("/api/chapters", json={"name": "Dos"})
    names = [c["name"] for c in client.get("/api/chapters").json()]
    assert names == ["Uno", "Dos"]


def test_chapter_includes_counts(client):
    chapter_id = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
    client.post(
        "/api/words",
        json={"chapter_id": chapter_id, "spanish": "casa", "dutch": "huis"},
    )
    chapter = client.get("/api/chapters").json()[0]
    assert chapter["word_count"] == 1
    assert chapter["verb_count"] == 0
    assert chapter["grammar_count"] == 0


def test_rename_chapter(client):
    chapter_id = client.post("/api/chapters", json={"name": "Oud"}).json()["id"]
    response = client.put(f"/api/chapters/{chapter_id}", json={"name": "Nieuw"})
    assert response.status_code == 200
    assert client.get("/api/chapters").json()[0]["name"] == "Nieuw"


def test_rename_missing_chapter_is_404(client):
    assert client.put("/api/chapters/999", json={"name": "X"}).status_code == 404


def test_delete_chapter_cascades(client):
    chapter_id = client.post("/api/chapters", json={"name": "Weg"}).json()["id"]
    client.post(
        "/api/words",
        json={"chapter_id": chapter_id, "spanish": "sol", "dutch": "zon"},
    )
    assert client.delete(f"/api/chapters/{chapter_id}").status_code == 204
    assert client.get("/api/chapters").json() == []
    assert client.get(f"/api/words?chapter_id={chapter_id}").json() == []


def test_empty_name_is_rejected(client):
    assert client.post("/api/chapters", json={"name": ""}).status_code == 422


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


def test_chapter_telt_voorbeeldoefeningen(client):
    chapter_id = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
    client.post("/api/examples", json={
        "chapter_id": chapter_id, "text": "Completa: ___",
    })
    chapter = client.get("/api/chapters").json()[0]
    assert chapter["example_count"] == 1


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
