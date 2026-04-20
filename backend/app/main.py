from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.app.db import init_db
from backend.app.routers import judges as judges_router
from backend.app.routers import models as models_router
from backend.app.routers import tasks as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Eval Backend", version="0.1.0", lifespan=lifespan)
app.include_router(models_router.router)
app.include_router(judges_router.router)
app.include_router(tasks_router.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}