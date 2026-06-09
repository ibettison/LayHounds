import asyncio
import logging
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from db import client, db
from licence_client import (
    LICENCE_SERVER_URL,
    background_revalidate_loop,
    build_customer_router,
)
from routes import betfair, sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(sessions.router)
app.include_router(betfair.router)

# Customer licence router: safe for public/customer installs.
if LICENCE_SERVER_URL:
    app.include_router(build_customer_router(db), prefix="/api")

# Private central licence router: only available in the private licensing repo/deploy.
LICENCE_SERVER_MODE = (os.environ.get("LICENCE_SERVER_MODE", "false").lower() == "true")
if LICENCE_SERVER_MODE:
    try:
        from licence_server import build_central_router
    except ImportError as e:
        raise RuntimeError(
            "LICENCE_SERVER_MODE=true but the private licence_server module is not installed"
        ) from e
    app.include_router(build_central_router(db), prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_tasks():
    if LICENCE_SERVER_URL:
        asyncio.create_task(background_revalidate_loop(db))
        logger.info("Licence revalidate loop scheduled (LICENCE_SERVER_URL=%s)", LICENCE_SERVER_URL)
    if LICENCE_SERVER_MODE:
        logger.info("Running in CENTRAL LICENCE SERVER mode - /api/licences/* + /api/webhook/stripe live")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
