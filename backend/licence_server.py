"""Central licence-management module.

Two distinct roles served from the same FastAPI process, gated by env vars:

  • CENTRAL ROLE (lay-hounds.co.uk):
      `LICENCE_SERVER_MODE=true` in backend/.env
      Exposes /api/licences/activate, /release, /validate, /webhook/stripe
      Stores Licence + Install + PaymentTransaction collections.

  • CUSTOMER ROLE (each customer's VPS):
      `LICENCE_SERVER_URL=https://lay-hounds.co.uk` in backend/.env
      Exposes /api/licence/status, /activate, /release (locally).
      On startup writes a UUID install_id into Mongo `app_meta` (one row, idempotent).
      Validates against LICENCE_SERVER_URL every hour, caches result for 7 days.

A box can be both (the central server is also a customer to itself for the demo / dev flow).
"""
from __future__ import annotations

import os
import secrets
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Literal

import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("layhounds.licence")

# ---- Config (read at import time) -----------------------------------------
LICENCE_SERVER_MODE = (os.environ.get("LICENCE_SERVER_MODE", "false").lower() == "true")
LICENCE_SERVER_URL = os.environ.get("LICENCE_SERVER_URL", "").rstrip("/")
LICENCE_PRICE_GBP = float(os.environ.get("LICENCE_PRICE_GBP", "19.99"))
LICENCE_CACHE_DAYS = int(os.environ.get("LICENCE_CACHE_DAYS", "7"))
LICENCE_REVALIDATE_HOURS = int(os.environ.get("LICENCE_REVALIDATE_HOURS", "1"))

# ---- Pydantic models ------------------------------------------------------

LicenceStatus = Literal["active", "cancelled", "past_due", "trialing", "incomplete"]


class Licence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    licence_key: str
    email: str
    provider: Literal["stripe", "paypal", "manual"]
    provider_subscription_id: Optional[str] = None
    provider_customer_id: Optional[str] = None
    status: LicenceStatus = "active"
    current_period_end: datetime
    bound_install_id: Optional[str] = None
    bound_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Install(BaseModel):
    install_id: str
    licence_id: Optional[str] = None
    licence_key: Optional[str] = None
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_validation_ok: bool = False
    last_validation_at: Optional[datetime] = None
    app_version: Optional[str] = None
    backend_version: Optional[str] = None
    git_commit: Optional[str] = None
    recovery_mode: Optional[str] = None
    strategy_profile: Optional[str] = None
    environment: Optional[Literal["simulator", "paper", "paper-live", "live"]] = None
    backend_status: Optional[str] = None
    betfair_connected: Optional[bool] = None
    licence_validation_status: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    last_error_at: Optional[datetime] = None
    current_mode: Optional[str] = None
    session_running: bool = False
    sessions_today: int = 0
    sessions_started_today: int = 0
    last_session_started_at: Optional[datetime] = None
    last_session_result: Optional[str] = None
    current_recovery_debt: Optional[float] = None
    max_recovery_debt_today: Optional[float] = None
    current_liability_cap: Optional[float] = None
    max_liability_used_today: Optional[float] = None
    stop_win: Optional[float] = None
    stop_loss: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    amount: float
    currency: str = "gbp"
    metadata: dict = Field(default_factory=dict)
    payment_status: str = "initiated"  # initiated|paid|failed|expired
    email: Optional[str] = None
    licence_key: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActivateRequest(BaseModel):
    key: str
    install_id: str


class ReleaseRequest(BaseModel):
    key: str
    install_id: str


class ValidateRequest(BaseModel):
    key: str
    install_id: str
    app_version: Optional[str] = None
    backend_version: Optional[str] = None
    git_commit: Optional[str] = None
    recovery_mode: Optional[str] = None
    strategy_profile: Optional[str] = None
    environment: Optional[Literal["simulator", "paper", "paper-live", "live"]] = None
    backend_status: Optional[str] = None
    betfair_connected: Optional[bool] = None
    licence_validation_status: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    last_error_at: Optional[datetime] = None
    current_mode: Optional[str] = None
    session_running: Optional[bool] = None
    sessions_today: Optional[int] = None
    sessions_started_today: Optional[int] = None
    last_session_started_at: Optional[datetime] = None
    last_session_result: Optional[str] = None
    current_recovery_debt: Optional[float] = None
    max_recovery_debt_today: Optional[float] = None
    current_liability_cap: Optional[float] = None
    max_liability_used_today: Optional[float] = None
    stop_win: Optional[float] = None
    stop_loss: Optional[float] = None


class ValidateResponse(BaseModel):
    ok: bool
    status: LicenceStatus
    bound_install_id: Optional[str] = None
    current_period_end: datetime
    message: Optional[str] = None


class LicenceStatusOut(BaseModel):
    """Customer-side view shown in the simulator UI."""
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


# ---- Helpers --------------------------------------------------------------

def _generate_licence_key() -> str:
    """Human-friendly key: LH-XXXX-XXXX-XXXX-XXXX  (URL-safe, base32-ish)."""
    raw = secrets.token_hex(8).upper()  # 16 hex chars
    chunks = [raw[i:i + 4] for i in range(0, 16, 4)]
    return "LH-" + "-".join(chunks)


def _mask(key: str) -> str:
    if not key or len(key) < 8:
        return key or ""
    return f"{key[:6]}…{key[-4:]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_licence_usable(lic: Licence | dict) -> bool:
    """A licence is usable if its status is active/trialing AND we're inside current_period_end."""
    if isinstance(lic, Licence):
        status, period_end = lic.status, lic.current_period_end
    else:
        status = lic.get("status")
        period_end = lic.get("current_period_end")
        if isinstance(period_end, str):
            period_end = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
    return status in ("active", "trialing") and (period_end is None or period_end > _now())


SAFE_INSTALL_FIELDS = {
    "app_version",
    "backend_version",
    "git_commit",
    "recovery_mode",
    "strategy_profile",
    "environment",
    "backend_status",
    "betfair_connected",
    "licence_validation_status",
    "last_error_code",
    "last_error_message",
    "last_error_at",
    "current_mode",
    "session_running",
    "sessions_today",
    "sessions_started_today",
    "last_session_started_at",
    "last_session_result",
    "current_recovery_debt",
    "max_recovery_debt_today",
    "current_liability_cap",
    "max_liability_used_today",
    "stop_win",
    "stop_loss",
}


def _safe_install_payload(inp: ValidateRequest) -> dict[str, Any]:
    payload = inp.model_dump(exclude={"key", "install_id"}, exclude_none=True)
    safe = {k: v for k, v in payload.items() if k in SAFE_INSTALL_FIELDS}
    if "last_error_message" in safe:
        safe["last_error_message"] = str(safe["last_error_message"])[:240]
    return safe


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _version_parts(version: Optional[str]) -> tuple[int, ...]:
    if not version:
        return tuple()
    parts = []
    for chunk in str(version).strip().lstrip("v").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


async def _latest_app_version(db: AsyncIOMotorDatabase) -> Optional[str]:
    env_version = os.environ.get("LAYHOUNDS_LATEST_APP_VERSION", "").strip()
    if env_version:
        return env_version
    versions = await db.installs.distinct("app_version")
    parsed = [v for v in versions if v and v != "unknown"]
    if not parsed:
        return None
    return sorted(parsed, key=_version_parts)[-1]


def _is_old_version(app_version: Optional[str], latest_version: Optional[str]) -> bool:
    if not app_version or not latest_version or app_version == "unknown":
        return False
    return _version_parts(app_version) < _version_parts(latest_version)


def _install_alerts(install: dict, *, latest_version: Optional[str], now: datetime) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    last_seen = _parse_dt(install.get("last_seen_at"))
    if last_seen and now - last_seen > timedelta(hours=24):
        alerts.append({"code": "offline_24h", "severity": "warning", "message": "Install offline for more than 24 hours"})
    if install.get("last_validation_ok") is False or install.get("licence_validation_status") == "failing":
        alerts.append({"code": "licence_validation_failing", "severity": "error", "message": "Licence validation failing"})
    if install.get("betfair_connected") is False:
        alerts.append({"code": "betfair_connection_failing", "severity": "warning", "message": "Betfair connection failing"})
    if _is_old_version(install.get("app_version"), latest_version):
        alerts.append({"code": "old_version", "severity": "warning", "message": "Old version detected"})
    if install.get("last_error_code"):
        alerts.append({"code": "backend_errors", "severity": "error", "message": "Repeated backend errors"})
    return alerts


# ===========================================================================
# CENTRAL ROLE
# ===========================================================================

def build_central_router(db: AsyncIOMotorDatabase) -> APIRouter:
    """Endpoints exposed by lay-hounds.co.uk for all customer installs to call."""
    r = APIRouter(prefix="/licences")

    @r.post("/activate", response_model=ValidateResponse)
    async def activate(inp: ActivateRequest):
        lic_doc = await db.licences.find_one({"licence_key": inp.key}, {"_id": 0})
        if not lic_doc:
            raise HTTPException(404, "Licence key not found")
        lic = Licence(**lic_doc)
        if not _is_licence_usable(lic):
            return ValidateResponse(
                ok=False, status=lic.status, current_period_end=lic.current_period_end,
                message=f"Subscription not active (status={lic.status})",
            )
        if lic.bound_install_id and lic.bound_install_id != inp.install_id:
            raise HTTPException(409,
                "Licence is already bound to another install. Release it on the other VPS first, "
                "or use the customer portal to manage."
            )
        if not lic.bound_install_id:
            lic.bound_install_id = inp.install_id
            lic.bound_at = _now()
            lic.updated_at = _now()
            await db.licences.replace_one({"id": lic.id}, lic.model_dump(mode="json"))
        await db.installs.update_one(
            {"install_id": inp.install_id},
            {"$set": {
                "install_id": inp.install_id,
                "licence_id": lic.id,
                "licence_key": lic.licence_key,
                "last_validation_ok": True,
                "last_validation_at": _now().isoformat(),
                "last_seen_at": _now().isoformat(),
                **_safe_install_payload(inp),
            }, "$unset": {"ip": "", "user_agent": ""}},
            upsert=True,
        )
        return ValidateResponse(
            ok=True, status=lic.status,
            bound_install_id=lic.bound_install_id,
            current_period_end=lic.current_period_end,
        )

    @r.post("/release", response_model=ValidateResponse)
    async def release(inp: ReleaseRequest):
        lic_doc = await db.licences.find_one({"licence_key": inp.key}, {"_id": 0})
        if not lic_doc:
            raise HTTPException(404, "Licence key not found")
        lic = Licence(**lic_doc)
        if lic.bound_install_id != inp.install_id:
            raise HTTPException(403, "This install is not bound to that licence")
        lic.bound_install_id = None
        lic.bound_at = None
        lic.updated_at = _now()
        await db.licences.replace_one({"id": lic.id}, lic.model_dump(mode="json"))
        return ValidateResponse(
            ok=False, status=lic.status,
            bound_install_id=None,
            current_period_end=lic.current_period_end,
            message="Released. Activate on another install when ready.",
        )

    @r.post("/validate", response_model=ValidateResponse)
    async def validate(inp: ValidateRequest, request: Request):
        lic_doc = await db.licences.find_one({"licence_key": inp.key}, {"_id": 0})
        if not lic_doc:
            raise HTTPException(404, "Licence key not found")
        lic = Licence(**lic_doc)
        usable = _is_licence_usable(lic)
        # Heartbeat: update install last_seen
        await db.installs.update_one(
            {"install_id": inp.install_id},
            {"$set": {
                "install_id": inp.install_id,
                "licence_id": lic.id,
                "licence_key": lic.licence_key,
                "last_validation_ok": usable and lic.bound_install_id == inp.install_id,
                "last_validation_at": _now().isoformat(),
                "last_seen_at": _now().isoformat(),
                **_safe_install_payload(inp),
            }, "$unset": {"ip": "", "user_agent": ""}},
            upsert=True,
        )
        if lic.bound_install_id and lic.bound_install_id != inp.install_id:
            return ValidateResponse(
                ok=False, status=lic.status,
                bound_install_id=lic.bound_install_id,
                current_period_end=lic.current_period_end,
                message="Licence bound to a different install_id",
            )
        return ValidateResponse(
            ok=usable, status=lic.status,
            bound_install_id=lic.bound_install_id,
            current_period_end=lic.current_period_end,
        )

    @r.get("/admin/operations")
    async def operations_dashboard():
        now = _now()
        latest_version = await _latest_app_version(db)
        installs = await db.installs.find({}, {"_id": 0, "ip": 0, "user_agent": 0}).sort("last_seen_at", -1).to_list(1000)
        licences = await db.licences.find({}, {"_id": 0, "licence_key": 1, "status": 1, "current_period_end": 1}).to_list(1000)
        licence_by_key = {lic.get("licence_key"): lic for lic in licences}

        rows = []
        for install in installs:
            lic = licence_by_key.get(install.get("licence_key")) or {}
            last_seen = _parse_dt(install.get("last_seen_at"))
            online = bool(last_seen and now - last_seen <= timedelta(minutes=5))
            alerts = _install_alerts(install, latest_version=latest_version, now=now)
            status = "Online" if online else "Offline"
            if any(a["severity"] == "error" for a in alerts):
                status = "Error"
            elif alerts:
                status = "Warning"
            old_version = _is_old_version(install.get("app_version"), latest_version)
            rows.append({
                **install,
                "licence_key": _mask(install.get("licence_key") or ""),
                "licence_status": lic.get("status"),
                "current_period_end": lic.get("current_period_end"),
                "online": online,
                "old_version": old_version,
                "status_badge": status,
                "alerts": alerts,
            })

        summary = {
            "online_now": sum(1 for row in rows if row["online"]),
            "active_today": sum(1 for row in rows if int(row.get("sessions_today") or row.get("sessions_started_today") or 0) > 0),
            "live_mode_running": sum(1 for row in rows if row.get("session_running") and row.get("environment") == "live"),
            "betfair_errors": sum(1 for row in rows if row.get("betfair_connected") is False),
            "old_versions": sum(1 for row in rows if row.get("old_version")),
            "licence_failures": sum(1 for row in rows if row.get("last_validation_ok") is False or row.get("licence_validation_status") == "failing"),
        }
        return {
            "generated_at": now.isoformat(),
            "latest_app_version": latest_version,
            "summary": summary,
            "installs": rows,
        }

    return r


# ---- Stripe integration (central role only) -------------------------------
#
# Uses the official `stripe` Python SDK directly so external VPS deploys can
# install cleanly from public PyPI (no private Emergent mirror needed).

def _stripe_client() -> stripe.StripeClient:
    api_key = os.environ.get("STRIPE_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "STRIPE_API_KEY not set on server")
    if api_key == "sk_test_emergent":
        raise HTTPException(
            500,
            "STRIPE_API_KEY is the Emergent dev placeholder ('sk_test_emergent'). "
            "Set a real Stripe secret key (sk_test_xxx or sk_live_xxx) in backend/.env to enable checkout. "
            "Grab a test key from https://dashboard.stripe.com/test/apikeys after creating a free Stripe account."
        )
    return stripe.StripeClient(api_key=api_key)


async def create_stripe_checkout_session(*, db: AsyncIOMotorDatabase, origin_url: str, email: Optional[str] = None) -> dict:
    """Spins up a Stripe Checkout Session for a one-month £19.99 GBP charge.

    NOTE: Until we have a recurring Stripe Price ID, we charge a one-time £19.99
    via `mode='payment'`. The status/webhook handler then issues a 30-day licence
    so the customer-side flow already works end-to-end. Switch `mode` to
    `'subscription'` and pass a recurring `price` for true auto-renewal.
    """
    client = _stripe_client()
    origin_url = origin_url.rstrip("/")

    success_url = f"{origin_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/#pricing"

    metadata = {"product": "layhounds_live_unlock", "tier": "monthly"}
    if email:
        metadata["email"] = email

    amount_pence = int(round(LICENCE_PRICE_GBP * 100))

    session = await asyncio.to_thread(
        client.checkout.sessions.create,
        params={
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items": [{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {"name": "Lay-Hounds Live Unlock — 30 days"},
                    "unit_amount": amount_pence,
                },
                "quantity": 1,
            }],
            "metadata": metadata,
            **({"customer_email": email} if email else {}),
        },
    )

    tx = PaymentTransaction(
        session_id=session.id,
        amount=LICENCE_PRICE_GBP,
        currency="gbp",
        metadata=metadata,
        email=email,
        payment_status="initiated",
    )
    await db.payment_transactions.insert_one(tx.model_dump(mode="json"))
    return {"url": session.url, "session_id": session.id}


async def _issue_licence_if_paid(db: AsyncIOMotorDatabase, session_id: str, payment_status: str, metadata: dict) -> Optional[str]:
    """Idempotent: on first time we see `paid` for this session, mint a licence."""
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Unknown checkout session")

    if payment_status == "paid" and tx.get("payment_status") != "paid":
        email = (metadata or {}).get("email") or tx.get("email") or "unknown@unknown"
        licence = Licence(
            licence_key=_generate_licence_key(),
            email=email,
            provider="stripe",
            provider_subscription_id=session_id,
            status="active",
            current_period_end=_now() + timedelta(days=30),
        )
        await db.licences.insert_one(licence.model_dump(mode="json"))
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "paid", "licence_key": licence.licence_key,
                      "email": email, "updated_at": _now().isoformat()}},
        )
        return licence.licence_key

    if payment_status == "paid":
        return tx.get("licence_key")

    if tx.get("payment_status") != payment_status:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": payment_status, "updated_at": _now().isoformat()}},
        )
    return None


async def get_stripe_checkout_status(*, db: AsyncIOMotorDatabase, session_id: str, origin_url: str) -> dict:
    """Poll endpoint — also responsible for issuing the licence on first paid status."""
    client = _stripe_client()
    session = await asyncio.to_thread(client.checkout.sessions.retrieve, session_id)
    payment_status = session.payment_status or "unpaid"
    metadata = dict(session.metadata or {})
    licence_key = await _issue_licence_if_paid(db, session_id, payment_status, metadata)
    return {"payment_status": payment_status, "status": session.status, "licence_key": licence_key}


async def handle_stripe_webhook(*, db: AsyncIOMotorDatabase, body: bytes, signature: str, origin_url: str) -> dict:
    """Webhook entry — idempotent, issues licence on first paid event for a session.

    If STRIPE_WEBHOOK_SECRET is configured, the signature is verified (recommended in
    production). Otherwise we parse the event payload unsigned — fine for local /
    test environments but DO NOT ship that to a public production endpoint.
    """
    import json
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if webhook_secret and signature:
        try:
            event = stripe.Webhook.construct_event(body, signature, webhook_secret)
        except Exception as e:
            raise HTTPException(400, f"Stripe webhook signature verification failed: {e}")
    else:
        event = json.loads(body.decode() or "{}")

    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    data_obj = (event.get("data", {}) or {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]
    logger.info("Stripe webhook: type=%s", event_type)

    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        session_id = data_obj.get("id")
        payment_status = data_obj.get("payment_status") or "paid"
        metadata = data_obj.get("metadata") or {}
        if session_id:
            await _issue_licence_if_paid(db, session_id, payment_status, metadata)
    return {"received": True}


# ===========================================================================
# CUSTOMER ROLE
# ===========================================================================

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


async def _set_local_licence_state(db: AsyncIOMotorDatabase, value: dict):
    await db.app_meta.update_one(
        {"_meta_key": "licence_state"},
        {"$set": {"_meta_key": "licence_state", "value": value, "updated_at": _now().isoformat()}},
        upsert=True,
    )


async def is_licence_active(db: AsyncIOMotorDatabase) -> tuple[bool, str]:
    """Check whether Paper-Live/Live should be unlocked. Returns (allowed, reason)."""
    state = await _get_local_licence_state(db)
    if not state.get("key"):
        return False, "No licence key activated on this install"
    if not state.get("last_ok"):
        return False, state.get("message") or "Last validation failed"
    last_validation_at = state.get("last_validation_at")
    if last_validation_at:
        last_dt = datetime.fromisoformat(last_validation_at.replace("Z", "+00:00"))
        if _now() - last_dt > timedelta(days=LICENCE_CACHE_DAYS):
            return False, f"Validation cache expired ({LICENCE_CACHE_DAYS} days). Reconnect to lay-hounds.co.uk."
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
        # Tailored diagnostic for the most common misconfig: the central host is
        # reachable but LICENCE_SERVER_MODE=true isn't set there, so the
        # /api/licences/* router was never mounted → FastAPI returns the
        # default {"detail":"Not Found"}.
        if resp.status_code == 404 and (detail or "").lower() in ("not found", "not-found"):
            raise HTTPException(
                404,
                f"Licence server at {LICENCE_SERVER_URL} is reachable but the "
                f"/api/licences/{endpoint} endpoint is NOT mounted. "
                f"Fix: set LICENCE_SERVER_MODE=true in backend/.env on that host "
                f"and restart the API (sudo -u layhounds pm2 restart layhounds-api). "
                f"Confirm with: curl {LICENCE_SERVER_URL}/api/licence/diag"
            )
        raise HTTPException(resp.status_code, f"Licence server: {detail}")
    return resp.json()


def build_customer_router(db: AsyncIOMotorDatabase) -> APIRouter:
    r = APIRouter(prefix="/licence")

    @r.get("/status", response_model=LicenceStatusOut)
    async def status():
        install_id = await _get_or_create_install_id(db)
        state = await _get_local_licence_state(db)
        key = state.get("key")
        last_ok = state.get("last_ok", False)
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
            ok=last_ok,
            status=state.get("status"),
            current_period_end=state.get("current_period_end"),
            last_validation_at=last_at,
            cache_valid_until=cache_until.isoformat() if cache_until else None,
            message=state.get("message"),
        )

    @r.post("/activate", response_model=LicenceStatusOut)
    async def activate(inp: ActivateRequest):
        install_id = await _get_or_create_install_id(db)
        if inp.install_id and inp.install_id != install_id:
            raise HTTPException(400, "install_id mismatch — POST without install_id and the server will use its own")
        result = await _call_central("activate", {"key": inp.key, "install_id": install_id})
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

    @r.post("/release", response_model=LicenceStatusOut)
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

    @r.post("/refresh", response_model=LicenceStatusOut)
    async def refresh():
        install_id = await _get_or_create_install_id(db)
        state = await _get_local_licence_state(db)
        key = state.get("key")
        if not key:
            raise HTTPException(400, "Nothing to refresh — activate a licence first")
        result = await _call_central("validate", {"key": key, "install_id": install_id})
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

    @r.get("/diag")
    async def diag():
        """Diagnostic endpoint — shows EXACTLY what the licence subsystem sees.

        Returns config, the install_id this box uses, count of licences in the
        local DB (if this box is also the central host), and a connectivity
        check to LICENCE_SERVER_URL. Drop this in to the URL bar when activation
        fails — it'll tell you which piece is wrong.
        """
        install_id = await _get_or_create_install_id(db)
        diag_info: dict = {
            "install_id": install_id,
            "config": {
                "LICENCE_SERVER_URL": LICENCE_SERVER_URL or "(not set)",
                "LICENCE_SERVER_MODE": LICENCE_SERVER_MODE,
                "LICENCE_PRICE_GBP": LICENCE_PRICE_GBP,
                "LICENCE_CACHE_DAYS": LICENCE_CACHE_DAYS,
                "LICENCE_REVALIDATE_HOURS": LICENCE_REVALIDATE_HOURS,
            },
            "is_central_host": LICENCE_SERVER_MODE,
            "licences_in_local_db": None,
            "connectivity": None,
        }
        if LICENCE_SERVER_MODE:
            # We host the central DB — show how many keys are seeded
            count = await db.licences.count_documents({})
            sample = await db.licences.find({}, {"_id": 0, "licence_key": 1, "status": 1,
                                                  "bound_install_id": 1, "current_period_end": 1}
                                            ).limit(10).to_list(length=10)
            diag_info["licences_in_local_db"] = {
                "total": count,
                "first_10": [{"key": _mask(d.get("licence_key", "")),
                              "status": d.get("status"),
                              "bound": bool(d.get("bound_install_id")),
                              "expires": d.get("current_period_end")} for d in sample],
            }
        # Try a connectivity test to LICENCE_SERVER_URL/api/ — just to confirm reachability
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

    return r


async def background_revalidate_loop(db: AsyncIOMotorDatabase):
    """Run in the FastAPI startup — hourly validate-and-cache. Resilient to outages."""
    while True:
        try:
            state = await _get_local_licence_state(db)
            key = state.get("key")
            if key:
                install_id = await _get_or_create_install_id(db)
                try:
                    result = await _call_central("validate", {"key": key, "install_id": install_id})
                    await _set_local_licence_state(db, {
                        **state,
                        "last_ok": result.get("ok", False),
                        "status": result.get("status"),
                        "current_period_end": result.get("current_period_end"),
                        "last_validation_at": _now().isoformat(),
                        "message": result.get("message"),
                    })
                except HTTPException as e:
                    logger.warning("Licence revalidation failed: %s (will retry next cycle)", e.detail)
        except Exception:
            logger.exception("Background revalidate loop crashed; restarting")
        await asyncio.sleep(LICENCE_REVALIDATE_HOURS * 3600)
