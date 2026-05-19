#!/usr/bin/env python3
"""Seed a test licence key into the LOCAL MongoDB.

Use this on your VPS to create a working licence key WITHOUT going through the
Stripe checkout flow. Useful for:
  • First-run testing of the Paper-Live / Live gate
  • Verifying the LicencePanel UI binds correctly to install_id
  • Letting yourself in while Stripe / PayPal webhooks are still being wired

Run from /opt/layhounds/backend (or wherever your runtime backend lives):

    cd /opt/layhounds/backend
    source venv/bin/activate
    python seed_test_licence.py                    # default key, 30 days
    python seed_test_licence.py --key LH-MINE-1234-5678-9999
    python seed_test_licence.py --days 365 --email me@example.com

This script ONLY writes to the local MongoDB referenced by the same MONGO_URL +
DB_NAME that the running API uses. It is a no-op idempotent insert: re-running
it with the same key will reset bound_install_id back to NULL so you can
re-activate after testing.

Make sure `LICENCE_SERVER_MODE=true` is set in backend/.env so the API exposes
the /api/licences/activate endpoint that this key validates against.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load .env from the same dir as this script (i.e. /opt/layhounds/backend/.env)
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

# Import after .env is loaded so module-level config is correct
sys.path.insert(0, str(HERE))
from licences import Licence, _now  # noqa: E402


async def seed(key: str, email: str, days: int, force_unbind: bool):
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        sys.exit("MONGO_URL and DB_NAME must be set in backend/.env")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    existing = await db.licences.find_one({"licence_key": key}, {"_id": 0})
    if existing:
        if force_unbind:
            await db.licences.update_one(
                {"licence_key": key},
                {"$set": {"bound_install_id": None, "bound_at": None,
                          "current_period_end": (_now() + timedelta(days=days)).isoformat(),
                          "status": "active", "updated_at": _now().isoformat()}},
            )
            print(f"✓ Reset existing key {key} → unbound, +{days} days, status=active")
        else:
            print(f"⚠ Key {key} already exists. Use --reset to unbind it for fresh activation.")
            print(f"  Status:           {existing.get('status')}")
            print(f"  Bound install_id: {existing.get('bound_install_id') or '(none)'}")
            print(f"  Expires:          {existing.get('current_period_end')}")
        client.close()
        return

    lic = Licence(
        licence_key=key,
        email=email,
        provider="manual",
        status="active",
        current_period_end=_now() + timedelta(days=days),
    )
    await db.licences.insert_one(lic.model_dump(mode="json"))
    client.close()
    print(f"✓ Seeded new licence key: {key}")
    print(f"  Email:   {email}")
    print(f"  Expires: in {days} days")
    print(f"  DB:      {db_name} (via {mongo_url.split('@')[-1]})")
    print()
    print("Now open the simulator UI, paste this key into the Live Unlock Licence")
    print("panel, and click Activate. It should bind to this install's UUID.")


def main():
    p = argparse.ArgumentParser(description="Seed a test licence into the local MongoDB.")
    p.add_argument("--key", default="LH-TEST-AAAA-BBBB-CCCC",
                   help="Licence key to insert (default: LH-TEST-AAAA-BBBB-CCCC)")
    p.add_argument("--email", default="test@layhounds.local",
                   help="Email to associate (cosmetic — used for receipt copy)")
    p.add_argument("--days", type=int, default=30,
                   help="Days until current_period_end (default: 30)")
    p.add_argument("--reset", action="store_true",
                   help="If key already exists, unbind it + extend by --days (use after testing)")
    args = p.parse_args()
    asyncio.run(seed(args.key, args.email, args.days, args.reset))


if __name__ == "__main__":
    main()
