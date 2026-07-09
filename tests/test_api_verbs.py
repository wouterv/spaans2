import pytest

FORMS = {
    "yo": "hablo",
    "tu": "hablas",
    "el": "habla",
    "nosotros": "hablamos",
    "vosotros": "habláis",
    "ellos": "hablan",
}


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def make_verb(client, chapter_id, **overrides):
    payload = {
        "chapter_id": chapter_id,
        "infinitive_es": "hablar",
        "translation_nl": "praten; spreken",
        "tense": "presente",
        "forms": FORMS,
    }
    payload.update(overrides)
    return client.post("/api/verbs", json=payload)


def test_create_verb_with_conjugations(client, chapter_id):
    response = make_verb(client, chapter_id)
    assert response.status_code == 201
    verbs = client.get(f"/api/verbs?chapter_id={chapter_id}").json()
    assert len(verbs) == 1
    verb = verbs[0]
    assert verb["infinitive_es"] == "hablar"
    assert verb["translation_nl"] == "praten; spreken"
    assert verb["conjugations"]["presente"] == FORMS


def test_all_six_forms_are_required(client, chapter_id):
    incomplete = {k: v for k, v in FORMS.items() if k != "ellos"}
    response = make_verb(client, chapter_id, forms=incomplete)
    assert response.status_code == 422


def test_update_verb_replaces_forms(client, chapter_id):
    verb_id = make_verb(client, chapter_id).json()["id"]
    new_forms = dict(FORMS, yo="charlo")
    response = client.put(
        f"/api/verbs/{verb_id}",
        json={
            "infinitive_es": "hablar",
            "translation_nl": "praten",
            "tense": "presente",
            "forms": new_forms,
        },
    )
    assert response.status_code == 200
    verb = client.get(f"/api/verbs?chapter_id={chapter_id}").json()[0]
    assert verb["conjugations"]["presente"]["yo"] == "charlo"


def test_delete_verb(client, chapter_id):
    verb_id = make_verb(client, chapter_id).json()["id"]
    assert client.delete(f"/api/verbs/{verb_id}").status_code == 204
    assert client.get(f"/api/verbs?chapter_id={chapter_id}").json() == []


def test_verb_in_missing_chapter_is_404(client):
    assert make_verb(client, 999).status_code == 404
