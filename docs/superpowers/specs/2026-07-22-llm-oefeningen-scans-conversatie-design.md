# Ontwerp: LLM-oefeningen, scan-upload en conversatie

*Datum: 2026-07-22 — status: goedgekeurd in brainstorm*

## Doel

De app uitbreiden met drie features op basis van de Claude API, gebouwd in drie fasen:

1. **Fase 1 — Oefeningen genereren**: per hoofdstuk grammatica-oefeningen laten genereren op basis van de al ingevoerde lesstof (grammatica-regels, woorden, werkwoorden).
2. **Fase 2 — Scan-upload**: gescande lessen uit het oefenboek uploaden; Claude leest ze en zet ze om naar grammatica-items die na nakijken worden opgeslagen.
3. **Fase 3 — Conversatie**: live gesprek in het Spaans (spreken én typen) met directe correctie per beurt, gestuurd door de lesstof van het hoofdstuk.

Elke fase is zelfstandig af en direct bruikbaar.

## Uitgangspunten en keuzes

- **LLM**: Claude API. Zelf hosten valt af: de server (Hetzner-VPS, 4 GB RAM, 2 vCPU, geen GPU) kan geen bruikbaar open-source model draaien. Kosten bij verwacht gebruik: enkele euro's per maand.
- **Uitwisselbaar laagje**: alle LLM-aanroepen lopen via één module (`app/llm.py`), zodat later overstappen naar een ander model of eigen hosting mogelijk blijft zonder de rest van de app te raken.
- **Model instelbaar**: `LLM_MODEL` in `.env`, default `claude-opus-4-8`. API-key als `ANTHROPIC_API_KEY` in `.env`.
- **Oefeningen direct oefenbaar** (geen nakijkstap); slechte oefeningen kun je tijdens het oefenen wegstemmen.
- **Scan-extractie wél met nakijkstap** voordat iets wordt opgeslagen.
- **Correctie in conversatie**: direct per beurt, kort en in het Nederlands.

## Fase 1 — LLM-laag en oefeningen

### LLM-laag (`app/llm.py`)

Kleine module op basis van de `anthropic`-SDK, met één functie:

- `complete_json(system, messages, schema) -> dict` — gestructureerde output via `output_config.format` (JSON-schema). Alle vier de toepassingen (oefeninggeneratie, vertaal-beoordeling, scan-extractie, conversatiebeurt) geven gestructureerde data terug, dus één functie volstaat. Afbeeldingen gaan in fase 2 als content-blocks in `messages` mee.

Niets buiten deze module importeert `anthropic`. Adaptieve thinking (default), non-streaming met ruime `max_tokens` (~16000). Prompt-caching op de systeemprompt waar dat loont (conversatie).

### Datamodel (migratie `app/migrations/002_exercises.sql`)

```sql
CREATE TABLE exercises (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('invullen','vertalen','meerkeuze','herschrijven')),
    instruction TEXT NOT NULL,            -- opdracht, bijv. "Vul de juiste vorm van 'ser' in"
    prompt TEXT NOT NULL,                 -- zin met gat, NL-zin, of bronzin
    answer TEXT NOT NULL,                 -- juiste antwoord; synoniemen met ';'
    options TEXT,                         -- JSON-array, alleen bij meerkeuze
    explanation TEXT NOT NULL DEFAULT '', -- korte uitleg, getoond na beantwoorden
    disabled INTEGER NOT NULL DEFAULT 0,  -- weggestemd
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Statistieken via bestaande `practice_stats` met `item_type='exercise'`.

### Genereren

- Knop "Oefeningen genereren" op het hoofdstukscherm → `POST /api/exercises/generate` (met `chapter_id` in de body).
- Backend verzamelt grammatica-regels + voorbeelden van het hoofdstuk, plus woorden en werkwoorden als context (oefeningen gebruiken bekende woordenschat).
- Claude genereert een mix van de vier typen als JSON; backend valideert en slaat op.
- Duurt ± een halve tot hele minuut; frontend toont spinner en daarna het aantal nieuwe oefeningen.

### Oefenen

Nieuwe oefenmodus "Oefeningen" naast woorden/werkwoorden; hergebruik van `queue.js` en de bestaande oefenflow.

| Type | Invoer | Controle |
|---|---|---|
| invullen | typen | lokaal, soepele check (`checking.py`, accent-hint) |
| herschrijven | typen | lokaal, soepele check |
| meerkeuze | knoppen | lokaal |
| vertalen | typen | eerst lokaal tegen opgeslagen antwoord; alleen bij "fout" beoordeelt Claude (goed/fout + korte uitleg) binnen hetzelfde check-endpoint |

Elke oefening heeft een knop "slechte oefening" → `disabled=1`, uit de rotatie.

## Fase 2 — Scan-upload

- Knop "Les uploaden" op het hoofdstukscherm; één of meer foto's/scans (JPEG/PNG).
- Frontend verkleint afbeeldingen in de browser naar max ~2000 px (langste zijde) vóór upload.
- `POST /api/chapters/{id}/lessons/extract` stuurt de afbeeldingen naar Claude (vision) met de vraag om lesstof om te zetten naar grammatica-regels: titel + Nederlandse uitleg + Spaanse voorbeeldzinnen met vertaling (JSON).
- Resultaat gaat níét direct de database in maar naar een **nakijkscherm**: voorgevulde, bewerkbare velden (zoals het bestaande grammatica-invoerscherm). Na "Opslaan" worden het gewone `grammar_rules` + `grammar_examples`.
- Scans worden niet op de server bewaard; na extractie zijn ze niet meer nodig.
- Endpoint valideert bestandstype en grootte.

## Fase 3 — Conversatie

- Nieuwe modus "Gesprek" per hoofdstuk: chatweergave, invoer via typen of microfoon (bestaande spraakherkenning, Spaans). Antwoorden worden voorgelezen met de bestaande TTS.
- Systeemprompt bevat de lesstof van het hoofdstuk (grammatica, woorden, werkwoorden). Claude is een Spaanse gesprekspartner die stuurt richting die lesstof, in eenvoudig Spaans met korte zinnen.
- Per beurt geeft Claude gestructureerd terug: (1) optionele korte correctie in het Nederlands op wat de gebruiker zei, (2) het Spaanse antwoord dat het gesprek voortzet. Correctie verschijnt klein onder het bericht van de gebruiker.
- Server blijft stateless: frontend stuurt per beurt de hele gespreksgeschiedenis mee naar `POST /api/chapters/{id}/conversation`. Systeemprompt wordt gecachet (prompt-caching) om kosten te drukken.
- Gesprekken worden niet opgeslagen.

## Foutafhandeling

- API-fouten (verbinding, rate limit, ongeldige key) → nette Nederlandse foutmelding in de UI; technische details in het serverlog.
- Faalt de vertaal-beoordeling tijdens het oefenen, dan valt de app terug op de lokale soepele check — oefenen blijft werken zonder API.
- Generatie/extractie-endpoints geven bij een onbruikbare LLM-respons (ongeldige JSON ondanks schema, lege set) een duidelijke fout en slaan niets half op.

## Testen

- **pytest**: alle nieuwe endpoints met gemockte LLM-laag (geen echte API-calls in tests); prompt-opbouw; verwerking en validatie van JSON-responses; migratie.
- **node:test**: gesprekslogica in de frontend als die niet-triviaal wordt.
- Tests eerst, conform de bestaande werkwijze.

## Buiten scope

- Gespreksgeschiedenis bewaren.
- Scans bewaren op de server.
- Nakijkstap voor gegenereerde oefeningen.
- Andere werkwoordstijden dan presente (schema ondersteunt ze al; generatie beperkt zich tot ingevoerde lesstof).
