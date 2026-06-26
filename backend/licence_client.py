"""Customer-side licence client.

This module is safe to ship in the public/customer application. It only stores
the local install ID and cached licence state, then validates keys against the
separate central licensing service configured by LICENCE_SERVER_URL.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

logger = logging.getLogger("layhounds.licence.client")

LICENCE_SERVER_URL = os.environ.get("LICENCE_SERVER_URL", "").rstrip("/")
LICENCE_CACHE_DAYS = int(os.environ.get("LICENCE_CACHE_DAYS", "7"))
LICENCE_REVALIDATE_HOURS = int(os.environ.get("LICENCE_REVALIDATE_HOURS", "1"))
# A heartbeat makes the central Admin view useful for operational monitoring
# without transmitting betting data, credentials, or any browser information.
LICENCE_HEARTBEAT_SECONDS = max(30, int(os.environ.get("LICENCE_HEARTBEAT_SECONDS", "120")))
LAYHOUNDS_APP_VERSION = os.environ.get("LAYHOUNDS_APP_VERSION", "unknown").strip() or "unknown"

LicenceStatus = Literal["active", "cancelled", "past_due", "trialing", "incomplete"]


class ActivateRequest(BaseModel):
    key: str
    install_id: str = ""


class ReleaseRequest(BaseModel):
    key: str
    install_id: str


class ValidateRequest(BaseModel):
    key: str
    install_id: str


class ValidateResponse(BaseModel):
    ok: bool
    status: LicenceStatus
    bound_install_id: Optional[str] = None
    current_period_end: datetime
    message: Optional[str] = None


class LicenceStatusOut(BaseModel):
    install_id: str
    has_key: bool
    licence_key_masked: Optional[str] = None
    bound: bool
    ok: bool
    status: Optional[LicenceStatus] = None
    current_period_end: Optional[datetime] = None
    last_validation_at: Optional[datetime] = None
    cache_valid_until: Optional[datetime] = None
    message: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mask(key: str) -> str:
    if not key or len(key) < 8:
        return key or ""
    return f"{key[:6]}...{key[-4:]}"


async def _central_payload(db: AsyncIOMotorDatabase, key: str, install_id: str) -> dict:
    """Return the small operational snapshot sent with an authenticated heartbeat."""
    day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    active_session = await db.sessions.find_one(
        {"status": "active"},
        {"_id": 0, "config.mode": 1},
        sort=[("created_at", -1)],
    )
    raw_mode = ((active_session or {}).get("config") or {}).get("mode")
    current_mode = {"simulator": "paper", "paper_live": "paper_live", "live": "live"}.get(raw_mode, "idle")
    sessions_started_today = await db.sessions.count_documents({"created_at": {"$gte": day_start}})
    return {
        "key": key,
        "install_id": install_id,
        "app_version": LAYHOUNDS_APP_VERSION,
        "current_mode": current_mode,
        "sessions_started_today": sessions_started_today,
    }


async def _get_or_create_install_id(db: AsyncIOMotorDatabase) -> str:
    doc = await db.app_meta.find_one({"_meta_key": "install_id"}, {"_id": 0})
    if doc:
        return doc["value"]
    new_id = str(uuid.uuid4())
    await db.app_meta.insert_one({"_meta_key": "install_id", "value": new_id, "created_at": _now().isoformat()})
    return new_id


async def _get_local_licence_state(db: AsyncIOMotorDatabase) -> dict:
    doc = await db.app_meta.find_one({"_meta_key": "licence_state"}, {"_id": 0})
    return (doc or {}).get("value", {})


async def _set_local_licence_state(db: AsyncIOMotorDatabase, value: dict) -> None:
    await db.app_meta.update_one(
        {"_meta_key": "licence_state"},
        {"$set": {"_meta_key": "licence_state", "value": value, "updated_at": _now().isoformat()}},
        upsert=True,
    )


async def is_licence_active(db: AsyncIOMotorDatabase) -> tuple[bool, str]:
    state = await _get_local_licence_state(db)
    if not state.get("key"):
        return False, "No licence key activated on this install"
    if not state.get("last_ok"):
        return False, state.get("message") or "Last validation failed"

    last_validation_at = state.get("last_validation_at")
    if last_validation_at:
        last_dt = datetime.fromisoformat(last_validation_at.replace("Z", "+00:00"))
        if _now() - last_dt > timedelta(days=LICENCE_CACHE_DAYS):
            return False, f"Validation cache expired ({LICENCE_CACHE_DAYS} days). Reconnect to the licence server."

    period_end = state.get("current_period_end")
    if period_end:
        pe = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
        if pe < _now():
            return False, "Subscription period ended"

    return True, "ok"


async def _call_central(endpoint: str, payload: dict) -> dict:
    if not LICENCE_SERVER_URL:
        raise HTTPException(500, "LICENCE_SERVER_URL not configured on this install")

    url = f"{LICENCE_SERVER_URL}/api/licences/{endpoint}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Could not reach licence server: {type(e).__name__}: {e}")

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        if resp.status_code == 404 and (detail or "").lower() in ("not found", "not-found"):
            raise HTTPException(
                404,
                f"Licence server at {LICENCE_SERVER_URL} is reachable but /api/licences/{endpoint} is not mounted.",
            )
        raise HTTPException(resp.status_code, f"Licence server: {detail}")

    return resp.json()


def build_customer_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/licence")

    @router.get("/status", response_model=LicenceStatusOut)
    async def status():
        install_id = await _get_or_create_install_id(db)
        state = await _get_local_licence_state(db)
        key = state.get("key")
        last_at = state.get("last_validation_at")
        cache_until = None
        if last_at:
            last_dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
            cache_until = last_dt + timedelta(days=LICENCE_CACHE_DAYS)

        return LicenceStatusOut(
            install_id=install_id,
            has_key=bool(key),
            licence_key_masked=_mask(key) if key else None,
            bound=bool(state.get("bound_install_id") == install_id),
            ok=state.get("last_ok", False),
            status=state.get("status"),
            current_period_end=state.get("current_period_end"),
            last_validation_at=last_at,
            cache_valid_until=cache_until.isoformat() if cache_until else None,
            message=state.get("message"),
        )

    @router.post("/activate", response_model=LicenceStatusOut)
    async def activate(inp: ActivateRequest):
        install_id = await _get_or_create_install_id(db)
        if inp.install_id and inp.install_id != install_id:
            raise HTTPException(400, "install_id mismatch; refresh the page and try again")
        result = await _call_central("activate", await _central_payload(db, inp.key, install_id))
        await _set_local_licence_state(db, {
            "key": inp.key,
            "last_ok": result.get("ok", False),
            "status": result.get("status"),
            "bound_install_id": result.get("bound_install_id"),
            "current_period_end": result.get("current_period_end"),
            "last_validation_at": _now().isoformat(),
            "message": result.get("message"),
        })
        return await status()

    @router.post("/release", response_model=LicenceStatusOut)
    async def release():
        install_id = await _get_or_create_install_id(db)
        state = await _get_local_licence_state(db)
        key = state.get("key")
        if not key:
            raise HTTPException(400, "No licence to release on this install")
        try:
            await _call_central("release", {"key": key, "install_id": install_id})
        finally:
            await _set_local_licence_state(db, {})
        return await status()

    @router.post("/refresh", response_model=LicenceStatusOut)
    async def refresh():
        install_id = await _get_or_create_install_id(db)
        state = await _get_local_licence_state(db)
        key = state.get("key")
        if not key:
            raise HTTPException(400, "Nothing to refresh; activate a licence first")
        result = await _call_central("validate", await _central_payload(db, key, install_id))
        await _set_local_licence_state(db, {
            **state,
            "last_ok": result.get("ok", False),
            "status": result.get("status"),
            "bound_install_id": result.get("bound_install_id"),
            "current_period_end": result.get("current_period_end"),
            "last_validation_at": _now().isoformat(),
            "message": result.get("message"),
        })
        return await status()

    @router.get("/diag")
    async def diag():
        install_id = await _get_or_create_install_id(db)
        diag_info = {
            "install_id": install_id,
            "config": {
                "LICENCE_SERVER_URL": LICENCE_SERVER_URL or "(not set)",
                "LICENCE_CACHE_DAYS": LICENCE_CACHE_DAYS,
                "LICENCE_REVALIDATE_HOURS": LICENCE_REVALIDATE_HOURS,
                "LICENCE_HEARTBEAT_SECONDS": LICENCE_HEARTBEAT_SECONDS,
                "LAYHOUNDS_APP_VERSION": LAYHOUNDS_APP_VERSION,
            },
            "connectivity": None,
        }
        if LICENCE_SERVER_URL:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{LICENCE_SERVER_URL}/api/")
                diag_info["connectivity"] = {
                    "url": f"{LICENCE_SERVER_URL}/api/",
                    "http_status": resp.status_code,
                    "ok": resp.status_code == 200,
                }
            except Exception as e:
                diag_info["connectivity"] = {
                    "url": f"{LICENCE_SERVER_URL}/api/",
                    "http_status": None,
                    "ok": False,
                    "error": f"{type(e).__name__}: {e}",
                }
        return diag_info

    return router


async def background_revalidate_loop(db: AsyncIOMotorDatabase) -> None:
    while True:
        try:
            state = await _get_local_licence_state(db)
            key = state.get("key")
            if key:
                install_id = await _get_or_create_install_id(db)
                try:
                    result = await _call_central("validate", await _central_payload(db, key, install_id))
                    await _set_local_licence_state(db, {
                        **state,
                        "last_ok": result.get("ok", False),
                        "status": result.get("status"),
                        "bound_install_id": result.get("bound_install_id"),
                        "current_period_end": result.get("current_period_end"),
                        "last_validation_at": _now().isoformat(),
                        "message": result.get("message"),
                    })
                except HTTPException as e:
                    logger.warning("Licence revalidation failed: %s (will retry next cycle)", e.detail)
        except Exception:
            logger.exception("Background revalidate loop crashed; restarting")
        await asyncio.sleep(LICENCE_REVALIDATE_HOURS * 3600)


async def background_heartbeat_loop(db: AsyncIOMotorDatabase) -> None:
    """Keep the central install record current while this LayHounds server runs.

    The existing authenticated validation endpoint doubles as the heartbeat.  It
    accepts only the locally stored licence key and install ID, so arbitrary
    callers cannot create an active-install record merely by guessing an ID.
    The hourly revalidation loop remains responsible for updating the local
    cached licence state; this loop only reports liveness to the Admin service.
    """
    while True:
        try:
            state = await _get_local_licence_state(db)
            key = state.get("key")
            if key:
                install_id = await _get_or_create_install_id(db)
                try:
                    await _call_central("validate", await _central_payload(db, key, install_id))
                except HTTPException as e:
                    logger.warning("Licence heartbeat failed: %s (will retry shortly)", e.detail)
        except Exception:
            logger.exception("Licence heartbeat loop crashed; restarting")
        await asyncio.sleep(LICENCE_HEARTBEAT_SECONDS)
