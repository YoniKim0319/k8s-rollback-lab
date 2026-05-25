import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ready():
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready"}


def test_info_contains_version():
    res = client.get("/info")
    assert res.status_code == 200
    data = res.json()
    assert "version" in data
    assert "env" in data
