"""Antwoordcontrole: soepel met accenten, streng op ñ.

Opgeslagen antwoorden mogen synoniemen bevatten, gescheiden door ';'.
Binnen één synoniem scheidt '/' geslachtsvormen (el primo/la prima),
in dezelfde volgorde aan beide taalkanten. Zonder 'form' telt elke vorm
als goed antwoord; met 'form' (de index van de gevraagde vorm) telt
alleen de bijbehorende vorm.
Interpunctie zoals ¿? ¡! hoeft niet meegetypt te worden.
Een lidwoord vooraan mag aan één kant ontbreken (coche == el coche),
maar een verkeerd lidwoord blijft fout. Bij een geslachtsvraag ('form')
toetst het lidwoord juist het geslacht en blijft het verplicht.
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
    text = re.sub(r"\s*/\s*", "/", text)
    return re.sub(r"\s+", " ", text).strip()


def _fold_accents(text):
    return text.translate(_ACCENT_MAP)


_ARTICLES = {"el", "la", "los", "las", "un", "una", "unos", "unas", "de", "het", "een"}


def _without_article(text):
    head, _, rest = text.partition(" ")
    if head in _ARTICLES and rest:
        return rest
    return None


def _article_match(variant, answer):
    # Lidwoord mag aan één kant ontbreken; met lidwoord aan beide kanten
    # levert strippen hier nooit een match op, dus een fout lidwoord blijft fout.
    return _without_article(variant) == answer or _without_article(answer) == variant


def _variants(stored, form=None):
    variants = []
    for synonym in stored.split(";"):
        synonym = synonym.strip()
        if not synonym:
            continue
        forms = [f.strip() for f in synonym.split("/") if f.strip()]
        if form is not None and len(forms) > 1:
            variants.append(forms[min(form, len(forms) - 1)])
        else:
            variants.append(synonym)
            if len(forms) > 1:
                variants.extend(forms)
    return variants


def check_answer(stored, answer, form=None):
    variants = _variants(stored, form)
    correct_answer = "; ".join(variants) if form is not None else stored.strip()
    norm_answer = _normalize(answer)
    lenient_article = form is None
    if norm_answer:
        for variant in variants:
            norm_variant = _normalize(variant)
            if norm_variant == norm_answer or (
                lenient_article and _article_match(norm_variant, norm_answer)
            ):
                return CheckResult("correct", correct_answer, variant)
        folded_answer = _fold_accents(norm_answer)
        for variant in variants:
            folded_variant = _fold_accents(_normalize(variant))
            if folded_variant == folded_answer or (
                lenient_article and _article_match(folded_variant, folded_answer)
            ):
                return CheckResult("correct_accent", correct_answer, variant)
    return CheckResult("wrong", correct_answer, None)
