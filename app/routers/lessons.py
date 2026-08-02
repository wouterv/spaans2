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
        },
        "examples": {
            "type": "array",
            "items": {"type": "string"},
        },
        "verbs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "infinitive_es": {"type": "string"},
                    "translation_nl": {"type": "string"},
                },
                "required": ["infinitive_es", "translation_nl"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rules", "examples", "verbs"],
    "additionalProperties": False,
}

_EXTRACT_SYSTEM = (
    "Je leest foto's of scans van pagina's uit een Spaans lesboek voor "
    "Nederlandstaligen. Een pagina kan uitleg bevatten, oefenopgaven, of "
    "beide. Zet beide om:\n"
    "- Uitleg wordt een grammaticaregel (rules): een korte Nederlandse "
    "titel, een beknopte Nederlandse uitleg in eigen woorden, en de Spaanse "
    "voorbeeldzinnen van de pagina met hun Nederlandse vertaling (vertaal "
    "zelf als de vertaling er niet bij staat).\n"
    "- Elke oefenopgave wordt een voorbeeldoefening (examples): neem de "
    "opgave letterlijk over als één tekst, inclusief de opdracht erboven en "
    "het antwoord als dat afgedrukt staat.\n"
    "- Biedt de pagina expliciet werkwoorden aan — in een woordenlijstje "
    "met vertaling, een vervoegingstabel of duidelijk als nieuwe stof — "
    "dan worden dat werkwoorden (verbs): de infinitief voluit geschreven "
    "(reflexieve werkwoorden mét -se, zoals 'levantarse') met de "
    "Nederlandse vertaling (vertaal zelf als die er niet bij staat). Neem "
    "geen werkwoorden over die alleen in lopende tekst of voorbeeldzinnen "
    "voorkomen.\n"
    "Sla paginanummers en kopteksten over. Verzin niets dat niet op de "
    "pagina staat. Splits verschillende onderwerpen in aparte regels."
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


def _clean_examples(data):
    return [ex.strip() for ex in data.get("examples", []) if ex.strip()]


def _clean_verbs(data, existing):
    """Werkwoorden uit het LLM-antwoord, zonder lege kanten en zonder
    werkwoorden die al in het hoofdstuk staan (of dubbel herkend zijn)."""
    seen = set(existing)
    verbs = []
    for verb in data.get("verbs", []):
        infinitive = verb["infinitive_es"].strip().lower()
        translation = verb["translation_nl"].strip()
        if infinitive and translation and infinitive not in seen:
            seen.add(infinitive)
            verbs.append(
                {"infinitive_es": infinitive, "translation_nl": translation}
            )
    return verbs


_WORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "words": {
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
        }
    },
    "required": ["words"],
    "additionalProperties": False,
}

_WORDS_SYSTEM = (
    "Je leest foto's of scans van pagina's uit een Spaans lesboek voor "
    "Nederlandstaligen. Herken uitsluitend Spaans-Nederlandse woordparen: "
    "woordenlijstjes, tabellen of vocabulaire in de kantlijn. Negeer alle "
    "overige tekst volledig — uitleg, oefenopgaven, lopende tekst en "
    "paginanummers. Verzin geen paren die niet op de pagina staan en vertaal "
    "niet zelf: neem alleen paren over waarvan beide kanten er staan. Een "
    "geslachtspaar zoals 'el primo/la prima' blijft één paar, met '/' aan "
    "beide taalkanten. Gebruikt het boek een verkorte notatie zoals "
    "'arquitecto/a', 'profesor/a' of 'francés/esa', schrijf dan beide vormen "
    "voluit ('arquitecto/arquitecta', 'profesor/profesora', "
    "'francés/francesa'); neem nooit een los achtervoegsel na de '/' over — "
    "elke vorm moet een volledig woord zijn."
)


def _clean_words(data):
    words = []
    for word in data.get("words", []):
        spanish = word["spanish"].strip()
        dutch = word["dutch"].strip()
        if spanish and dutch:
            words.append({"spanish": spanish, "dutch": dutch})
    return words


@router.post("/{chapter_id}/words/extract")
def extract_words(chapter_id: int, body: ExtractRequest, conn=Depends(get_conn)):
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
        "text": "Haal de Spaans-Nederlandse woordparen van deze pagina('s).",
    })
    try:
        data = llm.complete_json(
            system=_WORDS_SYSTEM,
            messages=[{"role": "user", "content": content}],
            schema=_WORDS_SCHEMA,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    words = _clean_words(data)
    if not words:
        raise HTTPException(
            status_code=502, detail="Geen woordenlijst herkend in de scan(s)"
        )
    return {"words": words}


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
        "text": "Zet de lesstof op deze pagina('s) om naar grammaticaregels, "
                "voorbeeldoefeningen en werkwoorden.",
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
    examples = _clean_examples(data)
    existing = {
        row["infinitive_es"].strip().lower()
        for row in conn.execute(
            "SELECT infinitive_es FROM verbs WHERE chapter_id = ?", (chapter_id,)
        )
    }
    verbs = _clean_verbs(data, existing)
    if not rules and not examples and not verbs:
        raise HTTPException(
            status_code=502, detail="Geen lesstof herkend in de scan(s)"
        )
    return {"rules": rules, "examples": examples, "verbs": verbs}
