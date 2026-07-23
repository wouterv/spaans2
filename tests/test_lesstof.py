import pytest

from app import db
from app.lesstof import lesson_context


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def _context(app_instance, chapter_id):
    conn = db.connect(app_instance.state.db_path)
    try:
        return lesson_context(conn, chapter_id)
    finally:
        conn.close()


class TestLessonContext:
    def test_leeg_hoofdstuk_geeft_lege_string(self, client, app_instance, chapter_id):
        assert _context(app_instance, chapter_id) == ""

    def test_alle_secties_gevuld(self, client, app_instance, chapter_id):
        client.post("/api/grammar", json={
            "chapter_id": chapter_id, "title": "Ser en estar",
            "explanation": "Ser voor blijvend.",
            "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
        })
        client.post("/api/words", json={
            "chapter_id": chapter_id, "spanish": "cansado", "dutch": "moe",
        })
        client.post("/api/verbs", json={
            "chapter_id": chapter_id, "infinitive_es": "estar",
            "translation_nl": "zijn",
            "forms": {"yo": "estoy", "tu": "estás", "el": "está",
                      "nosotros": "estamos", "vosotros": "estáis",
                      "ellos": "están"},
        })
        context = _context(app_instance, chapter_id)
        assert "Grammaticaregels:" in context
        assert "## Ser en estar" in context
        assert "- Estoy cansado — Ik ben moe" in context
        assert "Woordenschat:" in context
        assert "- cansado — moe" in context
        assert "Werkwoorden:" in context
        assert "- estar — zijn" in context

    def test_alleen_woorden_geen_grammatica_kop(self, client, app_instance, chapter_id):
        client.post("/api/words", json={
            "chapter_id": chapter_id, "spanish": "sol", "dutch": "zon",
        })
        context = _context(app_instance, chapter_id)
        assert "Grammaticaregels:" not in context
        assert "Woordenschat:" in context
