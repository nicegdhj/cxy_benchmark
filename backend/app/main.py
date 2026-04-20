import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.db import init_db
from backend.app.routers import batches as batches_router
from backend.app.routers import judges as judges_router
from backend.app.routers import models as models_router
from backend.app.routers import tasks as tasks_router
from backend.app.services.worker import worker_loop


_worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task
    init_db()
    _worker_task = asyncio.create_task(worker_loop())
    yield
    _worker_task.cancel()


app = FastAPI(title="Eval Backend", version="0.1.0", lifespan=lifespan)
app.include_router(models_router.router)
app.include_router(judges_router.router)
app.include_router(tasks_router.router)
app.include_router(batches_router.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
