from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import chapter_or_404, get_conn

router = APIRouter(prefix="/api/grammar")


class ExampleIn(BaseModel):
    spanish: str = Field(min_length=1)
    dutch: str = ""


class RuleIn(BaseModel):
    chapter_id: int
    title: str = Field(min_length=1)
    explanation: str = ""
    examples: list[ExampleIn] = []


class RuleUpdate(BaseModel):
    title: str = Field(min_length=1)
    explanation: str = ""
    examples: list[ExampleIn] = []


def _save_examples(conn, rule_id, examples):
    conn.execute("DELETE FROM grammar_examples WHERE rule_id = ?", (rule_id,))
    for position, example in enumerate(examples):
        conn.execute(
            "INSERT INTO grammar_examples (rule_id, spanish, dutch, position) "
            "VALUES (?, ?, ?, ?)",
            (rule_id, example.spanish.strip(), example.dutch.strip(), position),
        )


@router.get("")
def list_rules(chapter_id: int, conn=Depends(get_conn)):
    rules = {
        row["id"]: dict(row, examples=[])
        for row in conn.execute(
            "SELECT id, chapter_id, title, explanation FROM grammar_rules "
            "WHERE chapter_id = ? ORDER BY position, id",
            (chapter_id,),
        )
    }
    if rules:
        placeholders = ",".join("?" * len(rules))
        for row in conn.execute(
            f"SELECT id, rule_id, spanish, dutch FROM grammar_examples "
            f"WHERE rule_id IN ({placeholders}) ORDER BY position, id",
            list(rules),
        ):
            rules[row["rule_id"]]["examples"].append(
                {"id": row["id"], "spanish": row["spanish"], "dutch": row["dutch"]}
            )
    return list(rules.values())


@router.post("", status_code=201)
def create_rule(body: RuleIn, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    cursor = conn.execute(
        """
        INSERT INTO grammar_rules (chapter_id, title, explanation, position)
        VALUES (?, ?, ?, (SELECT COALESCE(MAX(position), 0) + 1
                          FROM grammar_rules WHERE chapter_id = ?))
        """,
        (body.chapter_id, body.title.strip(), body.explanation, body.chapter_id),
    )
    _save_examples(conn, cursor.lastrowid, body.examples)
    conn.commit()
    return {"id": cursor.lastrowid}


@router.put("/{rule_id}")
def update_rule(rule_id: int, body: RuleUpdate, conn=Depends(get_conn)):
    cursor = conn.execute(
        "UPDATE grammar_rules SET title = ?, explanation = ? WHERE id = ?",
        (body.title.strip(), body.explanation, rule_id),
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Regel niet gevonden")
    _save_examples(conn, rule_id, body.examples)
    conn.commit()
    return {"id": rule_id}


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, conn=Depends(get_conn)):
    cursor = conn.execute("DELETE FROM grammar_rules WHERE id = ?", (rule_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Regel niet gevonden")
