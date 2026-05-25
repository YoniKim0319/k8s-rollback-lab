import pytest
import os
from fastapi.testclient import TestClient


def make_client(env: dict = {}):
    for k, v in env.items():
        os.environ[k] = v
    import importlib
    import main
    importlib.reload(main)
    return TestClient(main.app)


def teardown_function():
    for key in ("FORCE_NOT_READY", "SLOW_READY_MS", "APP_VERSION"):
        os.environ.pop(key, None)


# --- v1 정상 동작 ---

def test_health():
    client = make_client()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ready_normal():
    client = make_client()
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready"}


def test_info_contains_version():
    client = make_client({"APP_VERSION": "1.0.0"})
    res = client.get("/info")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "1.0.0"
    assert "env" in data


# --- v2 fault injection ---

def test_ready_force_not_ready():
    """FORCE_NOT_READY=true 시 readinessProbe 가 503 을 받아 Pod 가 트래픽에서 제외됨을 시뮬레이션"""
    client = make_client({"FORCE_NOT_READY": "true"})
    res = client.get("/ready")
    assert res.status_code == 503
    assert "fault injection" in res.json()["detail"]


def test_info_exposes_fault_flags():
    """운영자가 /info 로 현재 fault injection 상태를 확인할 수 있어야 함"""
    client = make_client({"FORCE_NOT_READY": "true", "SLOW_READY_MS": "200"})
    res = client.get("/info")
    assert res.status_code == 200
    fi = res.json()["fault_injection"]
    assert fi["force_not_ready"] is True
    assert fi["slow_ready_ms"] == 200


def test_health_unaffected_by_fault_injection():
    """livenessProbe 대상인 /health 는 fault injection 과 무관하게 정상 응답해야 함"""
    client = make_client({"FORCE_NOT_READY": "true"})
    res = client.get("/health")
    assert res.status_code == 200


# --- Prometheus metrics ---

def test_metrics_endpoint_exists():
    """Prometheus가 scraping할 /metrics 엔드포인트가 존재해야 함"""
    client = make_client()
    res = client.get("/metrics")
    assert res.status_code == 200


def test_metrics_content_type():
    """/metrics 응답은 Prometheus text format 이어야 함"""
    client = make_client()
    res = client.get("/metrics")
    assert "text/plain" in res.headers["content-type"]


def test_metrics_records_http_requests():
    """엔드포인트 호출 후 /metrics 에 http_requests 카운터가 기록되어야 함"""
    client = make_client()
    client.get("/health")
    client.get("/ready")
    res = client.get("/metrics")
    assert "http_requests_total" in res.text
