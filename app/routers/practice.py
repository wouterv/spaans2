from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.checking import check_answer
from app.deps import get_conn
from app.routers.verbs import list_verbs
from app.routers.words import list_words

router = APIRouter(prefix="/api/practice")


class CheckRequest(BaseModel):
    item_type: Literal["word", "verb"]
    item_id: int
    direction: str
    answer: str
    # Extra kandidaten van spraakherkenning; de beste uitkomst telt
    alternatives: list[str] = []
    # Index van de gevraagde geslachtsvorm (el primo/la prima → 0 of 1)
    form: int | None = Field(default=None, ge=0)
    tense: str = "presente"
    person: str | None = None

    @model_validator(mode="after")
    def verb_requires_person(self):
        if self.item_type == "verb" and not self.person:
            raise ValueError("person is verplicht bij een werkwoord-check")
        return self


@router.get("/items")
def practice_items(
    chapter_id: int, type: Literal["words", "verbs"], conn=Depends(get_conn)
):
    if type == "words":
        return list_words(chapter_id, conn)
    return list_verbs(chapter_id, conn)


def _stored_answer(conn, body):
    if body.item_type == "word":
        row = conn.execute(
            "SELECT spanish, dutch FROM words WHERE id = ?", (body.item_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Woord niet gevonden")
        return row["dutch"] if body.direction == "es_nl" else row["spanish"]
    row = conn.execute(
        "SELECT form FROM conjugations WHERE verb_id = ? AND tense = ? AND person = ?",
        (body.item_id, body.tense, body.person),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Vervoeging niet gevonden")
    return row["form"]


def _stats_direction(body):
    if body.item_type == "verb":
        return f"{body.tense}:{body.person}"
    return body.direction


def _update_stats(conn, body, is_correct):
    conn.execute(
        """
        INSERT INTO practice_stats
            (item_type, item_id, direction, correct, wrong, last_practiced_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT (item_type, item_id, direction) DO UPDATE SET
            correct = correct + excluded.correct,
            wrong = wrong + excluded.wrong,
            last_practiced_at = excluded.last_practiced_at
        """,
        (
            body.item_type,
            body.item_id,
            _stats_direction(body),
            1 if is_correct else 0,
            0 if is_correct else 1,
        ),
    )
    conn.commit()


_RANK = {"correct": 0, "correct_accent": 1, "wrong": 2}


@router.post("/check")
def check(body: CheckRequest, conn=Depends(get_conn)):
    stored = _stored_answer(conn, body)
    candidates = [body.answer, *body.alternatives]
    result = min(
        (check_answer(stored, candidate, body.form) for candidate in candidates),
        key=lambda r: _RANK[r.result],
    )
    _update_stats(conn, body, result.result != "wrong")
    return {
        "result": result.result,
        "correct_answer": result.correct_answer,
        "matched": result.matched,
    }
