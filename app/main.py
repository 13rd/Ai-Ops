import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.responses import fail, ok
from app.services.ml.registry import warmup as ml_warmup
from app.services.scheduler.collector_scheduler import scheduler
from app.services.scheduler.ml_analysis_job import MLAnalysisJob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    await scheduler.start()
    ml_warmup()
    ml_job = MLAnalysisJob()
    await ml_job.start()
    app.state.ml_job = ml_job
    yield
    logger.info("Shutting down application...")
    await app.state.ml_job.stop()
    await scheduler.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


def _resolve_cors_origins() -> list[str]:
    """Resolve allowed CORS origins.

    Browsers reject wildcard origins combined with credentialed requests
    (cookies), so when BACKEND_CORS_ORIGINS is empty or "*", fall back to
    the explicit FRONTEND_URL.
    """
    raw = settings.BACKEND_CORS_ORIGINS
    if not raw or raw.strip() == "*":
        return [settings.FRONTEND_URL]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return fail(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("detail") or "HTTP error"
        code = detail.get("code", f"http_{exc.status_code}")
        details = detail.get("details")
    else:
        message = str(detail) if detail else "HTTP error"
        code = f"http_{exc.status_code}"
        details = None
    return fail(code=code, message=message, details=details, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return fail(
        code="validation_error",
        message="Request validation failed",
        details={"errors": jsonable_encoder(exc.errors())},
        status_code=422,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc)
    return fail(
        code="internal_error",
        message="Internal server error",
        status_code=500,
    )


@app.get("/health")
async def health_check():
    return ok(
        data={
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        },
        message="OK",
    )


app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
