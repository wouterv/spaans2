import json

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_conn

router = APIRouter(prefix="/api/exercises")


@router.get("")
def list_exercises(chapter_id: int, conn=Depends(get_conn)):
    rows = conn.execute(
        "SELECT id, chapter_id, type, instruction, prompt, answer, options, "
        "explanation FROM exercises WHERE chapter_id = ? AND disabled = 0 "
        "ORDER BY id",
        (chapter_id,),
    ).fetchall()
    return [
        dict(row, options=json.loads(row["options"]) if row["options"] else None)
        for row in rows
    ]


@router.post("/{exercise_id}/disable", status_code=204)
def disable_exercise(exercise_id: int, conn=Depends(get_conn)):
    cursor = conn.execute(
        "UPDATE exercises SET disabled = 1 WHERE id = ?", (exercise_id,)
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Oefening niet gevonden")
