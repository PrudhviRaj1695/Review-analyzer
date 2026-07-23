import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.logging_config import request_id_var
from app.routers.compare import router as compare_router
from app.routers.products import router as products_router
from app.routers.reviews import router as reviews_router
from app.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """App startup and shutdown events."""
    # Database migrations are now managed by Alembic
    # Run 'alembic upgrade head' before starting the app
    logger.info("Application startup")
    yield
    logger.info("Application shutdown")


app = FastAPI(lifespan=lifespan)
app.include_router(products_router)
app.include_router(reviews_router)
app.include_router(compare_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One log line per request: method, path, status, duration_ms.

    A request_id is generated per request, stamped onto every log line
    emitted while handling it (via request_id_var), and returned as
    X-Request-ID. Requests slower than settings.http_slow_request_seconds
    log at WARNING instead of INFO so they visibly stand out.

    Unhandled exceptions are caught here (not via @app.exception_handler,
    which runs in Starlette's ServerErrorMiddleware *outside* this
    middleware — by the time it ran, our finally below would already have
    reset request_id_var) so the traceback log and the X-Request-ID header
    both still see the request's id.
    """
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled exception during %s %s", request.method, request.url.path
            )
            response = JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )
        duration_ms = (time.perf_counter() - start) * 1000

        log = (
            logger.warning
            if duration_ms / 1000 > settings.http_slow_request_seconds
            else logger.info
        )
        log(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


@app.get("/")
@app.get("/health")
def health_check():
    return {
        "message": "✓ API is healthy and ready",
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/command-center", response_class=HTMLResponse)
def command_center():
    return """
    <html>
        <head>
            <title>Review Analyzer</title>
        </head>
        <body>
            <h1>Review Analyzer</h1>
            <p>Command Center</p>
        </body>
    </html>
    """


@app.get("/demo-blocking")
def demo_blocking():
    logger.info("blocking start at %s", datetime.now().isoformat())
    time.sleep(3)
    logger.info("blocking end at %s", datetime.now().isoformat())
    return {"message": "blocking complete"}


@app.get("/demo-async")
async def demo_async():
    logger.info("async start at %s", datetime.now().isoformat())
    await asyncio.sleep(3)
    logger.info("async end at %s", datetime.now().isoformat())
    return {"message": "async complete"}
