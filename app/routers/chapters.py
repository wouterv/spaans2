from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_conn

router = APIRouter(prefix="/api/chapters")


class ChapterIn(BaseModel):
    name: str = Field(min_length=1)


@router.get("")
def list_chapters(conn=Depends(get_conn)):
    rows = conn.execute(
        """
        SELECT c.id, c.name, c.position,
            (SELECT COUNT(*) FROM words w WHERE w.chapter_id = c.id) AS word_count,
            (SELECT COUNT(*) FROM verbs v WHERE v.chapter_id = c.id) AS verb_count,
            (SELECT COUNT(*) FROM grammar_rules g WHERE g.chapter_id = c.id) AS grammar_count,
            (SELECT COUNT(*) FROM exercises e WHERE e.chapter_id = c.id AND e.disabled = 0) AS exercise_count
        FROM chapters c
        ORDER BY c.position, c.id
        """
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("", status_code=201)
def create_chapter(body: ChapterIn, conn=Depends(get_conn)):
    cursor = conn.execute(
        """
        INSERT INTO chapters (name, position)
        VALUES (?, (SELECT COALESCE(MAX(position), 0) + 1 FROM chapters))
        """,
        (body.name,),
    )
    conn.commit()
    return {"id": cursor.lastrowid, "name": body.name}


@router.put("/{chapter_id}")
def rename_chapter(chapter_id: int, body: ChapterIn, conn=Depends(get_conn)):
    cursor = conn.execute(
        "UPDATE chapters SET name = ? WHERE id = ?", (body.name, chapter_id)
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Hoofdstuk niet gevonden")
    return {"id": chapter_id, "name": body.name}


@router.delete("/{chapter_id}", status_code=204)
def delete_chapter(chapter_id: int, conn=Depends(get_conn)):
    cursor = conn.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Hoofdstuk niet gevonden")
