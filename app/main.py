import os
from pathlib import Path

from fastapi import FastAPI

from app import db

DEFAULT_DB = Path(__file__).parent.parent / "data" / "spaans.db"


def create_app(db_path=None):
    db_path = Path(db_path or os.environ.get("SPAANS_DB", DEFAULT_DB))
    db.migrate(db_path)

    app = FastAPI(title="Spaans")
    app.state.db_path = db_path

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


def get_default_app():
    return create_app()
