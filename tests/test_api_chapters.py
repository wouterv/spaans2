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
