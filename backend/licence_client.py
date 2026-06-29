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
from types import SimpleNamespace
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from betfair_client import betfair
from services.recovery import recovery_total

logger = logging.getLogger("layhounds.licence.client")

LICENCE_SERVER_URL = os.environ.get("LICENCE_SERVER_URL", "").rstrip("/")
LICENCE_CACHE_DAYS = int(os.environ.get("LICENCE_CACHE_DAYS", "7"))
LICENCE_REVALIDATE_HOURS = int(os.environ.get("LICENCE_REVALIDATE_HOURS", "1"))
# A heartbeat makes the central Admin view useful for operational monitoring
# without transmitting betting data, credentials, or any browser information.
LICENCE_HEARTBEAT_SECONDS = max(30, int(os.environ.get("LICENCE_HEARTBEAT_SECONDS", "120")))
LAYHOUNDS_APP_VERSION = os.environ.get("LAYHOUNDS_APP_VERSION", "unknown").strip() or "unknown"
LAYHOUNDS_BACKEND_VERSION = os.environ.get("LAYHOUNDS_BACKEND_VERSION", "").strip()
LAYHOUNDS_GIT_COMMIT = os.environ.get("GIT_COMMIT", os.environ.get("LAYHOUNDS_GIT_COMMIT", "")).strip()

LicenceStatus = Literal["active", "cancelled", "past_due", "trialing", "incomplete", "expired"]
LicenceTier = Literal["simulator_free", "live_trial", "live_paid"]


class ActivateRequest(BaseModel):
    key: str
    install_id: str = ""


class ReleaseRequest(BaseModel):
    key: str
    install_id: str


class ValidateRequest(BaseModel):
    key: str
    install_id: str


class FreeSimulatorLicenceRequest(BaseModel):
    first_name: str
    email: str
    marketing_opt_in: bool = False
    accepted_terms: bool
    accepted_privacy: bool


class ValidateResponse(BaseModel):
    ok: bool
    status: LicenceStatus
    licence_tier: LicenceTier = "live_paid"
    bound_install_id: Optional[str] = None
    current_period_end: datetime
    simulator_enabled: bool = False
    paper_live_enabled: bool = False
    live_enabled: bool = False
    trial_active: bool = False
    trial_ends_at: Optional[datetime] = None
    trial_days_remaining: int = 0
    trial_eligible: bool = False
    trial_readiness_progress: dict = Field(default_factory=dict)
    marketing_opt_in: bool = False
    message: Optional[str] = None


class LicenceStatusOut(BaseModel):
    install_id: str
    has_key: bool
    licence_key_masked: Optional[str] = None
    bound: bool
    ok: bool
    status: Optional[LicenceStatus] = None
    licence_tier: Optional[LicenceTier] = None
    current_period_end: Optional[datetime] = None
    simulator_enabled: bool = False
    paper_live_enabled: bool = False
    live_enabled: bool = False
    trial_active: bool = False
    trial_ends_at: Optional[datetime] = None
    trial_days_remaining: int = 0
    trial_eligible: bool = False
    trial_readiness_progress: dict = Field(default_factory=dict)
    marketing_opt_in: bool = False
    last_validation_at: Optional[datetime] = None
    cache_valid_until: Optional[datetime] = None
    message: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mask(key: str) -> str:
    if not key or len(key) < 8:
        return key or ""
    return f"{key[:6]}...{key[-4:]}"


def _safe_error_message(message: Optional[str]) -> Optional[str]:
    if not message:
        return None
    text = str(message)
    lowered = text.lower()
    if any(secret in lowered for secret in ("password=", "token=", "x-authentication", "app_key", "licence_key")):
        return "Redacted operational error"
    return text[:240]


def _session_result(status: Optional[str]) -> Optional[str]:
    return {
        "active": "running",
        "stopped_win": "stop_win",
        "stopped_loss": "stop_loss",
        "stopped_manual": "manually_stopped",
        "stopped_max": "manually_stopped",
    }.get(status or "")


def _environment_for_mode(mode: Optional[str]) -> str:
    return {
        "simulator": "simulator",
        "paper_live": "paper-live",
        "live": "live",
    }.get(mode or "", "paper")


def _chain_debt(chain: dict) -> float:
    return recovery_total(SimpleNamespace(**(chain or {})))


async def _central_payload(db: AsyncIOMotorDatabase, key: str, install_id: str) -> dict:
    """Return the small operational snapshot sent with an authenticated heartbeat."""
    day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    active_session = await db.sessions.find_one(
        {"status": "active"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    latest_session = await db.sessions.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    session_for_config = active_session or latest_session or {}
    config = session_for_config.get("config") or {}
    raw_mode = config.get("mode")
    today_sessions = await db.sessions.find({"created_at": {"$gte": day_start}}, {"_id": 0}).to_list(500)
    all_sessions = await db.sessions.find({}, {"_id": 0, "created_at": 1, "config": 1, "races": 1, "status": 1}).to_list(100_000)
    simulator_sessions = [
        session for session in all_sessions
        if (session.get("config") or {}).get("mode") == "simulator"
    ]
    active_days = {
        str(session.get("created_at", ""))[:10]
        for session in simulator_sessions
        if session.get("created_at")
    }
    total_races_analysed = sum(len(session.get("races") or []) for session in simulator_sessions)
    stop_win_sessions = sum(1 for session in simulator_sessions if session.get("status") == "stopped_win")

    current_recovery_debt = round(sum(_chain_debt(c) for c in ((active_session or {}).get("recovery_chains") or {}).values()), 4)
    max_recovery_debt_today = current_recovery_debt
    max_liability_used_today = 0.0
    for session in today_sessions:
        for chain in (session.get("recovery_chains") or {}).values():
            max_recovery_debt_today = max(max_recovery_debt_today, _chain_debt(chain))
        for race in session.get("races") or []:
            for bet in race.get("bets") or []:
                max_liability_used_today = max(
                    max_liability_used_today,
                    float(bet.get("liability_used") or bet.get("liability") or 0),
                )

    betfair_status = await betfair.status()
    licence_state = await _get_local_licence_state(db)
    last_error_code = None
    last_error_message = None
    if not licence_state.get("last_ok", False) and licence_state.get("message"):
        last_error_code = "LICENCE_VALIDATION_FAILED"
        last_error_message = licence_state.get("message")
    if betfair_status.get("configured") and not betfair_status.get("logged_in"):
        last_error_code = "BETFAIR_CONNECTION_FAILED"
        last_error_message = betfair_status.get("reason")

    sessions_started_today = len(today_sessions)
    return {
        "key": key,
        "install_id": install_id,
        "app_version": LAYHOUNDS_APP_VERSION,
        "backend_version": LAYHOUNDS_BACKEND_VERSION or None,
        "git_commit": LAYHOUNDS_GIT_COMMIT[:12] or None,
        "recovery_mode": config.get("recovery_mode"),
        "strategy_profile": config.get("favourite_risk_guard"),
        "environment": _environment_for_mode(raw_mode),
        "backend_status": "ok",
        "betfair_connected": bool(betfair_status.get("logged_in")),
        "licence_validation_status": "valid" if licence_state.get("last_ok", False) else "failing",
        "last_error_code": last_error_code,
        "last_error_message": _safe_error_message(last_error_message),
        "last_error_at": _now().isoformat() if last_error_code else None,
        "current_mode": raw_mode or "idle",
        "session_running": bool(active_session),
        "sessions_today": sessions_started_today,
        "sessions_started_today": sessions_started_today,
        "total_simulator_sessions": len(simulator_sessions),
        "total_races_analysed": total_races_analysed,
        "active_days_count": len(active_days),
        "stop_win_sessions": stop_win_sessions,
        "last_session_started_at": latest_session.get("created_at") if latest_session else None,
        "last_session_result": _session_result(latest_session.get("status") if latest_session else None),
        "current_recovery_debt": current_recovery_debt,
        "max_recovery_debt_today": round(max_recovery_debt_today, 4),
        "current_liability_cap": config.get("max_liability_cap"),
        "max_liability_used_today": round(max_liability_used_today, 4),
        "stop_win": config.get("stop_win"),
        "stop_loss": config.get("stop_loss"),
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
    if state.get("live_enabled") is False:
        return False, "Live access is not enabled for this licence tier"

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
            licence_tier=state.get("licence_tier"),
            current_period_end=state.get("current_period_end"),
            simulator_enabled=bool(state.get("simulator_enabled")),
            paper_live_enabled=bool(state.get("paper_live_enabled")),
            live_enabled=bool(state.get("live_enabled")),
            trial_active=bool(state.get("trial_active")),
            trial_ends_at=state.get("trial_ends_at"),
            trial_days_remaining=int(state.get("trial_days_remaining") or 0),
            trial_eligible=bool(state.get("trial_eligible")),
            trial_readiness_progress=state.get("trial_readiness_progress") or {},
            marketing_opt_in=bool(state.get("marketing_opt_in")),
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
            "licence_tier": result.get("licence_tier"),
            "bound_install_id": result.get("bound_install_id"),
            "current_period_end": result.get("current_period_end"),
            "simulator_enabled": result.get("simulator_enabled", False),
            "paper_live_enabled": result.get("paper_live_enabled", False),
            "live_enabled": result.get("live_enabled", False),
            "trial_active": result.get("trial_active", False),
            "trial_ends_at": result.get("trial_ends_at"),
            "trial_days_remaining": result.get("trial_days_remaining", 0),
            "trial_eligible": result.get("trial_eligible", False),
            "trial_readiness_progress": result.get("trial_readiness_progress") or {},
            "marketing_opt_in": result.get("marketing_opt_in", False),
            "last_validation_at": _now().isoformat(),
            "message": result.get("message"),
        })
        return await status()

    @router.post("/free-simulator", response_model=LicenceStatusOut)
    async def free_simulator(inp: FreeSimulatorLicenceRequest):
        install_id = await _get_or_create_install_id(db)
        result = await _call_central("free-simulator", {
            "first_name": inp.first_name,
            "email": inp.email,
            "marketing_opt_in": inp.marketing_opt_in,
            "accepted_terms": inp.accepted_terms,
            "accepted_privacy": inp.accepted_privacy,
            "install_id": install_id,
        })
        licence = result.get("licence") or {}
        key = licence.get("licence_key")
        if not key:
            raise HTTPException(502, "Licence server did not return a simulator licence key")
        validation = await _call_central("validate", await _central_payload(db, key, install_id))
        await _set_local_licence_state(db, {
            "key": key,
            "last_ok": validation.get("ok", False),
            "status": validation.get("status"),
            "licence_tier": validation.get("licence_tier"),
            "bound_install_id": validation.get("bound_install_id"),
            "current_period_end": validation.get("current_period_end"),
            "simulator_enabled": validation.get("simulator_enabled", False),
            "paper_live_enabled": validation.get("paper_live_enabled", False),
            "live_enabled": validation.get("live_enabled", False),
            "trial_active": validation.get("trial_active", False),
            "trial_ends_at": validation.get("trial_ends_at"),
            "trial_days_remaining": validation.get("trial_days_remaining", 0),
            "trial_eligible": validation.get("trial_eligible", False),
            "trial_readiness_progress": validation.get("trial_readiness_progress") or {},
            "marketing_opt_in": validation.get("marketing_opt_in", False),
            "last_validation_at": _now().isoformat(),
            "message": validation.get("message"),
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
            "licence_tier": result.get("licence_tier"),
            "bound_install_id": result.get("bound_install_id"),
            "current_period_end": result.get("current_period_end"),
            "simulator_enabled": result.get("simulator_enabled", False),
            "paper_live_enabled": result.get("paper_live_enabled", False),
            "live_enabled": result.get("live_enabled", False),
            "trial_active": result.get("trial_active", False),
            "trial_ends_at": result.get("trial_ends_at"),
            "trial_days_remaining": result.get("trial_days_remaining", 0),
            "trial_eligible": result.get("trial_eligible", False),
            "trial_readiness_progress": result.get("trial_readiness_progress") or {},
            "marketing_opt_in": result.get("marketing_opt_in", False),
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
                        "licence_tier": result.get("licence_tier"),
                        "bound_install_id": result.get("bound_install_id"),
                        "current_period_end": result.get("current_period_end"),
                        "simulator_enabled": result.get("simulator_enabled", False),
                        "paper_live_enabled": result.get("paper_live_enabled", False),
                        "live_enabled": result.get("live_enabled", False),
                        "trial_active": result.get("trial_active", False),
                        "trial_ends_at": result.get("trial_ends_at"),
                        "trial_days_remaining": result.get("trial_days_remaining", 0),
                        "trial_eligible": result.get("trial_eligible", False),
                        "trial_readiness_progress": result.get("trial_readiness_progress") or {},
                        "marketing_opt_in": result.get("marketing_opt_in", False),
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
