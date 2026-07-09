"""Single-user auth: pbkdf2-wachtwoordhash + signed session cookie."""

import hashlib
import hmac
import secrets
import sys

from itsdangerous import BadSignature, URLSafeTimedSerializer

PBKDF2_ITERATIONS = 260_000
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 dagen
COOKIE_NAME = "session"


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2:{PBKDF2_ITERATIONS}:{salt}:{digest}"


def verify_password(password, stored):
    try:
        _, iterations, salt, digest = stored.split(":")
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        ).hex()
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(computed, digest)


def _serializer(secret_key):
    return URLSafeTimedSerializer(secret_key, salt="spaans-session")


def create_session_token(secret_key):
    return _serializer(secret_key).dumps("ok")


def session_is_valid(secret_key, token):
    if not token:
        return False
    try:
        _serializer(secret_key).loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return False
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Gebruik: python -m app.auth <wachtwoord>", file=sys.stderr)
        sys.exit(1)
    print(hash_password(sys.argv[1]))
