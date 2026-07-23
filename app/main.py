import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import auth, db
from app.routers import chapters, conversation, exercises, grammar, lessons, practice, verbs, words

DEFAULT_DB = Path(__file__).parent.parent / "data" / "spaans.db"
STATIC_DIR = Path(__file__).parent / "static"

# Paden die zonder login bereikbaar zijn
OPEN_PATHS = {"/api/login", "/api/health", "/login"}
# Statische assets bevatten geen data; de loginpagina heeft ze nodig
OPEN_PREFIXES = ("/static/",)


class LoginRequest(BaseModel):
    password: str


def create_app(db_path=None, password_hash=None, secret_key=None):
    load_dotenv()
    db_path = Path(db_path or os.environ.get("SPAANS_DB", DEFAULT_DB))
    password_hash = password_hash or os.environ.get("SPAANS_PASSWORD_HASH")
    secret_key = secret_key or os.environ.get("SPAANS_SECRET_KEY")
    if not password_hash or not secret_key:
        raise RuntimeError(
            "Zet SPAANS_PASSWORD_HASH en SPAANS_SECRET_KEY in .env "
            "(hash maken: python -m app.auth <wachtwoord>)"
        )

    db.migrate(db_path)

    app = FastAPI(title="Spaans")
    app.state.db_path = db_path

    @app.middleware("http")
    async def require_auth(request, call_next):
        path = request.url.path
        if path not in OPEN_PATHS and not path.startswith(OPEN_PREFIXES):
            token = request.cookies.get(auth.COOKIE_NAME, "")
            if not auth.session_is_valid(secret_key, token):
                if path.startswith("/api/"):
                    return JSONResponse({"detail": "Niet ingelogd"}, status_code=401)
                return RedirectResponse("/login", status_code=302)
        return await call_next(request)

    app.include_router(chapters.router)
    app.include_router(words.router)
    app.include_router(verbs.router)
    app.include_router(grammar.router)
    app.include_router(practice.router)
    app.include_router(exercises.router)
    app.include_router(lessons.router)
    app.include_router(conversation.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/login", status_code=204)
    def login(body: LoginRequest):
        if not auth.verify_password(body.password, password_hash):
            return JSONResponse({"detail": "Onjuist wachtwoord"}, status_code=401)
        response = Response(status_code=204)
        response.set_cookie(
            auth.COOKIE_NAME,
            auth.create_session_token(secret_key),
            max_age=auth.SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/login")
    def login_page():
        return FileResponse(STATIC_DIR / "login.html")

    @app.post("/api/logout", status_code=204)
    def logout():
        response = Response(status_code=204)
        response.delete_cookie(auth.COOKIE_NAME)
        return response

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app
