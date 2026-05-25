from fastapi import FastAPI, HTTPException
import os
import time

app = FastAPI(title="k8s-rollback-lab")

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENV = os.getenv("APP_ENV", "development")

# v2 fault injection: FORCE_NOT_READY=true 이면 /ready 가 항상 503 반환
FORCE_NOT_READY = os.getenv("FORCE_NOT_READY", "false").lower() == "true"

# v2 fault injection: SLOW_READY_MS 설정 시 /ready 응답 지연 (ms)
SLOW_READY_MS = int(os.getenv("SLOW_READY_MS", "0"))


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
