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


def resolve_chapter_ids(conn, chapter_id, chapter_ids):
    """Eén chapter_id óf een kommalijst chapter_ids naar een lijst ids.

    Precies één van beide is verplicht (422), elke id moet bestaan (404);
    de volgorde van de meegegeven lijst blijft behouden.
    """
    from fastapi import HTTPException

    if (chapter_id is None) == (chapter_ids is None):
        raise HTTPException(
            status_code=422, detail="Geef chapter_id óf chapter_ids op"
        )
    if chapter_id is not None:
        ids = [chapter_id]
    else:
        parts = [p.strip() for p in chapter_ids.split(",")]
        if not parts or not all(p.isdigit() for p in parts):
            raise HTTPException(
                status_code=422,
                detail="chapter_ids moet een kommalijst van ids zijn",
            )
        ids = [int(p) for p in parts]
    for cid in ids:
        chapter_or_404(conn, cid)
    return ids
