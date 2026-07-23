"""Lesstof van een hoofdstuk als platte tekst, voor LLM-prompts."""

from app.routers.grammar import list_rules
from app.routers.verbs import list_verbs
from app.routers.words import list_words


def lesson_context(conn, chapter_id):
    """Grammatica, woorden en werkwoorden; secties alleen als ze gevuld zijn."""
    parts = []
    rules = list_rules(chapter_id, conn)
    if rules:
        parts.append("Grammaticaregels:")
        for rule in rules:
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
