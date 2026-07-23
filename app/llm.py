"""Uitwisselbaar laagje rond de Claude API.

Dit is de enige module die `anthropic` importeert; de rest van de app
kent alleen `complete_json` en `LLMError`. Model instelbaar via
LLM_MODEL in .env (default claude-opus-4-8), key via ANTHROPIC_API_KEY.
"""

import json
import os

import anthropic

DEFAULT_MODEL = "claude-opus-4-8"


class LLMError(Exception):
    """Nederlandse foutmelding die direct aan de gebruiker getoond kan worden."""


def _client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMError("ANTHROPIC_API_KEY ontbreekt in .env")
    return anthropic.Anthropic()


def complete_json(system, messages, schema, max_tokens=16000, cache_system=False):
    """Vraag Claude om JSON volgens `schema` en geef die geparst terug.

    Met cache_system=True wordt de systeemprompt gecachet (prompt-caching):
    goedkoper wanneer dezelfde prompt per beurt opnieuw meegaat (conversatie).
    """
    if cache_system:
        system = [{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }]
    try:
        response = _client().messages.create(
            model=os.environ.get("LLM_MODEL", DEFAULT_MODEL),
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.AuthenticationError as exc:
        raise LLMError("De API-sleutel is ongeldig") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError(
            "De taaldienst is even overbelast; probeer het zo opnieuw"
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("Geen verbinding met de taaldienst") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError("De taaldienst gaf een fout terug") from exc
    if response.stop_reason == "refusal":
        raise LLMError("De taaldienst weigerde dit verzoek")
    text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )
    try:
        return json.loads(text)
    except ValueError as exc:
        raise LLMError("Onbruikbaar antwoord van de taaldienst") from exc
