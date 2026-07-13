---
name: verify
description: Draai de Spaans-app lokaal en verifieer wijzigingen via de echte web-UI
---

# Spaans-app verifiëren

## App starten (testinstantie, los van productie op poort 8100)

```bash
SCRATCH=<scratchpad-dir>
HASH=$(.venv/bin/python -m app.auth verifytest | tail -1)
SPAANS_DB=$SCRATCH/verify.db SPAANS_PASSWORD_HASH="$HASH" SPAANS_SECRET_KEY=verify-secret \
  setsid .venv/bin/python -m uvicorn app.main:create_app --factory --port 8765 \
  > $SCRATCH/uvicorn.log 2>&1 < /dev/null &
```

- Wachtwoord is dan `verifytest`; login: `POST /api/login {"password": "verifytest"}` (cookie-jar gebruiken).
- **Let op:** op poort 8100 draait de echte instantie (spaans.wjadv.nl) — niet killen. Stop de testinstantie met `pkill -f '[u]vicorn.*8765'` (de `[u]` voorkomt dat pkill z'n eigen shell raakt).

## Browser-UI aansturen

- Geen playwright in de project-venv; installeer los: `uv pip install --python .venv/bin/python --target $SCRATCH/pwlib playwright` en draai met `PYTHONPATH=$SCRATCH/pwlib`.
- Chrome zit op `/usr/bin/google-chrome`; launch met `executable_path="/usr/bin/google-chrome", headless=True` (geen browser-download nodig).
- Login-pagina: veld `#password`, knop `button[type=submit]`. Wacht na login op URL exact `BASE + "/"` — een glob als `/**` matcht `/login` zelf en racet de cookie.
- Routes: hash-router, bijv. `#/h/<id>/werkwoorden`. Views gebruiken `aria-label`-selectors (bijv. `input[aria-label='Infinitief (Spaans)']`).
- Maak eerst een hoofdstuk aan via `POST /api/chapters {"name": "Testhoofdstuk"}`.

## Gotcha's

- Wikimedia/Wiktionary geeft 403 zonder contactinfo in de User-Agent (zie `app/conjugate.py`).
- Tests: `.venv/bin/python -m pytest tests/` en `node --test tests/js/*.test.mjs` (een kale map geven aan `node --test` faalt met MODULE_NOT_FOUND) — maar verificatie is de app draaien, niet de tests.
