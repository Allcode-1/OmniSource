import asyncio
import time
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import init_db
from app.core.redis import redis_client
from app.core.logging import configure_logging, get_logger
from app.core.metrics import metrics_registry
from app.ml.vectorizer import get_vectorizer
from app.models.content_meta import ContentMetadata
from app.auth import routes as auth
from app.api.routers import actions, content, recommendations, research, user

configure_logging()
logger = get_logger(__name__)
_startup_warmup_task: asyncio.Task[None] | None = None

async def _warmup_vectorizer() -> None:
    try:
        await asyncio.to_thread(get_vectorizer().get_embedding, "startup warmup")
        logger.info("Vectorizer warmup completed")
    except Exception as exc:
        logger.warning("Vectorizer warmup failed: %s", type(exc).__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await startup_event()
    try:
        yield
    finally:
        await shutdown_event()


async def startup_event() -> None:
    global _startup_warmup_task
    logger.info("Starting %s", settings.PROJECT_NAME)
    await init_db()
    if redis_client.enabled:
        redis_ok = await redis_client.ping()
        logger.info("Redis health: %s", "up" if redis_ok else "down")
    else:
        logger.info("Redis health: disabled")
    _startup_warmup_task = asyncio.create_task(_warmup_vectorizer())


async def shutdown_event() -> None:
    global _startup_warmup_task
    if _startup_warmup_task is not None and not _startup_warmup_task.done():
        _startup_warmup_task.cancel()
        with suppress(asyncio.CancelledError):
            await _startup_warmup_task
    _startup_warmup_task = None
    await asyncio.gather(
        content.service.close(),
        content.ml_engine.close(),
        research.engine.close(),
        return_exceptions=True,
    )
    await redis_client.close()
    logger.info("Shutdown completed")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan, root_path="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    except asyncio.CancelledError:
        duration_ms = (time.perf_counter() - start) * 1000
        status = 499
        metrics_registry.observe(
            request.method,
            request.url.path,
            status,
            duration_ms,
        )
        logger.info(
            "request_cancelled",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round(duration_ms, 2),
            },
        )
        response = Response(status_code=status)
        response.headers["x-request-id"] = request_id
        return response
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        metrics_registry.observe(
            request.method,
            request.url.path,
            status,
            duration_ms,
        )
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round(duration_ms, 2),
            },
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    metrics_registry.observe(
        request.method,
        request.url.path,
        status,
        duration_ms,
    )
    response.headers["x-request-id"] = request_id

    log_extra = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "duration_ms": round(duration_ms, 2),
    }
    if request.method == "OPTIONS":
        logger.debug("request_completed", extra=log_extra)
    else:
        logger.info("request_completed", extra=log_extra)
        if duration_ms >= settings.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning("request_slow", extra=log_extra)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )

# routs
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(content.router)
app.include_router(actions.router)
app.include_router(recommendations.router)
app.include_router(research.router)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "redis": await redis_client.health_status(),
        "ml": {
            "vector_index_enabled": settings.ML_VECTOR_INDEX_ENABLED,
            "vector_index_max_items": settings.ML_VECTOR_INDEX_MAX_ITEMS,
            "vector_backend": settings.ML_VECTOR_BACKEND,
        },
    }


@app.get("/diagnostics")
async def diagnostics():
    total = await ContentMetadata.find().count()
    vectorized = await ContentMetadata.find(
        {"features_vector.0": {"$exists": True}},
    ).count()
    return {
        "status": "ok",
        "redis": await redis_client.health_status(),
        "ml": {
            "vector_index_enabled": settings.ML_VECTOR_INDEX_ENABLED,
            "vector_index_ttl_seconds": settings.ML_VECTOR_INDEX_TTL_SECONDS,
            "vector_index_max_items": settings.ML_VECTOR_INDEX_MAX_ITEMS,
            "vector_backend": settings.ML_VECTOR_BACKEND,
            "vector_search_multiplier": settings.ML_VECTOR_SEARCH_MULTIPLIER,
            "event_weights": {
                "view": settings.ML_EVENT_WEIGHT_VIEW,
                "open_detail": settings.ML_EVENT_WEIGHT_OPEN_DETAIL,
                "dwell_time": settings.ML_EVENT_WEIGHT_DWELL_TIME,
                "like": settings.ML_EVENT_WEIGHT_LIKE,
                "playlist_add": settings.ML_EVENT_WEIGHT_PLAYLIST_ADD,
            },
            "score_weights": {
                "similarity": settings.ML_HYBRID_SIMILARITY_WEIGHT,
                "rating": settings.ML_HYBRID_RATING_WEIGHT,
                "genre": settings.ML_HYBRID_GENRE_WEIGHT,
            },
        },
        "catalog": {
            "total_documents": total,
            "vectorized_documents": vectorized,
            "vector_coverage": round(vectorized / total, 4) if total else 0.0,
        },
        "cache": {
            "warmup_tag_limit": settings.CACHE_WARMUP_TAG_LIMIT,
            "warmup_user_limit": settings.CACHE_WARMUP_USER_LIMIT,
        },
    }


@app.get("/metrics")
async def metrics():
    return Response(
        content=metrics_registry.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
