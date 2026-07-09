"""Antwoordcontrole: soepel met accenten, streng op ñ.

Opgeslagen antwoorden mogen synoniemen bevatten, gescheiden door ';'.
Interpunctie zoals ¿? ¡! hoeft niet meegetypt te worden.
"""

import re
import unicodedata
from dataclasses import dataclass

_PUNCTUATION = "¿?¡!.,:…\"'()"
# ñ staat hier bewust niet in: dat is een aparte letter (año != ano)
_ACCENT_MAP = str.maketrans("áéíóúü", "aeiouu")


@dataclass
class CheckResult:
    result: str  # "correct" | "correct_accent" | "wrong"
    correct_answer: str
    matched: str | None = None


def _normalize(text):
    text = unicodedata.normalize("NFC", text).strip().lower()
    text = text.translate(str.maketrans("", "", _PUNCTUATION))
    return re.sub(r"\s+", " ", text).strip()


def _fold_accents(text):
    return text.translate(_ACCENT_MAP)


def check_answer(stored, answer):
    correct_answer = stored.strip()
    variants = [v.strip() for v in stored.split(";") if v.strip()]
    norm_answer = _normalize(answer)
    if norm_answer:
        for variant in variants:
            if _normalize(variant) == norm_answer:
                return CheckResult("correct", correct_answer, variant)
        folded_answer = _fold_accents(norm_answer)
        for variant in variants:
            if _fold_accents(_normalize(variant)) == folded_answer:
                return CheckResult("correct_accent", correct_answer, variant)
    return CheckResult("wrong", correct_answer, None)
