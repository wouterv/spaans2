# Spaans

Persoonlijke webapp om Spaanse lessen te oefenen: woorden, werkwoordvervoegingen
en grammatica, ingedeeld in hoofdstukken. Oefenen kan door te typen of via
spraak (voorlezen + spraakherkenning, handig in de auto).

## Stack

- **Backend**: Python + FastAPI + SQLite (`app/`), geen ORM, migraties in `app/migrations/`
- **Frontend**: vanilla JS/CSS zonder build-stap (`app/static/`)
- **Spraak**: Web Speech API in de browser (vereist HTTPS; werkt het best in Chrome)
- **Auth**: één wachtwoord, signed session cookie; config in `.env`

## Ontwikkelen

```bash
.venv/bin/pytest                          # Python-tests (API, checking, auth)
node --test tests/js/queue.test.mjs       # JS-tests (oefenwachtrij)

# Dev-server (leest .env):
.venv/bin/uvicorn --factory app.main:create_app --port 8100 --reload
```

## Configuratie (LLM)

Voor de LLM-functies (oefeningen genereren, vertaalbeoordeling, scans uitlezen):

```bash
ANTHROPIC_API_KEY=sk-ant-...   # verplicht voor LLM-functies
LLM_MODEL=claude-opus-4-8      # optioneel, dit is de default
```

Zonder key blijft de rest van de app gewoon werken; alleen genereren
geeft dan een foutmelding en vertaalzinnen vallen terug op de lokale check.

## Wachtwoord wijzigen

```bash
.venv/bin/python -m app.auth 'nieuw-wachtwoord'
# → plak de hash in .env als SPAANS_PASSWORD_HASH, daarna:
sudo systemctl restart spaans
```

## Deployment (eenmalig)

```bash
sudo cp deploy/spaans.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now spaans
cat deploy/caddy-spaans.txt | sudo tee -a /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Daarna draait de app op https://spaans.wjadv.nl (DNS wijst al naar deze
server). De database staat in `data/spaans.db` — dat bestand is de enige
plek met jouw lesdata; back-up = dat ene bestand kopiëren.

## Nieuwe werkwoordstijden toevoegen (later)

Het schema ondersteunt meerdere tijden (`conjugations.tense`). Voeg in
`app/static/js/views/verbs-entry.js` een `<option>` toe aan de tijd-dropdown;
invoer en oefenen werken er dan mee.
