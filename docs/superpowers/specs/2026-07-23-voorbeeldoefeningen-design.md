# Ontwerp: Voorbeeldoefeningen uit het boek als lesstof

*Datum: 2026-07-23 — status: goedgekeurd in brainstorm*

## Doel

Gescande boekpagina's die (ook) oefenopgaven bevatten — zonder of naast uitleg —
verwerken tot **voorbeeldoefeningen**: een vierde lesstof-bron per hoofdstuk die
de oefeninggenerator stuurt ("maak oefeningen zoals deze") en meegaat in het
gesprek. De boekoefeningen worden bewust níét zelf oefenbaar in de app.

## Keuzes

- **Eén slimme upload-flow**: de bestaande knop "📷 Les uploaden" blijft de enige
  ingang. Claude herkent per pagina wat erop staat: uitleg → grammaticaregels
  (zoals nu), oefenopgaven → voorbeeldoefeningen, een gemengde pagina levert
  beide op.
- **Bewaren als lesstof**: voorbeelden worden (na nakijken) opgeslagen bij het
  hoofdstuk en voeden daarna elke generatie en elk gesprek; één keer scannen
  volstaat.
- **Alleen voorbeeld-input**: geen directe import als oefenbare oefeningen.

## Datamodel (migratie `app/migrations/003_example_exercises.sql`)

```sql
CREATE TABLE example_exercises (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    text TEXT NOT NULL,          -- de opgave zoals in het boek, evt. met antwoord
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Eén vrij tekstveld per voorbeeld: flexibel voor elk opgavetype en precies wat
een LLM-prompt nodig heeft.

## API

Nieuwe router `app/routers/examples.py`, stijl van de bestaande CRUD-routers:

- `GET /api/examples?chapter_id=N` → `[{id, chapter_id, text}]`
- `POST /api/examples` body `{chapter_id, text}` → 201 `{id}` (404 onbekend
  hoofdstuk, 422 lege tekst)
- `DELETE /api/examples/{id}` → 204 (404 onbekend)

## Extractie (wijziging van `POST /api/chapters/{id}/lessons/extract`)

- Schema uitgebreid: naast `rules` ook `examples` (lijst strings).
- Instructie: uitleg → grammaticaregels zoals nu; oefenopgaven → letterlijk
  overnemen als voorbeeldoefening, mét het antwoord als dat afgedrukt staat;
  één pagina mag beide opleveren. De huidige regel "sla invuloefeningen en
  opgaven over" vervalt.
- Respons: `{"rules": [...], "examples": [...]}` (beide na dezelfde schoonmaak:
  strippen, lege items weg).
- 502 "geen lesstof herkend" alleen als **beide** lijsten leeg zijn.
- Er wordt nog steeds niets opgeslagen door dit endpoint.

## Gebruik in generatie en gesprek

- `lesson_context` (app/lesstof.py) krijgt een vierde sectie, na Werkwoorden:
  `"Voorbeeldoefeningen uit het boek:"` met per voorbeeld `- <tekst>`.
  Daarmee zien de generator én het gesprek ze automatisch.
- Generatie-instructie erbij: "Als er voorbeeldoefeningen uit het boek zijn:
  maak oefeningen in dezelfde stijl en over dezelfde stof, maar kopieer ze
  niet letterlijk."
- Generator-guard versoepeld: 400 alleen als het hoofdstuk géén grammatica én
  géén voorbeeldoefeningen heeft (was: alleen grammatica telde).

## Nakijkscherm (uitbreiding `lesson-upload.js`)

- Na het uitlezen twee secties: bovenaan de grammaticaregels (bestaande
  bewerkbare kaarten), daaronder "Voorbeeldoefeningen": per opgave een kaart
  met één tekstvak en een verwijderknop, plus "+ voorbeeld".
- "💾 Alles opslaan" slaat regels op via het bestaande `POST /api/grammar` en
  voorbeelden via `POST /api/examples`; elke kaart verdwijnt direct na
  succesvol opslaan (bestaand anti-duplicaten-patroon). Na volledig succes
  → terug naar het hoofdstukscherm (`#/h/{id}`), omdat het resultaat nu twee
  soorten lesstof kan zijn.
- Levert een scan alléén voorbeelden op, dan verschijnt alleen die sectie.

## Beheer

- Vierde rij "Voorbeeldoefeningen" met teller in het Invoer-lijstje op het
  hoofdstukscherm (`example_count` via de bestaande chapters-query, zoals de
  andere tellers).
- Nieuw invoerscherm route `#/h/{id}/voorbeelden` in de stijl van de bestaande
  invoerschermen: lijst van kaarten met opgavetekst en verwijderknop, plus een
  klein formulier (textarea) om handmatig een voorbeeld toe te voegen.

## Foutafhandeling

Zelfde patronen als fase 2: Nederlandse meldingen; bij deels mislukt opslaan
blijven alleen de niet-opgeslagen kaarten staan; LLM-storing → 503 met nette
melding.

## Testen

- pytest: migratie, examples-CRUD (incl. 404/422), extract met gemengde pagina
  (beide secties terug), alleen-oefeningen-pagina (geen 502), 502 alleen bij
  beide leeg, `lesson_context` met vierde sectie, versoepelde generator-guard
  (voorbeelden zonder grammatica → generatie mag), alles met gemockte LLM.
- UI-verificatie via de verify-skill met één echte extractie van een
  testpagina die uitleg én opgaven bevat.

## Buiten scope

- Boekoefeningen zelf oefenbaar maken.
- Koppeling van voorbeelden aan specifieke grammaticaregels.
- Bewerken van een opgeslagen voorbeeld (verwijderen + opnieuw toevoegen volstaat).
