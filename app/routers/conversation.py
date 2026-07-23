"""Conversatie: gesprek in het Spaans over de lesstof van een hoofdstuk.

Stateless: de frontend stuurt per beurt de hele geschiedenis mee en er
wordt niets opgeslagen (spec). De systeemprompt met lesstof wordt gecachet.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import llm
from app.deps import chapter_or_404, get_conn
from app.lesstof import lesson_context

router = APIRouter(prefix="/api/chapters")

# reply staat bewust vóór correction: het model vult velden in schema-volgorde
# in, en een onbesliste correctie-afweging lekte anders als redeneertekst in
# het eerste veld. Eerst antwoorden, dan pas het (besliste) oordeel.
_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string",
            "description": "Jouw Spaanse antwoord dat het gesprek voortzet.",
        },
        "correction": {
            "type": "string",
            "description": (
                "Eén korte Nederlandse verbetering van een echte fout in het "
                "laatste bericht van de leerling, of een lege string. Nooit "
                "overwegingen, Engels of meta-tekst."
            ),
        },
    },
    "required": ["reply", "correction"],
    "additionalProperties": False,
}

# Een echte correctie is één korte zin; alles daarboven is vrijwel zeker
# gelekt redeneerwerk en wordt weggegooid.
MAX_CORRECTION_LENGTH = 200

_SYSTEM_TEMPLATE = (
    "Je bent een geduldige Spaanse gesprekspartner voor een Nederlandstalige "
    "beginner. Voer een natuurlijk gesprek in eenvoudig Spaans met korte "
    "zinnen en stuur het gesprek richting de lesstof hieronder: gebruik de "
    "grammatica en woordenschat van dit hoofdstuk en stel vragen die de "
    "leerling uitnodigen die ook te gebruiken.\n\n"
    "Geef per beurt twee velden terug:\n"
    "- correction: alleen als het laatste bericht van de leerling een echte "
    "fout bevat één korte Nederlandse verbetering; anders een lege string. "
    "Accent- en interpunctiefouten verbeter je niet, stijlkeuzes (zoals 'yo' "
    "weglaten) ook niet, en een correctie die je eerder in dit gesprek al gaf "
    "herhaal je niet. Een grammaticaal correct bericht krijgt nooit een "
    "correctie. Schrijf in correction nooit je overwegingen of iets anders "
    "dan de verbetering zelf; twijfel je, laat het veld dan leeg.\n"
    "- reply: jouw Spaanse antwoord dat het gesprek voortzet, afgesloten met "
    "een vraag terug. Maximaal twee korte zinnen.\n\n"
    "Lesstof van dit hoofdstuk:\n{lesstof}"
)

_OPENING = (
    "Begin het gesprek met een korte Spaanse begroeting en één eenvoudige "
    "openingsvraag over de lesstof."
)


class TurnIn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class ConversationRequest(BaseModel):
    messages: list[TurnIn] = Field(default=[], max_length=100)


@router.post("/{chapter_id}/conversation")
def conversation_turn(
    chapter_id: int, body: ConversationRequest, conn=Depends(get_conn)
):
    chapter_or_404(conn, chapter_id)
    lesstof = lesson_context(conn, chapter_id)
    if not lesstof:
        raise HTTPException(
            status_code=400,
            detail="Dit hoofdstuk heeft nog geen lesstof om over te praten",
        )
    if body.messages:
        if body.messages[-1].role != "user":
            raise HTTPException(
                status_code=400,
                detail="Het laatste bericht moet van de leerling zijn",
            )
        messages = [
            {"role": turn.role, "content": turn.text} for turn in body.messages
        ]
    else:
        messages = [{"role": "user", "content": _OPENING}]
    try:
        data = llm.complete_json(
            system=_SYSTEM_TEMPLATE.format(lesstof=lesstof),
            messages=messages,
            schema=_TURN_SCHEMA,
            cache_system=True,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    reply = data["reply"].strip()
    if not reply:
        raise HTTPException(
            status_code=502, detail="Geen antwoord van de gesprekspartner"
        )
    # Bij een gespreksopening valt er niets te corrigeren
    correction = data["correction"].strip() if body.messages else ""
    if len(correction) > MAX_CORRECTION_LENGTH:
        correction = ""
    return {"correction": correction, "reply": reply}
