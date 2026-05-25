from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
import os
import time

app = FastAPI(title="k8s-rollback-lab")

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENV = os.getenv("APP_ENV", "development")

FORCE_NOT_READY = os.getenv("FORCE_NOT_READY", "false").lower() == "true"
SLOW_READY_MS = int(os.getenv("SLOW_READY_MS", "0"))

# /metrics 엔드포인트 자동 생성
# Prometheus가 이 주소를 주기적으로 긁어서 데이터 수집 (scraping)
Instrumentator().instrument(app).expose(app)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if SLOW_READY_MS > 0:
        time.sleep(SLOW_READY_MS / 1000)

    if FORCE_NOT_READY:
        raise HTTPException(status_code=503, detail="readiness check failed (v2 fault injection)")

    return {"status": "ready"}


@app.get("/info")
def info():
    return {
        "version": APP_VERSION,
        "env": APP_ENV,
        "fault_injection": {
            "force_not_ready": FORCE_NOT_READY,
            "slow_ready_ms": SLOW_READY_MS,
        },
    }
