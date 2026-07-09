from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import chapter_or_404, get_conn

router = APIRouter(prefix="/api/words")


class WordIn(BaseModel):
    chapter_id: int
    spanish: str = Field(min_length=1)
    dutch: str = Field(min_length=1)


class WordUpdate(BaseModel):
    spanish: str = Field(min_length=1)
    dutch: str = Field(min_length=1)


@router.get("")
def list_words(chapter_id: int, conn=Depends(get_conn)):
    rows = conn.execute(
        "SELECT id, chapter_id, spanish, dutch FROM words "
        "WHERE chapter_id = ? ORDER BY id",
        (chapter_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("", status_code=201)
def create_word(body: WordIn, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    cursor = conn.execute(
        "INSERT INTO words (chapter_id, spanish, dutch) VALUES (?, ?, ?)",
        (body.chapter_id, body.spanish.strip(), body.dutch.strip()),
    )
    conn.commit()
    return {"id": cursor.lastrowid}


@router.put("/{word_id}")
def update_word(word_id: int, body: WordUpdate, conn=Depends(get_conn)):
    cursor = conn.execute(
        "UPDATE words SET spanish = ?, dutch = ? WHERE id = ?",
        (body.spanish.strip(), body.dutch.strip(), word_id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Woord niet gevonden")
    return {"id": word_id}


@router.delete("/{word_id}", status_code=204)
def delete_word(word_id: int, conn=Depends(get_conn)):
    cursor = conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Woord niet gevonden")
