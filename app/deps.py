from fastapi import Request

from app import db


def get_conn(request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def chapter_or_404(conn, chapter_id):
    from fastapi import HTTPException

    row = conn.execute(
        "SELECT id FROM chapters WHERE id = ?", (chapter_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Hoofdstuk niet gevonden")
