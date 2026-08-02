# Ontwerp: Hoofdstukken met de hand sorteren

*Datum: 2026-08-02 — status: goedgekeurd in gesprek*

## Doel

De volgorde van hoofdstukken op het hoofdscherm handmatig kunnen aanpassen.
De database heeft al een `position`-kolom en `GET /api/chapters` sorteert er
al op (`ORDER BY position, id`); er ontbreekt alleen een manier om de
volgorde te wijzigen.

## Keuze

▲/▼-knopjes per rij, altijd zichtbaar — simpel, werkt ook op telefoon, past
bij de bestaande icoon-knopjes. Geen drag & drop (afgewogen en afgevallen:
complexer, lastig op touchscreens). API per verplaatsing in plaats van een
volledige-volgorde-endpoint (YAGNI: alleen de pijltjes-UI bestaat).

## Backend

Nieuw endpoint in `app/routers/chapters.py`:

- `POST /api/chapters/{chapter_id}/move`, body `{"direction": "up"|"down"}`
  (Pydantic: `Literal["up", "down"]`).
- Werking: haal alle hoofdstuk-ids op in huidige volgorde
  (`ORDER BY position, id`), verwissel het hoofdstuk met z'n buurman en
  schrijf voor álle hoofdstukken de positie opnieuw als 1..n. Het
  hernummeren is bewust: bestaande hoofdstukken kunnen allemaal
  `position = 0` hebben (oude default) en elke verplaatsing herstelt dat
  vanzelf.
- Randen: staat het hoofdstuk al bovenaan (up) of onderaan (down), dan
  verandert de volgorde niet — wél hernummeren, geen fout.
- Antwoord: `{"id": <chapter_id>, "position": <nieuwe positie>}`;
  404 "Hoofdstuk niet gevonden" bij onbekend id.

## Frontend

In `app/static/js/views/chapters.js`, per rij vóór ✏️ twee icoon-knopjes:

- ▲ met `aria-label` "Verplaats <naam> omhoog", ▼ met "Verplaats <naam>
  omlaag"; klasse `icon-btn` zoals de bestaande knopjes.
- Bovenste rij: ▲ disabled; onderste rij: ▼ disabled.
- Klik → `POST /api/chapters/{id}/move` en daarna `renderChapters(view)`
  opnieuw aanroepen (zelfde patroon als hernoemen/verwijderen).

## Buiten scope

- Drag & drop.
- Sorteren van woorden/werkwoorden/grammatica binnen een hoofdstuk
  (die tabellen hebben ook `position`, maar daar is niet om gevraagd).

## Tests

- pytest (`tests/test_api_chapters.py`): omhoog, omlaag, boven-/onderrand,
  404, ongeldige direction (422), en hernummering wanneer alle posities 0
  zijn (volgorde dan op id).
- Geen JS-tests per view (bestaat niet voor views); verificatie via de
  verify-skill in de echte UI.
