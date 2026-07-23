import base64

import pytest

from app import llm
from app.routers import lessons

GELDIGE_DATA = base64.b64encode(b"nep-afbeelding-bytes").decode()


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def _body(n=1, media_type="image/jpeg", data=GELDIGE_DATA):
    return {"images": [{"media_type": media_type, "data": data}] * n}


def _regel(**overrides):
    regel = {
        "title": "Ser en estar",
        "explanation": "Ser voor blijvend, estar voor tijdelijk.",
        "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
    }
    regel.update(overrides)
    return regel


class TestExtract:
    def test_geeft_regels_terug_en_slaat_niets_op(
        self, client, chapter_id, monkeypatch
    ):
        aanroepen = []

        def fake(**kwargs):
            aanroepen.append(kwargs)
            return {"rules": [_regel()]}

        monkeypatch.setattr(llm, "complete_json", fake)
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body(n=2)
        )
        assert response.status_code == 200
        assert response.json() == {"rules": [_regel()]}
        # De afbeeldingen zitten als image-content-blocks in het bericht
        content = aanroepen[0]["messages"][0]["content"]
        image_blocks = [b for b in content if b["type"] == "image"]
        assert len(image_blocks) == 2
        assert image_blocks[0]["source"] == {
            "type": "base64", "media_type": "image/jpeg", "data": GELDIGE_DATA,
        }
        assert content[-1]["type"] == "text"
        # Er is niets in de database beland
        assert client.get(f"/api/grammar?chapter_id={chapter_id}").json() == []

    def test_lege_titel_en_leeg_voorbeeld_worden_gefilterd(
        self, client, chapter_id, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"rules": [
            _regel(),
            _regel(title="   "),
            _regel(examples=[
                {"spanish": "  ", "dutch": "leeg"},
                {"spanish": "Soy Wouter", "dutch": "Ik ben Wouter"},
            ]),
        ]})
        rules = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        ).json()["rules"]
        assert len(rules) == 2
        assert rules[1]["examples"] == [
            {"spanish": "Soy Wouter", "dutch": "Ik ben Wouter"}
        ]

    def test_onbekend_hoofdstuk_is_404(self, client, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"rules": []})
        assert (
            client.post("/api/chapters/999/lessons/extract", json=_body()).status_code
            == 404
        )

    def test_zonder_afbeeldingen_is_422(self, client, chapter_id):
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json={"images": []}
        )
        assert response.status_code == 422

    def test_verkeerd_bestandstype_is_422(self, client, chapter_id):
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract",
            json=_body(media_type="application/pdf"),
        )
        assert response.status_code == 422

    def test_ongeldige_base64_is_400(self, client, chapter_id):
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract",
            json=_body(data="dit is geen base64!!!"),
        )
        assert response.status_code == 400

    def test_te_grote_afbeelding_is_400(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(lessons, "MAX_IMAGE_BYTES", 4)
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 400
        assert "te groot" in response.json()["detail"]

    def test_llm_storing_is_503(self, client, chapter_id, monkeypatch):
        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Geen verbinding met de taaldienst"

    def test_geen_regels_herkend_is_502(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"rules": []})
        response = client.post(
            f"/api/chapters/{chapter_id}/lessons/extract", json=_body()
        )
        assert response.status_code == 502
