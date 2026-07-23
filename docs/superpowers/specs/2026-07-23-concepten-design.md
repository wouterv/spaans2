# Ontwerp: werk-in-uitvoering overleeft refresh (concepten)

*Datum: 2026-07-23 — status: goedgekeurd in gesprek*

## Doel

Een browser-refresh of later terugkomen mag geen werk kosten. Twee plekken:

1. **Nakijkscherm (scan-upload)**: het uitgelezen resultaat én elke bewerking
   wordt direct in de browser bewaard (localStorage). Bij terugkomen op
   "Les uploaden" biedt een banner aan: verdergaan met nakijken of weggooien.
   Pas na volledig succesvol opslaan wordt het concept gewist; na een deels
   mislukte opslag bevat het concept alleen de resterende kaarten.
2. **Gesprek**: de geschiedenis (incl. getoonde correcties) per hoofdstuk in
   localStorage; een refresh zet het gesprek gewoon voort. Nieuwe knop
   "🆕 Nieuw gesprek" wist de geschiedenis en laat Claude opnieuw openen.
   Bij ~100 berichten blokkeert versturen met de melding dat het gesprek vol
   is (lost het bestaande plafond netjes op).

## Verduidelijking op de fase 3-spec

"Gesprekken worden niet opgeslagen" blijft gelden voor de sérver (stateless,
geen database-opslag). Lokale browser-opslag valt daarbuiten.

## Techniek

- Nieuw module `app/static/js/concept.js`: `saveConcept(key, data)`,
  `loadConcept(key) -> {at, data} | null` (corrupt/afwezig → null),
  `clearConcept(key)`; storage injecteerbaar voor node:test.
- Sleutels: `spaans-les-concept-{chapterId}` en `spaans-gesprek-{chapterId}`.
- Gespreksberichten lokaal als `{role, text, correction?}`; vóór verzenden
  naar de server worden extra velden gestript.
- Tests: node:test voor concept.js; Playwright-verificatie met echte reload
  voor beide schermen (gemockte LLM-responses via route-interceptie).

## Buiten scope

- Oefensessie-voortgang (statistieken staan al veilig per antwoord).
- Concepten op de server / synchronisatie tussen apparaten.
