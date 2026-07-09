from app.auth import hash_password, verify_password
from tests.conftest import TEST_PASSWORD


def test_password_hash_roundtrip():
    stored = hash_password("geheim123")
    assert verify_password("geheim123", stored)
    assert not verify_password("fout", stored)
    assert stored != "geheim123"


def test_login_with_correct_password(anon_client):
    response = anon_client.post("/api/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 204
    assert "session" in anon_client.cookies


def test_login_with_wrong_password(anon_client):
    response = anon_client.post("/api/login", json={"password": "fout"})
    assert response.status_code == 401
    assert "session" not in anon_client.cookies


def test_api_requires_auth(anon_client):
    response = anon_client.get("/api/chapters")
    assert response.status_code == 401


def test_api_accessible_after_login(client):
    response = client.get("/api/chapters")
    assert response.status_code != 401


def test_health_is_open(anon_client):
    assert anon_client.get("/api/health").status_code == 200


def test_page_redirects_to_login(anon_client):
    response = anon_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_login_page_is_open(anon_client):
    response = anon_client.get("/login")
    assert response.status_code == 200


def test_logout_revokes_access(client):
    assert client.post("/api/logout").status_code == 204
    assert client.get("/api/chapters").status_code == 401


def test_tampered_cookie_is_rejected(anon_client):
    anon_client.cookies.set("session", "vervalst.cookie.waarde")
    assert anon_client.get("/api/chapters").status_code == 401
