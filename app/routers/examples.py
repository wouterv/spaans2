"""Voorbeeldoefeningen: opgaven uit het boek als input voor generatie en gesprek."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import chapter_or_404, get_conn

router = APIRouter(prefix="/api/examples")


class ExampleIn(BaseModel):
    chapter_id: int
    text: str = Field(min_length=1)


@router.get("")
def list_examples(chapter_id: int, conn=Depends(get_conn)):
    rows = conn.execute(
        "SELECT id, chapter_id, text FROM example_exercises "
        "WHERE chapter_id = ? ORDER BY id",
        (chapter_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("", status_code=201)
def create_example(body: ExampleIn, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Tekst is verplicht")
    cursor = conn.execute(
        "INSERT INTO example_exercises (chapter_id, text) VALUES (?, ?)",
        (body.chapter_id, text),
    )
    conn.commit()
    return {"id": cursor.lastrowid}


@router.delete("/{example_id}", status_code=204)
def delete_example(example_id: int, conn=Depends(get_conn)):
    cursor = conn.execute(
        "DELETE FROM example_exercises WHERE id = ?", (example_id,)
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Voorbeeld niet gevonden")
