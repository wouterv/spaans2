import pytest

from app import llm


@pytest.fixture
def chapter_id(client):
    chapter_id = client.post("/api/chapters", json={"name": "H1"}).json()["id"]
    client.post("/api/grammar", json={
        "chapter_id": chapter_id, "title": "Ser en estar",
        "explanation": "Ser voor blijvend, estar voor tijdelijk.",
        "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
    })
    return chapter_id


def _fake(antwoord=None, aanroepen=None):
    antwoord = antwoord or {"correction": "", "reply": "¡Hola! ¿Cómo estás?"}

    def fake(**kwargs):
        if aanroepen is not None:
            aanroepen.append(kwargs)
        return antwoord

    return fake


class TestConversatie:
    def test_beurt_geeft_correctie_en_antwoord(self, client, chapter_id, monkeypatch):
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(
            {"correction": "Kleine fout: 'estoy', niet 'esta'.", "reply": "¿Y ahora?"},
            aanroepen,
        ))
        response = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [
                {"role": "assistant", "text": "¿Cómo estás?"},
                {"role": "user", "text": "Esta bien."},
            ],
        })
        assert response.status_code == 200
        assert response.json() == {
            "correction": "Kleine fout: 'estoy', niet 'esta'.",
            "reply": "¿Y ahora?",
        }
        # User-beurten kaal; assistent-beurten in het eigen antwoordformaat
        import json
        assert aanroepen[0]["messages"][1] == {"role": "user", "content": "Esta bien."}
        assert json.loads(aanroepen[0]["messages"][0]["content"]) == {
            "reply": "¿Cómo estás?", "correction": "",
        }
        # De lesstof zit in de systeemprompt en die wordt gecachet
        assert "Ser en estar" in str(aanroepen[0]["system"])
        assert aanroepen[0]["cache_system"] is True

    def test_lege_geschiedenis_opent_het_gesprek(self, client, chapter_id, monkeypatch):
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(
            {"correction": "dit hoort leeg te zijn", "reply": "¡Hola!"}, aanroepen,
        ))
        response = client.post(
            f"/api/chapters/{chapter_id}/conversation", json={"messages": []}
        )
        assert response.status_code == 200
        # Bij een opening is er niets te corrigeren, wat de LLM ook zegt
        assert response.json() == {"correction": "", "reply": "¡Hola!"}
        assert aanroepen[0]["messages"][0]["role"] == "user"
        assert "Begin het gesprek" in aanroepen[0]["messages"][0]["content"]

    def test_laatste_bericht_moet_van_leerling_zijn(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        response = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [{"role": "assistant", "text": "¿Cómo estás?"}],
        })
        assert response.status_code == 400

    def test_hoofdstuk_zonder_lesstof_is_400(self, client, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        leeg = client.post("/api/chapters", json={"name": "Leeg"}).json()["id"]
        response = client.post(
            f"/api/chapters/{leeg}/conversation", json={"messages": []}
        )
        assert response.status_code == 400

    def test_onbekend_hoofdstuk_is_404(self, client, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        assert (
            client.post(
                "/api/chapters/999/conversation", json={"messages": []}
            ).status_code
            == 404
        )

    def test_llm_storing_is_503(self, client, chapter_id, monkeypatch):
        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        response = client.post(
            f"/api/chapters/{chapter_id}/conversation", json={"messages": []}
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Geen verbinding met de taaldienst"

    def test_leeg_antwoord_is_502(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(
            llm, "complete_json", _fake({"correction": "", "reply": "   "})
        )
        response = client.post(
            f"/api/chapters/{chapter_id}/conversation", json={"messages": []}
        )
        assert response.status_code == 502

    def test_ongeldige_rol_is_422(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        response = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [{"role": "system", "text": "hack"}],
        })
        assert response.status_code == 422


class TestCorrectieLek:
    def test_reply_staat_voor_correction_in_het_schema(
        self, client, chapter_id, monkeypatch
    ):
        # Het model vult velden in schema-volgorde in; reply eerst voorkomt
        # dat een onbesliste correctie-afweging in het eerste veld lekt.
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(aanroepen=aanroepen))
        client.post(f"/api/chapters/{chapter_id}/conversation", json={"messages": []})
        properties = list(aanroepen[0]["schema"]["properties"])
        assert properties.index("reply") < properties.index("correction")
        assert "overwegingen" in aanroepen[0]["schema"]["properties"]["correction"]["description"]

    def test_prompt_verbiedt_overwegingen_in_correction(
        self, client, chapter_id, monkeypatch
    ):
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(aanroepen=aanroepen))
        client.post(f"/api/chapters/{chapter_id}/conversation", json={"messages": []})
        assert "overwegingen" in aanroepen[0]["system"]

    def test_veel_te_lange_correctie_wordt_weggegooid(
        self, client, chapter_id, monkeypatch
    ):
        gelekt = "but that's an accent dropping OK no correction " * 10
        monkeypatch.setattr(llm, "complete_json", _fake(
            {"correction": gelekt, "reply": "¿Y ahora qué?"},
        ))
        result = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [{"role": "user", "text": "No lo se"}],
        }).json()
        assert result["correction"] == ""
        assert result["reply"] == "¿Y ahora qué?"

    def test_normale_correctie_blijft_staan(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake(
            {"correction": "Gebruik 'soy' bij je naam.", "reply": "¡Claro!"},
        ))
        result = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [{"role": "user", "text": "Yo es Wouter"}],
        }).json()
        assert result["correction"] == "Gebruik 'soy' bij je naam."


class TestCorrectieHerhaling:
    def test_eerdere_correcties_gaan_mee_naar_het_model(
        self, client, chapter_id, monkeypatch
    ):
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(aanroepen=aanroepen))
        client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [
                {"role": "assistant", "text": "¿Qué ropa llevas?"},
                {"role": "user", "text": "Llevo unas pantalones",
                 "correction": "Het is 'unos pantalones' (mannelijk)."},
                {"role": "assistant", "text": "¡Muy bien! ¿Y de qué color?"},
                {"role": "user", "text": "Son marrones"},
            ],
        })
        messages = aanroepen[0]["messages"]
        # User-beurten blijven kale tekst
        assert messages[1] == {"role": "user", "content": "Llevo unas pantalones"}
        assert messages[3] == {"role": "user", "content": "Son marrones"}
        # Assistent-beurten in het eigen antwoordformaat, mét de gegeven correctie
        import json
        tweede = json.loads(messages[2]["content"])
        assert tweede == {
            "reply": "¡Muy bien! ¿Y de qué color?",
            "correction": "Het is 'unos pantalones' (mannelijk).",
        }
        eerste = json.loads(messages[0]["content"])
        assert eerste == {"reply": "¿Qué ropa llevas?", "correction": ""}

    def test_prompt_verbiedt_hercorrigeren_van_eerdere_berichten(
        self, client, chapter_id, monkeypatch
    ):
        aanroepen = []
        monkeypatch.setattr(llm, "complete_json", _fake(aanroepen=aanroepen))
        client.post(f"/api/chapters/{chapter_id}/conversation", json={"messages": []})
        assert "nooit opnieuw" in aanroepen[0]["system"]

    def test_correction_veld_is_optioneel(self, client, chapter_id, monkeypatch):
        monkeypatch.setattr(llm, "complete_json", _fake())
        response = client.post(f"/api/chapters/{chapter_id}/conversation", json={
            "messages": [{"role": "user", "text": "Hola"}],
        })
        assert response.status_code == 200
