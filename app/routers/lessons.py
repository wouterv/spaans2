"""Scan-upload: lesboek-pagina's laten uitlezen door de LLM (vision).

Het extract-endpoint geeft alleen een voorstel terug; opslaan gebeurt
pas na het nakijken, via het bestaande /api/grammar-endpoint.
"""

import base64
import binascii
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import llm
from app.deps import chapter_or_404, get_conn

router = APIRouter(prefix="/api/chapters")

MAX_IMAGE_BYTES = 5_000_000

_RULES_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "explanation": {"type": "string"},
                    "examples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "spanish": {"type": "string"},
                                "dutch": {"type": "string"},
                            },
                            "required": ["spanish", "dutch"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "explanation", "examples"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rules"],
    "additionalProperties": False,
}

_EXTRACT_SYSTEM = (
    "Je leest foto's of scans van pagina's uit een Spaans lesboek voor "
    "Nederlandstaligen. Zet de leerstof om naar grammaticaregels: een korte "
    "Nederlandse titel, een beknopte Nederlandse uitleg in eigen woorden, en "
    "de Spaanse voorbeeldzinnen van de pagina met hun Nederlandse vertaling "
    "(vertaal zelf als de vertaling er niet bij staat). Neem alleen leerstof "
    "over: sla invuloefeningen, opgaven en paginanummers over. Verzin geen "
    "regels die niet op de pagina staan. Splits verschillende onderwerpen in "
    "aparte regels."
)


class ImageIn(BaseModel):
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(min_length=1)


class ExtractRequest(BaseModel):
    images: list[ImageIn] = Field(min_length=1, max_length=10)


def _validate_images(images):
    for image in images:
        try:
            raw = base64.b64decode(image.data, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Ongeldige afbeelding")
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Afbeelding is te groot (max 5 MB na verkleinen)",
            )


def _clean_rules(data):
    rules = []
    for rule in data.get("rules", []):
        title = rule["title"].strip()
        if not title:
            continue
        examples = [
            {"spanish": ex["spanish"].strip(), "dutch": ex["dutch"].strip()}
            for ex in rule["examples"]
            if ex["spanish"].strip()
        ]
        rules.append(
            {"title": title, "explanation": rule["explanation"].strip(),
             "examples": examples}
        )
    return rules


@router.post("/{chapter_id}/lessons/extract")
def extract_lesson(chapter_id: int, body: ExtractRequest, conn=Depends(get_conn)):
    chapter_or_404(conn, chapter_id)
    _validate_images(body.images)
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image.media_type,
                "data": image.data,
            },
        }
        for image in body.images
    ]
    content.append({
        "type": "text",
        "text": "Zet de lesstof op deze pagina('s) om naar grammaticaregels.",
    })
    try:
        data = llm.complete_json(
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": content}],
            schema=_RULES_SCHEMA,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    rules = _clean_rules(data)
    if not rules:
        raise HTTPException(
            status_code=502, detail="Geen lesstof herkend in de scan(s)"
        )
    return {"rules": rules}
