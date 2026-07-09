import pytest


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def make_rule(client, chapter_id, **overrides):
    payload = {
        "chapter_id": chapter_id,
        "title": "Lidwoorden",
        "explanation": "el voor mannelijk, la voor vrouwelijk.",
        "examples": [
            {"spanish": "el coche", "dutch": "de auto"},
            {"spanish": "la casa", "dutch": "het huis"},
        ],
    }
    payload.update(overrides)
    return client.post("/api/grammar", json=payload)


def test_create_rule_with_examples(client, chapter_id):
    response = make_rule(client, chapter_id)
    assert response.status_code == 201
    rules = client.get(f"/api/grammar?chapter_id={chapter_id}").json()
    assert len(rules) == 1
    rule = rules[0]
    assert rule["title"] == "Lidwoorden"
    assert [e["spanish"] for e in rule["examples"]] == ["el coche", "la casa"]


def test_rule_without_examples_is_allowed(client, chapter_id):
    response = make_rule(client, chapter_id, examples=[])
    assert response.status_code == 201


def test_update_rule_replaces_examples(client, chapter_id):
    rule_id = make_rule(client, chapter_id).json()["id"]
    response = client.put(
        f"/api/grammar/{rule_id}",
        json={
            "title": "Lidwoorden (update)",
            "explanation": "Nieuw.",
            "examples": [{"spanish": "los coches", "dutch": "de auto's"}],
        },
    )
    assert response.status_code == 200
    rule = client.get(f"/api/grammar?chapter_id={chapter_id}").json()[0]
    assert rule["title"] == "Lidwoorden (update)"
    assert len(rule["examples"]) == 1


def test_delete_rule(client, chapter_id):
    rule_id = make_rule(client, chapter_id).json()["id"]
    assert client.delete(f"/api/grammar/{rule_id}").status_code == 204
    assert client.get(f"/api/grammar?chapter_id={chapter_id}").json() == []


def test_rule_in_missing_chapter_is_404(client):
    assert make_rule(client, 999).status_code == 404
