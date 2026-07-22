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
