def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_migrations_create_tables(app_instance):
    import sqlite3

    conn = sqlite3.connect(app_instance.state.db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    conn.close()
    expected = {
        "chapters",
        "words",
        "verbs",
        "conjugations",
        "grammar_rules",
        "grammar_examples",
        "practice_stats",
    }
    assert expected <= tables


def test_migrations_are_idempotent(tmp_path):
    from app.main import create_app

    db_path = tmp_path / "twice.db"
    create_app(db_path=db_path)
    create_app(db_path=db_path)
