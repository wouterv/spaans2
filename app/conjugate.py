"""Vervoegingen ophalen van Wiktionary (Engelstalig, sectie Spanish)."""

import re

import httpx

API_URL = "https://en.wiktionary.org/w/api.php"
# Wikimedia weigert requests (403) zonder contactinfo in de User-Agent
USER_AGENT = "spaans-oefenapp/1.0 (https://spaans.wjadv.nl; persoonlijk gebruik) httpx"
PERSONS = ["yo", "tu", "el", "nosotros", "vosotros", "ellos"]


REFLEXIVE_PRONOUNS = {
    "yo": "me",
    "tu": "te",
    "el": "se",
    "nosotros": "nos",
    "vosotros": "os",
    "ellos": "se",
}


class SourceUnavailable(Exception):
    """Wiktionary is niet bereikbaar of gaf een foutstatus."""


def lookup_presente(infinitive):
    """Presente-vormen voor een infinitief, of None als niets gevonden.

    Reflexieve werkwoorden (-arse/-erse/-irse) hebben op Wiktionary geen
    eigen tabel; dan zoeken we het basiswerkwoord op en zetten het
    wederkerend voornaamwoord voor elke vorm.
    """
    html = fetch_page_html(infinitive)
    forms = parse_presente(html) if html else None
    if forms is None and infinitive.endswith(("arse", "erse", "irse")):
        base_html = fetch_page_html(infinitive[:-2])
        base_forms = parse_presente(base_html) if base_html else None
        if base_forms:
            forms = {
                person: f"{REFLEXIVE_PRONOUNS[person]} {form}"
                for person, form in base_forms.items()
            }
    return forms


def fetch_page_html(infinitive):
    """Gerenderde HTML van de Wiktionary-pagina, of None als die niet bestaat."""
    try:
        response = httpx.get(
            API_URL,
            params={
                "action": "parse",
                "page": infinitive,
                "prop": "text",
                "format": "json",
                "formatversion": 2,
                "redirects": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise SourceUnavailable(str(exc)) from exc
    if "error" in data:
        return None
    return data["parse"]["text"]


def parse_presente(html):
    """Presente-vormen uit de Spaanse vervoegingstabel, of None.

    De pagina kan tabellen voor meerdere talen bevatten (bijv. Asturisch op
    de tener-pagina), dus we beperken ons tot de sectie met id="Spanish".
    """
    section_start = html.find('id="Spanish"')
    if section_start == -1:
        return None
    section = html[section_start:]
    next_language = re.search(r'<h2 id="(?!Spanish)', section)
    if next_language:
        section = section[: next_language.start()]
    table_start = section.find("roa-inflection-table")
    if table_start == -1:
        return None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", section[table_start:], re.S):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
        if not cells or _cell_text(cells[0]) != "present":
            continue
        forms = [_first_form(cell) for cell in cells[1:7]]
        if len(forms) == 6 and all(forms):
            return dict(zip(PERSONS, forms))
        return None
    return None


def _cell_text(cell):
    return re.sub(r"<[^>]+>", "", cell).strip()


def _first_form(cell):
    # De tú/vos-cel bevat twee vormen; de eerste link is de tú-vorm
    match = re.search(r"<a [^>]*>([^<]+)</a>", cell)
    return match.group(1) if match else _cell_text(cell)
