import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import llm
from app.checking import CheckResult, check_answer
from app.deps import chapter_or_404, get_conn
from app.routers.grammar import list_rules
from app.routers.verbs import list_verbs
from app.routers.words import list_words

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
            max_tokens=4000,
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


GENERATION_COUNT = 12

_EXERCISES_SCHEMA = {
    "type": "object",
    "properties": {
        "exercises": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["invullen", "vertalen", "meerkeuze", "herschrijven"],
                    },
                    "instruction": {"type": "string"},
                    "prompt": {"type": "string"},
                    "answer": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                },
                "required": [
                    "type", "instruction", "prompt",
                    "answer", "options", "explanation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["exercises"],
    "additionalProperties": False,
}

_GENERATE_SYSTEM = (
    "Je maakt Spaanse grammatica-oefeningen voor een Nederlandstalige beginner. "
    "Baseer elke oefening op de gegeven grammaticaregels en gebruik zoveel "
    "mogelijk de gegeven woordenschat. Vier typen:\n"
    "- invullen: prompt is een Spaanse zin met precies één gat, geschreven als "
    "drie underscores (___); answer is wat er in het gat hoort.\n"
    "- vertalen: prompt is een Nederlandse zin; answer is de Spaanse vertaling. "
    "Meerdere goede vertalingen scheid je met ';'.\n"
    "- meerkeuze: prompt is een Spaanse zin met een gat (___); options bevat 3 "
    "of 4 mogelijkheden waarvan er precies één juist is; answer is exact de "
    "juiste optie.\n"
    "- herschrijven: instruction zegt hoe de zin moet worden omgezet (bijv. "
    "naar meervoud of een andere persoon); prompt is de bronzin; answer de "
    "omgezette zin.\n"
    "instruction is altijd een korte Nederlandse opdracht. explanation is één "
    "korte Nederlandse zin die de regel achter het antwoord uitlegt. options "
    "is bij andere typen dan meerkeuze een lege lijst. Houd de zinnen kort en "
    "op beginnersniveau."
)


class GenerateRequest(BaseModel):
    chapter_id: int


def _lesson_context(conn, chapter_id):
    parts = ["Grammaticaregels:"]
    for rule in list_rules(chapter_id, conn):
        parts.append(f"## {rule['title']}\n{rule['explanation']}")
        parts.extend(
            f"- {ex['spanish']} — {ex['dutch']}" for ex in rule["examples"]
        )
    words = list_words(chapter_id, conn)
    if words:
        parts.append("\nWoordenschat:")
        parts.extend(f"- {w['spanish']} — {w['dutch']}" for w in words)
    verbs = list_verbs(chapter_id, conn)
    if verbs:
        parts.append("\nWerkwoorden:")
        parts.extend(
            f"- {v['infinitive_es']} — {v['translation_nl']}" for v in verbs
        )
    return "\n".join(parts)


def _valid_exercise(item):
    if not item["prompt"].strip() or not item["answer"].strip():
        return False
    if item["type"] == "meerkeuze":
        options = [o.strip() for o in item["options"] if o.strip()]
        return len(options) >= 2 and item["answer"].strip() in options
    return True


@router.post("/generate")
def generate_exercises(body: GenerateRequest, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    if not list_rules(body.chapter_id, conn):
        raise HTTPException(
            status_code=400,
            detail="Dit hoofdstuk heeft nog geen grammatica om oefeningen op te baseren",
        )
    context = _lesson_context(conn, body.chapter_id)
    try:
        data = llm.complete_json(
            system=_GENERATE_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"{context}\n\nMaak {GENERATION_COUNT} oefeningen, "
                    "gemengd over de vier typen."
                ),
            }],
            schema=_EXERCISES_SCHEMA,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    created = 0
    for item in data.get("exercises", []):
        if not _valid_exercise(item):
            continue
        conn.execute(
            "INSERT INTO exercises (chapter_id, type, instruction, prompt, "
            "answer, options, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                body.chapter_id,
                item["type"],
                item["instruction"].strip(),
                item["prompt"].strip(),
                item["answer"].strip(),
                json.dumps([o.strip() for o in item["options"] if o.strip()], ensure_ascii=False)
                if item["type"] == "meerkeuze" else None,
                item["explanation"].strip(),
            ),
        )
        created += 1
    conn.commit()
    if created == 0:
        raise HTTPException(
            status_code=502, detail="De taaldienst gaf geen bruikbare oefeningen"
        )
    return {"created": created}
