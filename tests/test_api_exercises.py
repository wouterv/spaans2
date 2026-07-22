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
