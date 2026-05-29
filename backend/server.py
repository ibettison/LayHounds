import asyncio
import logging
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from db import client, db
from licences import (
    LICENCE_SERVER_MODE,
    LICENCE_SERVER_URL,
    background_revalidate_loop,
    build_central_router,
    build_customer_router,
)
from routes import betfair, payments, sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(sessions.router)
app.include_router(betfair.router)
app.include_router(payments.router)

# Licence routers (always mount the customer one; mount central only on the host with LICENCE_SERVER_MODE=true)
if LICENCE_SERVER_URL:
    app.include_router(build_customer_router(db), prefix="/api")
if LICENCE_SERVER_MODE:
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
