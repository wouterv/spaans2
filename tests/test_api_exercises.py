import sqlite3

import pytest

from app import db, llm


@pytest.fixture
def chapter_id(client):
    return client.post("/api/chapters", json={"name": "H1"}).json()["id"]


def _insert_exercise(app_instance, chapter_id, **overrides):
    """Testhelper: oefening direct in de database zetten."""
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


def _stats(app_instance):
    conn = db.connect(app_instance.state.db_path)
    try:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT item_type, item_id, direction, correct, wrong "
                "FROM practice_stats"
            )
        ]
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


class TestLijst:
    def test_lijst_geeft_oefeningen_met_geparste_options(
        self, client, app_instance, chapter_id
    ):
        _insert_exercise(
            app_instance, chapter_id,
            type="meerkeuze", options='["soy", "eres", "es"]',
        )
        exercises = client.get(f"/api/exercises?chapter_id={chapter_id}").json()
        assert len(exercises) == 1
        assert exercises[0]["options"] == ["soy", "eres", "es"]
        assert exercises[0]["prompt"] == "Yo ___ de Países Bajos."

    def test_options_null_zonder_meerkeuze(self, client, app_instance, chapter_id):
        _insert_exercise(app_instance, chapter_id)
        exercises = client.get(f"/api/exercises?chapter_id={chapter_id}").json()
        assert exercises[0]["options"] is None

    def test_weggestemde_oefening_staat_niet_in_de_lijst(
        self, client, app_instance, chapter_id
    ):
        exercise_id = _insert_exercise(app_instance, chapter_id)
        assert client.post(f"/api/exercises/{exercise_id}/disable").status_code == 204
        assert client.get(f"/api/exercises?chapter_id={chapter_id}").json() == []

    def test_wegstemmen_onbekende_oefening_is_404(self, client):
        assert client.post("/api/exercises/999/disable").status_code == 404


class TestCheck:
    def test_goed_antwoord(self, client, app_instance, chapter_id):
        exercise_id = _insert_exercise(app_instance, chapter_id, answer="soy")
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "soy"}
        ).json()
        assert result["result"] == "correct"
        assert result["explanation"] == "Bij 'yo' hoort 'soy'."

    def test_accentfout_blijft_soepel(self, client, app_instance, chapter_id):
        exercise_id = _insert_exercise(app_instance, chapter_id, answer="está")
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "esta"}
        ).json()
        assert result["result"] == "correct_accent"

    def test_fout_antwoord_update_statistiek(self, client, app_instance, chapter_id):
        exercise_id = _insert_exercise(app_instance, chapter_id, answer="soy")
        client.post(f"/api/exercises/{exercise_id}/check", json={"answer": "eres"})
        stats = _stats(app_instance)
        assert stats == [
            {
                "item_type": "exercise",
                "item_id": exercise_id,
                "direction": "invullen",
                "correct": 0,
                "wrong": 1,
            }
        ]

    def test_onbekende_oefening_is_404(self, client):
        assert (
            client.post("/api/exercises/999/check", json={"answer": "x"}).status_code
            == 404
        )


class TestVertalenMetLLM:
    def _vertaling(self, app_instance, chapter_id):
        return _insert_exercise(
            app_instance, chapter_id,
            type="vertalen",
            instruction="Vertaal naar het Spaans",
            prompt="Ik ben moe.",
            answer="Estoy cansado",
        )

    def test_llm_keurt_alternatieve_vertaling_goed(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)
        monkeypatch.setattr(
            llm, "complete_json",
            lambda **kwargs: {"correct": True, "feedback": ""},
        )
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Estoy cansada"}
        ).json()
        assert result["result"] == "correct"
        assert _stats(app_instance)[0]["correct"] == 1

    def test_llm_afkeuring_geeft_feedback(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)
        monkeypatch.setattr(
            llm, "complete_json",
            lambda **kwargs: {"correct": False, "feedback": "Gebruik 'estar' bij een tijdelijke toestand."},
        )
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Soy cansado"}
        ).json()
        assert result["result"] == "wrong"
        assert "estar" in result["feedback"]

    def test_lokaal_goed_antwoord_slaat_llm_over(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)

        def boom(**kwargs):
            raise AssertionError("LLM hoort niet aangeroepen te worden")

        monkeypatch.setattr(llm, "complete_json", boom)
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Estoy cansado"}
        ).json()
        assert result["result"] == "correct"

    def test_llm_storing_valt_terug_op_lokale_check(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)

        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": "Estoy cansada"}
        ).json()
        assert result["result"] == "wrong"
        assert result["feedback"] == ""

    def test_leeg_antwoord_gaat_niet_naar_de_llm(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._vertaling(app_instance, chapter_id)

        def boom(**kwargs):
            raise AssertionError("LLM hoort niet aangeroepen te worden")

        monkeypatch.setattr(llm, "complete_json", boom)
        result = client.post(
            f"/api/exercises/{exercise_id}/check", json={"answer": ""}
        ).json()
        assert result["result"] == "wrong"


@pytest.fixture
def chapter_met_lesstof(client, chapter_id):
    client.post("/api/grammar", json={
        "chapter_id": chapter_id,
        "title": "Ser en estar",
        "explanation": "Ser voor blijvend, estar voor tijdelijk.",
        "examples": [{"spanish": "Estoy cansado", "dutch": "Ik ben moe"}],
    })
    client.post("/api/words", json={
        "chapter_id": chapter_id, "spanish": "cansado", "dutch": "moe",
    })
    return chapter_id


def _gegenereerde_oefening(**overrides):
    exercise = {
        "type": "invullen",
        "instruction": "Vul de juiste vorm van 'estar' in",
        "prompt": "Yo ___ cansado.",
        "answer": "estoy",
        "options": [],
        "explanation": "Tijdelijke toestand: estar.",
    }
    exercise.update(overrides)
    return exercise


class TestGenereren:
    def test_genereert_en_slaat_op(
        self, client, app_instance, chapter_met_lesstof, monkeypatch
    ):
        prompts = []

        def fake(**kwargs):
            prompts.append(kwargs)
            return {"exercises": [
                _gegenereerde_oefening(),
                _gegenereerde_oefening(
                    type="meerkeuze", prompt="Tú ___ cansado.",
                    options=["estás", "eres"], answer="estás",
                ),
            ]}

        monkeypatch.setattr(llm, "complete_json", fake)
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.status_code == 200
        assert response.json() == {"created": 2, "skipped": 0}
        exercises = client.get(
            f"/api/exercises?chapter_id={chapter_met_lesstof}"
        ).json()
        assert len(exercises) == 2
        assert exercises[1]["options"] == ["estás", "eres"]
        # De lesstof staat in de prompt naar de LLM
        content = prompts[0]["messages"][0]["content"]
        assert "Ser en estar" in content
        assert "cansado" in content

    def test_ongeldige_meerkeuze_wordt_overgeslagen(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"exercises": [
            _gegenereerde_oefening(),
            _gegenereerde_oefening(
                type="meerkeuze", options=["soy"], answer="estoy",
            ),
        ]})
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.json() == {"created": 1, "skipped": 0}

    def test_meerkeuze_options_worden_gestript_opgeslagen(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"exercises": [
            _gegenereerde_oefening(
                type="meerkeuze", options=[" estás ", "está", ""], answer="estás",
            ),
        ]})
        client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        exercises = client.get(
            f"/api/exercises?chapter_id={chapter_met_lesstof}"
        ).json()
        assert exercises[0]["options"] == ["estás", "está"]

    def test_hoofdstuk_zonder_grammatica_is_400(self, client, chapter_id):
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_id}
        )
        assert response.status_code == 400

    def test_onbekend_hoofdstuk_is_404(self, client):
        assert (
            client.post(
                "/api/exercises/generate", json={"chapter_id": 999}
            ).status_code
            == 404
        )

    def test_llm_storing_is_503_met_nederlandse_melding(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Geen verbinding met de taaldienst"

    def test_geen_bruikbare_oefeningen_is_502(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        monkeypatch.setattr(
            llm, "complete_json", lambda **kwargs: {"exercises": []}
        )
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.status_code == 502


class TestHerschrijvenMetLLM:
    def _herschrijf(self, app_instance, chapter_id):
        return _insert_exercise(
            app_instance, chapter_id,
            type="herschrijven",
            instruction="Zet om naar meervoud",
            prompt="Esta es Catherine, mi hermana.",
            answer="Estas son Catherine y Uma, mis hermanas",
        )

    def test_llm_keurt_gelijkwaardig_antwoord_goed(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._herschrijf(app_instance, chapter_id)
        aanroepen = []

        def fake(**kwargs):
            aanroepen.append(kwargs)
            return {"correct": True, "feedback": ""}

        monkeypatch.setattr(llm, "complete_json", fake)
        result = client.post(
            f"/api/exercises/{exercise_id}/check",
            json={"answer": "Estas son Catherine y Emma, mis hermanas"},
        ).json()
        assert result["result"] == "correct"
        # De opdracht gaat mee naar de LLM, anders is het antwoord niet te beoordelen
        assert "Zet om naar meervoud" in aanroepen[0]["messages"][0]["content"]

    def test_lokaal_goed_antwoord_slaat_llm_over(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._herschrijf(app_instance, chapter_id)

        def boom(**kwargs):
            raise AssertionError("LLM hoort niet aangeroepen te worden")

        monkeypatch.setattr(llm, "complete_json", boom)
        result = client.post(
            f"/api/exercises/{exercise_id}/check",
            json={"answer": "Estas son Catherine y Uma, mis hermanas"},
        ).json()
        assert result["result"] == "correct"

    def test_llm_storing_valt_terug_op_lokale_check(
        self, client, app_instance, chapter_id, monkeypatch
    ):
        exercise_id = self._herschrijf(app_instance, chapter_id)

        def storing(**kwargs):
            raise llm.LLMError("Geen verbinding met de taaldienst")

        monkeypatch.setattr(llm, "complete_json", storing)
        result = client.post(
            f"/api/exercises/{exercise_id}/check",
            json={"answer": "Estas son Catherine y Emma, mis hermanas"},
        ).json()
        assert result["result"] == "wrong"


class TestGeneratieprompt:
    def test_eist_afleidbaar_antwoord(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        prompts = []

        def fake(**kwargs):
            prompts.append(kwargs)
            return {"exercises": [_gegenereerde_oefening()]}

        monkeypatch.setattr(llm, "complete_json", fake)
        client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert "afleidbaar" in prompts[0]["system"]

    def test_alleen_voorbeeldoefeningen_is_genoeg(
        self, client, chapter_id, monkeypatch
    ):
        client.post("/api/examples", json={
            "chapter_id": chapter_id, "text": "Completa: Yo ___ (ser) de Holanda.",
        })
        prompts = []

        def fake(**kwargs):
            prompts.append(kwargs)
            return {"exercises": [_gegenereerde_oefening()]}

        monkeypatch.setattr(llm, "complete_json", fake)
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_id}
        )
        assert response.status_code == 200
        # De voorbeelden zitten in de prompt en de stijl-instructie in de systeemprompt
        assert "Completa: Yo ___" in prompts[0]["messages"][0]["content"]
        assert "kopieer ze niet letterlijk" in prompts[0]["system"]


class TestDubbelen:
    def test_bestaande_oefeningen_gaan_mee_in_de_prompt(
        self, client, app_instance, chapter_met_lesstof, monkeypatch
    ):
        _insert_exercise(app_instance, chapter_met_lesstof, prompt="Yo ___ cansado.", answer="estoy")
        weggestemd = _insert_exercise(
            app_instance, chapter_met_lesstof, prompt="Tú ___ cansado.", answer="estás",
        )
        client.post(f"/api/exercises/{weggestemd}/disable")
        prompts = []

        def fake(**kwargs):
            prompts.append(kwargs)
            return {"exercises": [_gegenereerde_oefening()]}

        monkeypatch.setattr(llm, "complete_json", fake)
        client.post("/api/exercises/generate", json={"chapter_id": chapter_met_lesstof})
        content = prompts[0]["messages"][0]["content"]
        assert "Yo ___ cansado." in content
        # Ook weggestemde oefeningen tellen mee: die wil je niet opnieuw krijgen
        assert "Tú ___ cansado." in content
        assert "bestaan al" in content

    def test_zonder_bestaande_oefeningen_geen_lijstje(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        prompts = []

        def fake(**kwargs):
            prompts.append(kwargs)
            return {"exercises": [_gegenereerde_oefening()]}

        monkeypatch.setattr(llm, "complete_json", fake)
        client.post("/api/exercises/generate", json={"chapter_id": chapter_met_lesstof})
        assert "bestaan al" not in prompts[0]["messages"][0]["content"]

    def test_dubbele_wordt_overgeslagen(
        self, client, app_instance, chapter_met_lesstof, monkeypatch
    ):
        _insert_exercise(
            app_instance, chapter_met_lesstof,
            prompt="Yo ___ cansado.", answer="estoy",
        )
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"exercises": [
            # Zelfde prompt+antwoord, andere hoofdletters/spaties: toch dubbel
            _gegenereerde_oefening(prompt="  yo ___ CANSADO. ", answer="Estoy"),
            _gegenereerde_oefening(prompt="Nosotros ___ en casa.", answer="estamos"),
        ]})
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.json() == {"created": 1, "skipped": 1}
        exercises = client.get(
            f"/api/exercises?chapter_id={chapter_met_lesstof}"
        ).json()
        assert len(exercises) == 2  # 1 bestaande + 1 nieuwe

    def test_dubbele_binnen_een_batch_wordt_overgeslagen(
        self, client, chapter_met_lesstof, monkeypatch
    ):
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"exercises": [
            _gegenereerde_oefening(prompt="Yo ___ cansado.", answer="estoy"),
            _gegenereerde_oefening(prompt="Yo ___ cansado.", answer="estoy"),
        ]})
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.json() == {"created": 1, "skipped": 1}

    def test_alles_dubbel_is_502(
        self, client, app_instance, chapter_met_lesstof, monkeypatch
    ):
        _insert_exercise(
            app_instance, chapter_met_lesstof,
            prompt="Yo ___ cansado.", answer="estoy",
        )
        monkeypatch.setattr(llm, "complete_json", lambda **kwargs: {"exercises": [
            _gegenereerde_oefening(prompt="Yo ___ cansado.", answer="estoy"),
        ]})
        response = client.post(
            "/api/exercises/generate", json={"chapter_id": chapter_met_lesstof}
        )
        assert response.status_code == 502
        assert "bestaande" in response.json()["detail"]
