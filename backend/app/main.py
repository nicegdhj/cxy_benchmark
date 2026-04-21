import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.app.config import get_settings
from backend.app.db import init_db
from backend.app.routers import batches as batches_router
from backend.app.routers import judges as judges_router
from backend.app.routers import jobs as jobs_router
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


def _auth_middleware(request: Request, call_next):
    """全局 Bearer token 鉴权中间件。/health 免认证；若未配置 auth_token 则跳过。"""
    if request.url.path in ("/api/v1/health", "/docs", "/openapi.json", "/redoc"):
        return call_next(request)
    settings = get_settings()
    if settings.auth_token is None:
        return call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {settings.auth_token}":
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized"},
        )
    return call_next(request)


app = FastAPI(title="Eval Backend", version="0.1.0", lifespan=lifespan)
app.middleware("http")(_auth_middleware)
app.include_router(models_router.router)
app.include_router(judges_router.router)
app.include_router(tasks_router.router)
app.include_router(batches_router.router)
app.include_router(jobs_router.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
