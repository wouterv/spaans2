import pytest


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


class TestExamples:
    def test_aanmaken_en_lijst(self, client, chapter_id):
        response = client.post("/api/examples", json={
            "chapter_id": chapter_id,
            "text": "Completa: Yo ___ (ser) de Holanda.",
        })
        assert response.status_code == 201
        example_id = response.json()["id"]
        examples = client.get(f"/api/examples?chapter_id={chapter_id}").json()
        assert examples == [{
            "id": example_id,
            "chapter_id": chapter_id,
            "text": "Completa: Yo ___ (ser) de Holanda.",
        }]

    def test_tekst_wordt_gestript(self, client, chapter_id):
        client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "  Traduce: ik ben moe.  ",
        })
        examples = client.get(f"/api/examples?chapter_id={chapter_id}").json()
        assert examples[0]["text"] == "Traduce: ik ben moe."

    def test_lege_tekst_is_422(self, client, chapter_id):
        response = client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "",
        })
        assert response.status_code == 422

    def test_onbekend_hoofdstuk_is_404(self, client):
        response = client.post("/api/examples", json={
            "chapter_id": 999, "text": "Completa: ___",
        })
        assert response.status_code == 404

    def test_verwijderen(self, client, chapter_id):
        example_id = client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "Completa: ___",
        }).json()["id"]
        assert client.delete(f"/api/examples/{example_id}").status_code == 204
        assert client.get(f"/api/examples?chapter_id={chapter_id}").json() == []

    def test_verwijderen_onbekend_is_404(self, client):
        assert client.delete("/api/examples/999").status_code == 404

    def test_hoofdstuk_verwijderen_verwijdert_voorbeelden(self, client, app_instance, chapter_id):
        from app import db

        client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "Completa: ___",
        })
        client.delete(f"/api/chapters/{chapter_id}")
        conn = db.connect(app_instance.state.db_path)
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM example_exercises"
            ).fetchone()["n"]
        finally:
            conn.close()
        assert count == 0
