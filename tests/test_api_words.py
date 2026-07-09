import pytest


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def test_create_and_list_word(client, chapter_id):
    response = client.post(
        "/api/words",
        json={"chapter_id": chapter_id, "spanish": "la casa", "dutch": "het huis"},
    )
    assert response.status_code == 201
    words = client.get(f"/api/words?chapter_id={chapter_id}").json()
    assert len(words) == 1
    assert words[0]["spanish"] == "la casa"
    assert words[0]["dutch"] == "het huis"


def test_words_are_filtered_by_chapter(client, chapter_id):
    other = client.post("/api/chapters", json={"name": "H2"}).json()["id"]
    client.post(
        "/api/words",
        json={"chapter_id": chapter_id, "spanish": "uno", "dutch": "een"},
    )
    client.post(
        "/api/words", json={"chapter_id": other, "spanish": "dos", "dutch": "twee"}
    )
    assert len(client.get(f"/api/words?chapter_id={chapter_id}").json()) == 1
    assert len(client.get(f"/api/words?chapter_id={other}").json()) == 1


def test_update_word(client, chapter_id):
    word_id = client.post(
        "/api/words",
        json={"chapter_id": chapter_id, "spanish": "kasa", "dutch": "huis"},
    ).json()["id"]
    response = client.put(
        f"/api/words/{word_id}", json={"spanish": "casa", "dutch": "huis"}
    )
    assert response.status_code == 200
    words = client.get(f"/api/words?chapter_id={chapter_id}").json()
    assert words[0]["spanish"] == "casa"


def test_delete_word(client, chapter_id):
    word_id = client.post(
        "/api/words",
        json={"chapter_id": chapter_id, "spanish": "sol", "dutch": "zon"},
    ).json()["id"]
    assert client.delete(f"/api/words/{word_id}").status_code == 204
    assert client.get(f"/api/words?chapter_id={chapter_id}").json() == []


def test_word_in_missing_chapter_is_404(client):
    response = client.post(
        "/api/words", json={"chapter_id": 999, "spanish": "x", "dutch": "y"}
    )
    assert response.status_code == 404


def test_update_missing_word_is_404(client):
    response = client.put("/api/words/999", json={"spanish": "x", "dutch": "y"})
    assert response.status_code == 404


def test_empty_fields_are_rejected(client, chapter_id):
    response = client.post(
        "/api/words", json={"chapter_id": chapter_id, "spanish": "", "dutch": "y"}
    )
    assert response.status_code == 422
