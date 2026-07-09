import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app_instance(tmp_path):
    return create_app(db_path=tmp_path / "test.db")


@pytest.fixture
def client(app_instance):
    with TestClient(app_instance) as c:
        yield c
