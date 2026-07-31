# Ontwerp: Woordenlijsten scannen

*Datum: 2026-07-31 — status: goedgekeurd in gesprek*

## Doel

Scans waarop Spaans↔Nederlandse woordenlijstjes tussen andere tekst staan
gericht uitlezen: alléén de woordparen worden herkend, alle overige tekst
(uitleg, opgaven, verhalen) wordt genegeerd. Na nakijken worden de paren
opgeslagen als gewone woorden bij het hoofdstuk.

## Keuze

Aparte flow ("📷 Woorden scannen"), los van de bestaande les-upload — de
gebruiker kiest bewust voor gericht woorden scannen.

## Backend

Nieuw endpoint in `app/routers/lessons.py` (hergebruikt `_validate_images`,
`MAX_IMAGE_BYTES`, foutcode-conventies):

- `POST /api/chapters/{chapter_id}/words/extract`
  body `{"images": [{media_type, data}]}` (zelfde `ExtractRequest`) →
  `{"words": [{"spanish": str, "dutch": str}]}`
- Instructie aan Claude: herken uitsluitend Spaans↔Nederlandse woordparen
  (lijstjes, tabellen, vocabulaire in de kantlijn); negeer uitleg, opgaven en
  lopende tekst volledig; verzin geen paren die niet op de pagina staan;
  geslachtsparen zoals "el primo/la prima" blijven één paar met `/`.
- Schoonmaak: strippen; paren zonder Spaans of zonder Nederlands vervallen.
- Fouten: 404/422/400/503 als bij de les-extractie; 502 "Geen woordenlijst
  herkend in de scan(s)" als er geen paar overblijft.
- Slaat niets op.

## Frontend

- De upload-stap (bestand kiezen, thumbnails, max 10, verkleinen met
  voortgang, secondeteller, netwerk-herkansing, foto-cache) verhuist uit
  `lesson-upload.js` naar herbruikbaar `app/static/js/scan-step.js`;
  `lesson-upload.js` en de nieuwe view gebruiken beide deze module.
  Interface: `renderScanStep(container, {intro, buttonLabel, extract})`
  waarbij `extract(images)` de API aanroept en bij succes zelf verder
  navigeert/rendert.
- Nieuwe view `app/static/js/views/words-scan.js`, route
  `#/h/{id}/woorden-scannen`: nakijklijst met per paar twee invoervelden
  (Spaans / Nederlands, zelfde aria-labels als het woorden-invoerscherm) en
  een verwijderknop, plus "+ woord". "💾 Alles opslaan" per woord via het
  bestaande `POST /api/words`; rij verdwijnt direct na succesvol opslaan
  (anti-duplicaten-patroon); na volledig succes → `#/h/{id}/woorden`.
- Concept-bewaring via `concept.js` (sleutel `spaans-woorden-concept-{id}`):
  resultaat + elke bewerking; banner met verdergaan/weggooien; gewist na
  volledig opslaan.
- Knop: 📷-icoonknopje in de Invoer-rij "Woorden" op het hoofdstukscherm.

## Testen

- pytest: endpoint met gemockte LLM (woorden terug; schoonmaak; 502 bij leeg;
  prompt bevat negeer-instructie; slaat niets op; foutcodes via gedeelde
  validatie).
- node:test: bestaande concept-tests dekken de opslag; scan-step heeft geen
  eigen unittests (DOM), wordt gedekt door UI-verificatie.
- UI-verificatie: echte testpagina met een woordenlijstje tússen uitleg- en
  opgaventekst; controleren dat alleen de woorden terugkomen, bewerken,
  opslaan, teller klopt; refresh-herstel via de banner.

## Buiten scope

- Woorden herkennen in de bestaande les-upload (bewust aparte flow).
- Duplicaatdetectie tegen bestaande woorden in het hoofdstuk (handmatig
  nakijken volstaat; het woorden-invoerscherm toont de bestaande lijst).
