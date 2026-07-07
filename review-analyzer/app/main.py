from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from datetime import datetime
import asyncio
import time

from app.routers.products import router as products_router
from app.routers.reviews import router as reviews_router

app = FastAPI()
app.include_router(products_router)
app.include_router(reviews_router)


@app.get("/")
def health_check():
    return {"message": "✓ API is healthy and ready", "status": "operational"}


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
    print("blocking start", datetime.now().isoformat())
    time.sleep(3)
    print("blocking end", datetime.now().isoformat())
    return {"message": "blocking complete"}


@app.get("/demo-async")
async def demo_async():
    print("async start", datetime.now().isoformat())
    await asyncio.sleep(3)
    print("async end", datetime.now().isoformat())
    return {"message": "async complete"}
