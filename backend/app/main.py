from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Eval Backend", version="0.1.0", lifespan=lifespan)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
