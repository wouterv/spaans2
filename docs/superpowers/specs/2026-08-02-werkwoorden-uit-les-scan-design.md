# Ontwerp: Werkwoorden automatisch verwerken bij les-scans

*Datum: 2026-08-02 — status: goedgekeurd in gesprek*

## Doel

Bij het uploaden van les-scans worden werkwoorden die de les aanbiedt
automatisch herkend, van presente-vervoegingen voorzien en — na nakijken —
als oefenbare werkwoorden bij het hoofdstuk opgeslagen. Nu moeten die na
een scan nog met de hand ingevoerd worden.

## Keuzes

- Alleen werkwoorden die de les expliciet aanbiedt (woordenlijstje met
  vertaling, vervoegingstabel, duidelijk nieuwe stof) — geen losse
  infinitieven uit lopende tekst.
- Vervoegingen via de bestaande Wiktionary-lookup
  (`GET /api/verbs/conjugate`), niet van de pagina en niet door de LLM.
- Eerst nakijken, dan opslaan — consistent met de hele scan-flow.
- Eén LLM-call: het bestaande lessons/extract-endpoint wordt uitgebreid
  (afgewogen en afgevallen: aparte tweede vision-call — dubbele kosten en
  latency zonder voordeel).

## Backend (`app/routers/lessons.py`)

- `_RULES_SCHEMA` krijgt naast `rules` en `examples` een derde verplichte
  array `verbs`: items `{infinitive_es: str, translation_nl: str}`.
- `_EXTRACT_SYSTEM` uitgebreid: herken ook werkwoorden die de les expliciet
  aanbiedt; geef de infinitief voluit (reflexieve werkwoorden mét -se,
  bijv. "levantarse") plus de Nederlandse vertaling (van de pagina, of zelf
  vertaald als die er niet bij staat); neem geen werkwoorden uit lopende
  tekst en verzin niets.
- Schoonmaak (`_clean_verbs`): strippen; items zonder infinitief of zonder
  vertaling vervallen; infinitief naar kleine letters.
- Dedup: werkwoorden waarvan `infinitive_es` (hoofdletterongevoelig) al in
  de `verbs`-tabel van dit hoofdstuk staat, worden uit het voorstel
  gefilterd.
- Respons wordt `{rules, examples, verbs}`. De 502-guard "Geen lesstof
  herkend in de scan(s)" treedt alleen op als rules, examples én verbs
  alle drie leeg zijn.

## Frontend (`app/static/js/views/lesson-upload.js`)

- Het nakijkscherm krijgt een sectie "Werkwoorden" (eyebrow-kop, zoals
  "Voorbeeldoefeningen") met een kaart per werkwoord: invoervelden voor
  infinitief (Spaans) en vertaling (Nederlands) plus de zes
  presente-vormen (yo, tú, él, nosotros, vosotros, ellos), en een
  🗑️-knop om de kaart te verwijderen.
- Bij het openen van het nakijkscherm haalt de app per werkwoord de vormen
  op via `GET /api/verbs/conjugate?infinitive=...` en vult ze in. Mislukt
  de lookup (404/503), dan blijven de zes velden leeg en toont de kaart
  een korte melding dat de vormen handmatig ingevuld moeten worden.
  Vormen die al in het concept staan (na een refresh) worden niet opnieuw
  opgehaald.
- Het concept in localStorage bevat voortaan ook `verbs` (met bewerkte
  vormen), zodat werk-in-uitvoering een refresh overleeft. Een bestaand
  concept zonder `verbs`-veld telt als "geen werkwoorden".
- Opslaan: per kaart `POST /api/verbs` met
  `{chapter_id, infinitive_es, translation_nl, tense: "presente", forms}`.
  Een kaart met een lege infinitief, lege vertaling of ontbrekende vormen
  wordt niet opgestuurd en blijft staan; de statusregel meldt dat. De rest
  wordt opgeslagen en verdwijnt (zelfde patroon als regels/oefeningen:
  het concept houdt alleen bij wat nog niet is opgeslagen).
- De teller ("X regels en Y voorbeeldoefeningen gelezen") telt ook
  werkwoorden mee.
- Geen "+ werkwoord"-knop op het nakijkscherm: handmatig toevoegen kan al
  via het bestaande werkwoorden-invoerscherm.

## Buiten scope

- Andere tijden dan presente.
- Vervoegingstabellen van de pagina overnemen.
- Werkwoorden herkennen in de losse woorden-scanflow (die blijft puur
  woordparen).

## Tests

- pytest (`tests/test_api_lessons.py`, met gemockte LLM zoals de bestaande
  lessons-tests): verbs in de respons; schoonmaak (lege kanten vervallen,
  infinitief lowercased); dedup tegen bestaande hoofdstuk-werkwoorden
  (hoofdletterongevoelig); guard: alleen 502 als rules, examples en verbs
  alle drie leeg zijn; bestaand gedrag ongewijzigd.
- UI-verificatie via de verify-skill: scan met werkwoord → kaart met
  opgehaalde vormen → opslaan → werkwoord staat bij het hoofdstuk.
