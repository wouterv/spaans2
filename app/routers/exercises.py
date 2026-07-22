import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import llm
from app.checking import CheckResult, check_answer
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


class ExerciseCheck(BaseModel):
    answer: str


_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "feedback": {"type": "string"},
    },
    "required": ["correct", "feedback"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = (
    "Je beoordeelt of een leerling een Nederlandse zin correct naar het Spaans "
    "heeft vertaald. Meerdere vertalingen kunnen goed zijn; keur goed als de "
    "vertaling grammaticaal correct is en de betekenis overbrengt. Accentfouten "
    "zijn geen reden voor afkeuring. Geef bij een afkeuring in 'feedback' één "
    "korte Nederlandse zin die uitlegt wat er mis is; anders een lege string."
)


def _judge_translation(exercise, answer):
    """LLM-oordeel over een vertaling; None bij storing (dan telt de lokale check)."""
    try:
        return llm.complete_json(
            system=_JUDGE_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"Nederlandse zin: {exercise['prompt']}\n"
                    f"Voorbeeldvertaling: {exercise['answer']}\n"
                    f"Antwoord van de leerling: {answer}"
                ),
            }],
            schema=_JUDGE_SCHEMA,
            max_tokens=1000,
        )
    except llm.LLMError:
        return None


def _update_stats(conn, exercise_id, exercise_type, is_correct):
    conn.execute(
        """
        INSERT INTO practice_stats
            (item_type, item_id, direction, correct, wrong, last_practiced_at)
        VALUES ('exercise', ?, ?, ?, ?, datetime('now'))
        ON CONFLICT (item_type, item_id, direction) DO UPDATE SET
            correct = correct + excluded.correct,
            wrong = wrong + excluded.wrong,
            last_practiced_at = excluded.last_practiced_at
        """,
        (exercise_id, exercise_type, 1 if is_correct else 0, 0 if is_correct else 1),
    )
    conn.commit()


@router.post("/{exercise_id}/check")
def check_exercise(exercise_id: int, body: ExerciseCheck, conn=Depends(get_conn)):
    exercise = conn.execute(
        "SELECT id, type, prompt, answer, explanation FROM exercises WHERE id = ?",
        (exercise_id,),
    ).fetchone()
    if exercise is None:
        raise HTTPException(status_code=404, detail="Oefening niet gevonden")

    result = check_answer(exercise["answer"], body.answer)
    feedback = ""
    # Bij vertalen kunnen meerdere antwoorden goed zijn: alleen als de lokale
    # check "fout" zegt, mag de LLM het eindoordeel geven.
    if (
        result.result == "wrong"
        and exercise["type"] == "vertalen"
        and body.answer.strip()
    ):
        verdict = _judge_translation(exercise, body.answer)
        if verdict is not None:
            if verdict["correct"]:
                result = CheckResult("correct", result.correct_answer, body.answer)
            else:
                feedback = verdict["feedback"]

    _update_stats(conn, exercise_id, exercise["type"], result.result != "wrong")
    return {
        "result": result.result,
        "correct_answer": result.correct_answer,
        "explanation": exercise["explanation"],
        "feedback": feedback,
    }
