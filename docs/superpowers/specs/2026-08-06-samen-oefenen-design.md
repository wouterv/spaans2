# Ontwerp: Samen oefenen over meerdere hoofdstukken

*Datum: 2026-08-06 — status: goedgekeurd in gesprek*

## Doel

Oefenen met de stof van meerdere hoofdstukken tegelijk: hoofdstukken
selecteren (of alles) en dan woorden, werkwoorden, oefeningen en gesprek
doen met al die stof samen. Nu kan oefenen alleen per hoofdstuk.

## Keuzes

- Scope: woorden, werkwoorden, LLM-oefeningen én gesprek. Genereren van
  oefeningen en grammatica-lezen blijven per hoofdstuk.
- Ingang: apart scherm "Samen oefenen", via een knop op het hoofdscherm.
- Bestaande endpoints en views leren omgaan met meerdere hoofdstukken
  (afgewogen en afgevallen: aparte verzamel-endpoints en -views — dupliceert
  werkende schermen).
- Selectie reist als expliciete id-lijst in de route; "Alles" wordt op het
  selectiescherm opgelost naar de concrete ids.

## Nieuw scherm "Samen oefenen" (`app/static/js/views/combined.js`)

- Route `#/samen`; knop op het hoofdscherm (chapters.js), boven de lijst:
  "🎯 Samen oefenen" (alleen tonen als er ≥ 2 hoofdstukken zijn).
- Bovenaan een kaart met een checkbox per hoofdstuk (naam + aantallen) en
  een "Alles"-checkbox die alle vinkjes zet/wist. De selectie wordt bewaard
  in localStorage (`spaans-samen-selectie`, array van ids); ids die niet
  meer bestaan worden genegeerd. Default: alles aangevinkt.
- Daaronder dezelfde oefenkaarten als op het hoofdstukscherm, werkend op de
  selectie: Woorden (richting-toggle + ⌨️/🎙️), Werkwoorden (⌨️/🎙️),
  Oefeningen (alleen ⌨️ Oefenen, geen genereerknop), Gesprek (💬). Elke
  kaart toont het opgetelde aantal items van de selectie
  (word_count/verb_count/exercise_count uit `GET /api/chapters`).
- Kaarten zijn uitgeschakeld (knop disabled + melding) als de selectie leeg
  is of de teller 0 is.

## Routes (app.js)

Meervoudsvarianten naast de bestaande per-hoofdstuk-routes; `<ids>` is een
kommalijst zoals `1,3,4` (regex `\d+(?:,\d+)*`):

- `#/oefen/<ids>/woorden/(es_nl|nl_es)/(typen|spraak)` → renderPracticeWords
- `#/oefen/<ids>/werkwoorden/(typen|spraak)` → renderPracticeVerbs
- `#/oefen/<ids>/oefeningen` → renderPracticeExercises
- `#/gesprek/<ids>` → renderConversation

De bestaande routes (`#/h/{id}/oefen/...`, `#/h/{id}/gesprek`) blijven en
roepen dezelfde views aan met één id.

## Oefen-views

- `renderPracticeWords/Verbs/Exercises` en `renderConversation` krijgen in
  plaats van `chapterId` een `chapterIds`-array (per-hoofdstuk-routes geven
  `[id]` door).
- Items ophalen met `chapter_ids=<kommalijst>`; de wachtrij schudt alle
  items door elkaar (bestaand gedrag via shuffle).
- Terugknop: bij één id naar `#/h/{id}` (zoals nu), bij meerdere naar
  `#/samen`. Kop bij het gesprek: bij meerdere ids "Gesprek — samen oefenen"
  in plaats van de hoofdstuknaam.
- Gesprek gebruikt bij meerdere ids het nieuwe `POST /api/conversation`;
  bij één id het bestaande `POST /api/chapters/{id}/conversation`.

## Backend

- `GET /api/practice/items`: naast `chapter_id` (blijft werken) ook
  `chapter_ids` (kommalijst). Precies één van beide is verplicht (422 bij
  beide of geen van beide, en bij een lege of niet-numerieke lijst); 404
  als een id niet bestaat. Resultaat: items van alle hoofdstukken, in de
  volgorde van de meegegeven id-lijst (de views schudden toch).
- `GET /api/exercises`: zelfde `chapter_id`/`chapter_ids`-gedrag.
- `POST /api/conversation` (nieuw, in conversation.py): body
  `{chapter_ids: [int, ...], history: [...]}` — zelfde history-vorm en
  respons `{correction, reply}` als het bestaande endpoint. 404 als een id
  niet bestaat, 422 bij lege lijst. De systeemprompt bevat de lesstof van
  alle geselecteerde hoofdstukken, elk voorafgegaan door een kopregel met
  de hoofdstuknaam ("# <naam>"). Het bestaande per-hoofdstuk-endpoint
  blijft ongewijzigd; de gedeelde opbouw (schema, correctie-schoonmaak,
  LLM-aanroep) wordt een interne functie die beide endpoints gebruiken.
- `app/lesstof.py`: nieuwe functie `combined_context(conn, chapter_ids)`
  die per hoofdstuk `lesson_context` aanroept en samenvoegt met
  hoofdstuknaam-koppen.

## Buiten scope

- Oefeningen genereren over meerdere hoofdstukken.
- Grammatica lezen/les uploaden in de gecombineerde modus.
- Gewogen selectie (bijv. zwakke woorden eerst).

## Tests

- pytest: `chapter_ids` op practice/items en exercises (combineert in
  hoofdstuk-volgorde; 404 bij onbekend id; 422 bij geen/beide parameters en
  lege lijst; bestaand `chapter_id`-gedrag ongewijzigd).
- pytest: `POST /api/conversation` met gemockte LLM — lesstof van beide
  hoofdstukken mét naam-koppen in de systeemprompt, respons-vorm, 404/422;
  bestaand endpoint ongewijzigd.
- UI-verificatie via de verify-skill: selectiescherm (vinkjes, alles,
  onthouden selectie), woorden oefenen over twee hoofdstukken (items uit
  beide), terugknop naar #/samen.
