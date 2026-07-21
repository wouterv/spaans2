import sqlite3

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


@pytest.fixture
def word_id(client, chapter_id):
    return client.post(
        "/api/words",
        json={"chapter_id": chapter_id, "spanish": "cómo", "dutch": "hoe"},
    ).json()["id"]


@pytest.fixture
def verb_id(client, chapter_id):
    return client.post(
        "/api/verbs",
        json={
            "chapter_id": chapter_id,
            "infinitive_es": "hablar",
            "translation_nl": "praten",
            "tense": "presente",
            "forms": FORMS,
        },
    ).json()["id"]


def test_practice_items_words(client, chapter_id, word_id):
    items = client.get(
        f"/api/practice/items?chapter_id={chapter_id}&type=words"
    ).json()
    assert len(items) == 1
    assert items[0]["spanish"] == "cómo"
    assert items[0]["dutch"] == "hoe"


def test_practice_items_verbs(client, chapter_id, verb_id):
    items = client.get(
        f"/api/practice/items?chapter_id={chapter_id}&type=verbs"
    ).json()
    assert len(items) == 1
    assert items[0]["conjugations"]["presente"]["yo"] == "hablo"


def test_check_word_correct(client, word_id):
    response = client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": word_id,
            "direction": "es_nl",
            "answer": "hoe",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "correct"
    assert body["correct_answer"] == "hoe"


def test_check_word_wrong(client, word_id):
    body = client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": word_id,
            "direction": "nl_es",
            "answer": "casa",
        },
    ).json()
    assert body["result"] == "wrong"
    assert body["correct_answer"] == "cómo"


def test_check_word_accent_hint(client, word_id):
    body = client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": word_id,
            "direction": "nl_es",
            "answer": "como",
        },
    ).json()
    assert body["result"] == "correct_accent"
    assert body["matched"] == "cómo"


def test_check_word_gender_pair_both_directions(client, chapter_id):
    word_id = client.post(
        "/api/words",
        json={
            "chapter_id": chapter_id,
            "spanish": "el primo/la prima",
            "dutch": "de neef/de nicht",
        },
    ).json()["id"]

    body = client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": word_id,
            "direction": "es_nl",
            "answer": "de nicht",
        },
    ).json()
    assert body["result"] == "correct"
    assert body["correct_answer"] == "de neef/de nicht"

    body = client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": word_id,
            "direction": "nl_es",
            "answer": "la prima",
        },
    ).json()
    assert body["result"] == "correct"


def test_check_verb_form(client, verb_id):
    body = client.post(
        "/api/practice/check",
        json={
            "item_type": "verb",
            "item_id": verb_id,
            "direction": "conjugation",
            "tense": "presente",
            "person": "yo",
            "answer": "hablo",
        },
    ).json()
    assert body["result"] == "correct"

    body = client.post(
        "/api/practice/check",
        json={
            "item_type": "verb",
            "item_id": verb_id,
            "direction": "conjugation",
            "tense": "presente",
            "person": "tu",
            "answer": "hablo",
        },
    ).json()
    assert body["result"] == "wrong"
    assert body["correct_answer"] == "hablas"


def test_check_updates_stats(app_instance, client, word_id):
    for answer in ["hoe", "hoe", "fout"]:
        client.post(
            "/api/practice/check",
            json={
                "item_type": "word",
                "item_id": word_id,
                "direction": "es_nl",
                "answer": answer,
            },
        )
    conn = sqlite3.connect(app_instance.state.db_path)
    row = conn.execute(
        "SELECT correct, wrong, last_practiced_at FROM practice_stats "
        "WHERE item_type = 'word' AND item_id = ? AND direction = 'es_nl'",
        (word_id,),
    ).fetchone()
    conn.close()
    assert row == (2, 1, row[2])
    assert row[2] is not None


def test_accent_hint_counts_as_correct_in_stats(app_instance, client, word_id):
    client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": word_id,
            "direction": "nl_es",
            "answer": "como",
        },
    )
    conn = sqlite3.connect(app_instance.state.db_path)
    row = conn.execute(
        "SELECT correct, wrong FROM practice_stats "
        "WHERE item_type = 'word' AND item_id = ? AND direction = 'nl_es'",
        (word_id,),
    ).fetchone()
    conn.close()
    assert row == (1, 0)


def test_check_missing_item_is_404(client):
    response = client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": 999,
            "direction": "es_nl",
            "answer": "x",
        },
    )
    assert response.status_code == 404


def test_check_verb_requires_person(client, verb_id):
    response = client.post(
        "/api/practice/check",
        json={
            "item_type": "verb",
            "item_id": verb_id,
            "direction": "conjugation",
            "answer": "hablo",
        },
    )
    assert response.status_code == 422


def test_check_with_alternatives_picks_best(app_instance, client, word_id):
    # Spraakherkenning geeft meerdere kandidaten; de beste telt, stats één keer
    body = client.post(
        "/api/practice/check",
        json={
            "item_type": "word",
            "item_id": word_id,
            "direction": "nl_es",
            "answer": "koe mo",
            "alternatives": ["cómo", "komo"],
        },
    ).json()
    assert body["result"] == "correct"

    import sqlite3

    conn = sqlite3.connect(app_instance.state.db_path)
    row = conn.execute(
        "SELECT correct, wrong FROM practice_stats "
        "WHERE item_type = 'word' AND item_id = ? AND direction = 'nl_es'",
        (word_id,),
    ).fetchone()
    conn.close()
    assert row == (1, 0)
