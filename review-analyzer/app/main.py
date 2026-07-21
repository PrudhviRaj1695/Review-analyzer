import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.routers.compare import router as compare_router
from app.routers.products import router as products_router
from app.routers.reviews import router as reviews_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """App startup and shutdown events."""
    # Database migrations are now managed by Alembic
    # Run 'alembic upgrade head' before starting the app
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(lifespan=lifespan)
app.include_router(products_router)
app.include_router(reviews_router)
app.include_router(compare_router)


@app.get("/")
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
