from fastapi import FastAPI
import os

app = FastAPI(title="k8s-rollback-lab")

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENV = os.getenv("APP_ENV", "development")

_ready = True


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not _ready:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready"}


@app.get("/info")
def info():
    return {
        "version": APP_VERSION,
        "env": APP_ENV,
    }
