import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app

TEST_PASSWORD = "test-wachtwoord"


@pytest.fixture
def app_instance(tmp_path):
    return create_app(
        db_path=tmp_path / "test.db",
        password_hash=hash_password(TEST_PASSWORD),
        secret_key="test-secret",
    )


@pytest.fixture
def anon_client(app_instance):
    with TestClient(app_instance) as c:
        yield c


@pytest.fixture
def client(anon_client):
    response = anon_client.post(
        "/api/login", json={"password": TEST_PASSWORD}
    )
    assert response.status_code == 204
    return anon_client
