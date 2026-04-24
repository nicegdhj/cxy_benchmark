import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.app.config import get_settings
from backend.app.db import init_db, get_session
from backend.app.routers import batches as batches_router
from backend.app.routers import evaluations as evaluations_router
from backend.app.routers import judges as judges_router
from backend.app.routers import jobs as jobs_router
from backend.app.routers import models as models_router
from backend.app.routers import predictions as predictions_router
from backend.app.routers import tasks as tasks_router
from backend.app.services.seed import seed_generic_tasks, seed_custom_tasks
from backend.app.services.worker import worker_loop

_DEFAULT_GENERIC = [
    "ceval_gen_0_shot_str", "mmlu_redux_gen_5_shot_str", "teledata_gen_0_shot",
    "gpqa_gen_0_shot_str", "bbh_gen_3_shot_cot_chat", "BFCL_gen_simple",
    "ifeval_0_shot_gen_str", "math500_gen_0_shot_cot_chat_prompt",
    "aime2025_gen_0_shot_chat_prompt", "telemath_gen_0_cot_shot",
    "teleqna_gen_0_shot", "tspec_gen_0_shot", "telequad_gen_0_shot",
    "tele_exam_gen_0_shot", "tele_exam_gen_0_shot_str", "opseval_gen_0_shot",
    "identity_gen_0_shot", "exam_gen_0_shot",
]
_DEFAULT_CUSTOM = [1, 34, 36, 43, 44, 60]

_worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task
    init_db()
    try:
        with get_session() as session:
            seed_generic_tasks(session, _DEFAULT_GENERIC)
            seed_custom_tasks(session, _DEFAULT_CUSTOM)
            session.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Auto-seed tasks failed: %s", e)
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
app.include_router(predictions_router.router)
app.include_router(evaluations_router.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
