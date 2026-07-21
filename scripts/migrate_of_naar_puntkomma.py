"""Eenmalig opschonen: vertalingen met ' of ' omzetten naar het ';'-formaat.

Gebruik:
    python scripts/migrate_of_naar_puntkomma.py            # dry-run: toont voorstellen
    python scripts/migrate_of_naar_puntkomma.py --apply    # voert de wijzigingen uit

Zet ' of ' om naar '; ' zodat de antwoordcontrole elke variant apart goed rekent.
Alleen rijen die hier expliciet in OVERRIDES staan of het simpele patroon volgen
worden aangepast; controleer de dry-run-uitvoer voordat je --apply draait.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "spaans.db"

# Handmatige correcties waar naief splitsen op ' of ' een fout antwoord oplevert
# (bijv. "douche of badgel" betekent "douchegel of badgel").
OVERRIDES = {
    "douche of badgel": "douchegel; badgel",
    "een hoodie of sweatshirt": "een hoodie; een sweatshirt",
}


def proposal(text):
    if text in OVERRIDES:
        return OVERRIDES[text]
    if " of " in text:
        return "; ".join(part.strip() for part in text.split(" of "))
    return text


def main():
    apply = "--apply" in sys.argv
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, spanish, dutch FROM words "
        "WHERE spanish LIKE '% of %' OR dutch LIKE '% of %' ORDER BY id"
    ).fetchall()

    if not rows:
        print("Geen rijen met ' of ' gevonden — niets te doen.")
        return

    for word_id, spanish, dutch in rows:
        new_spanish, new_dutch = proposal(spanish), proposal(dutch)
        print(f"#{word_id}: {spanish!r} / {dutch!r}")
        print(f"    -> {new_spanish!r} / {new_dutch!r}")
        if apply:
            conn.execute(
                "UPDATE words SET spanish = ?, dutch = ? WHERE id = ?",
                (new_spanish, new_dutch, word_id),
            )

    if apply:
        conn.commit()
        print(f"\n{len(rows)} rijen bijgewerkt.")
    else:
        print(f"\nDry-run: {len(rows)} rijen zouden wijzigen. Draai met --apply om uit te voeren.")
    conn.close()


if __name__ == "__main__":
    main()
