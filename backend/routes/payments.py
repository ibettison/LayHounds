import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from db import db
from licences import (
    LICENCE_SERVER_MODE,
    create_stripe_checkout_session,
    get_stripe_checkout_status,
    handle_stripe_webhook,
)

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# ====================================================================
# Marketing site endpoints (Phase 1 stubs — wired in Phase 2)
# ====================================================================

class CheckoutResponse(BaseModel):
    url: Optional[str] = None
    message: Optional[str] = None
    provider: str
    test_mode: bool = True


@router.post("/payments/stripe/checkout")
async def stripe_checkout(request: Request, email: Optional[str] = None):
    """Create a real Stripe Checkout Session via emergentintegrations.

    The Checkout Session redirects to Stripe-hosted payment UI; on success Stripe
    sends the customer back to /checkout/success?session_id=... which polls
    /api/payments/stripe/status/{session_id} until paid, at which point a Licence
    is issued and the licence_key is returned to the success page.
    """
    if not LICENCE_SERVER_MODE:
        raise HTTPException(400, "This server is not the central licence host (set LICENCE_SERVER_MODE=true on lay-hounds.co.uk)")
    origin = str(request.base_url).rstrip("/")
    try:
        return await create_stripe_checkout_session(db=db, origin_url=origin, email=email)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Stripe checkout create failed")
        raise HTTPException(502, f"Stripe checkout failed: {type(e).__name__}: {e}")


@router.get("/payments/stripe/status/{session_id}")
async def stripe_status(session_id: str, request: Request):
    """Polled by the success page until payment_status == 'paid'. Returns licence_key on first paid."""
    if not LICENCE_SERVER_MODE:
        raise HTTPException(400, "Not the central licence host")
    origin = str(request.base_url).rstrip("/")
    try:
        return await get_stripe_checkout_status(db=db, session_id=session_id, origin_url=origin)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Stripe status check failed")
        raise HTTPException(502, f"Stripe status check failed: {type(e).__name__}: {e}")


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    if not LICENCE_SERVER_MODE:
        raise HTTPException(404, "No webhook endpoint here")
    body = await request.body()
    origin = str(request.base_url).rstrip("/")
    try:
        return await handle_stripe_webhook(db=db, body=body, signature=stripe_signature or "", origin_url=origin)
    except Exception as e:
        logger.exception("Stripe webhook handling failed")
        raise HTTPException(400, f"Webhook error: {type(e).__name__}: {e}")


@router.post("/payments/paypal/checkout")
async def paypal_checkout():
    """PayPal subscription order — placeholder until you drop your PayPal REST app credentials."""
    paypal_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    if not paypal_id or paypal_id.startswith("PLACEHOLDER"):
        return {
            "provider": "paypal",
            "message": "PayPal checkout — drop your PayPal REST client_id + client_secret in backend/.env and we'll wire the live flow next.",
            "test_mode": True,
        }
    return {"provider": "paypal", "url": "https://www.paypal.com/checkoutnow?token=PLACEHOLDER", "test_mode": True}


class ContactInput(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=1, max_length=4000)


@router.post("/contact")
async def contact(inp: ContactInput):
    """Persist contact-form submissions to MongoDB. Phase 2 will email + Slack alert."""
    if "@" not in inp.email or "." not in inp.email:
        raise HTTPException(400, "Invalid email")
    doc = {
        "id": str(uuid.uuid4()),
        "email": inp.email.strip(),
        "message": inp.message.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "handled": False,
    }
    await db.contact_messages.insert_one(doc)
    logger.info("contact form: %s", inp.email)
    return {"ok": True}


