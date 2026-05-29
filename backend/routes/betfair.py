from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from betfair_client import betfair, BetfairError
from race_categories import detect_category_from_market_name

router = APIRouter(prefix="/api")

@router.get("/betfair/status")
async def betfair_status():
    return await betfair.status()

@router.get("/betfair/funds")
async def betfair_funds():
    """Return the Betfair account balance — used by Paper-Live / Live to source the bank.
    Falls back to a structured error so the UI can render a helpful message.
    """
    if not betfair.is_configured():
        raise HTTPException(400, "Betfair credentials not configured on server")
    try:
        funds = await betfair.get_account_funds()
        return {
            "available_to_bet": float(funds.get("availableToBetBalance", 0.0) or 0.0),
            "exposure": float(funds.get("exposure", 0.0) or 0.0),
            "exposure_limit": float(funds.get("exposureLimit", 0.0) or 0.0),
            "retained_commission": float(funds.get("retainedCommission", 0.0) or 0.0),
            "wallet": funds.get("wallet") or "UK",
        }
    except BetfairError as e:
        raise HTTPException(502, str(e))


@router.get("/betfair/races")
async def betfair_races(minutes_ahead: int = 30, max_results: int = 10):
    try:
        markets = await betfair.list_greyhound_markets(minutes_ahead=minutes_ahead, max_results=max_results)
    except BetfairError as e:
        raise HTTPException(502, f"Betfair error: {e}")
    for market in markets:
        if "marketId" in market and "market_id" not in market:
            market["market_id"] = market["marketId"]
    return {"count": len(markets), "markets": markets}


@router.get("/betfair/market/{market_id}/preview")
async def betfair_market_preview(market_id: str):
    """Return the live runners + current lay-side odds for a specific market.

    Used by the frontend "Upcoming Race Preview" panel to show the user the
    field 5 minutes before the off — with live price updates so the user can
    see the market shape as the bet approaches.

    Returns:
        runners: [{trap, name, odds, favourite_rank, selection_id}]
        market_id, market_name, event_name, start_time, category
        last_updated: ISO timestamp
    """
    try:
        book = await betfair.get_market_book(market_id)
    except BetfairError as e:
        raise HTTPException(502, f"Betfair error: {e}")
    if not book:
        raise HTTPException(404, "Market not found or not yet active")

    # Look up the market catalogue for runner names / metadata / venue / name
    try:
        cats = await betfair.list_market_catalogue(market_ids=[market_id])
    except BetfairError:
        cats = []
    m = cats[0] if cats else {}
    runner_meta = {r["selectionId"]: r for r in m.get("runners", [])}

    priced = []
    for br in book.get("runners", []):
        if br.get("status") != "ACTIVE":
            continue
        ex = br.get("ex", {})
        lay_prices = ex.get("availableToLay", [])
        back_prices = ex.get("availableToBack", [])
        if not lay_prices:
            continue
        sel_id = br["selectionId"]
        meta = runner_meta.get(sel_id, {})
        priced.append({
            "selection_id": sel_id,
            "name": meta.get("runnerName", f"Runner {sel_id}"),
            "trap": int(meta.get("metadata", {}).get("CLOTH_NUMBER")
                        or meta.get("metadata", {}).get("TRAP_NUMBER") or 0),
            "odds": round(float(lay_prices[0]["price"]), 2),
            "back_odds": round(float(back_prices[0]["price"]), 2) if back_prices else None,
            "lay_size": round(float(lay_prices[0].get("size") or 0), 2),
        })

    # Assign traps in order if Betfair didn't supply CLOTH_NUMBER
    for i, p in enumerate(priced):
        if not p["trap"]:
            p["trap"] = i + 1

    sorted_by_odds = sorted(priced, key=lambda r: r["odds"])
    rank_by_sel = {r["selection_id"]: idx + 1 for idx, r in enumerate(sorted_by_odds)}
    runners = [
        {**p, "favourite_rank": rank_by_sel[p["selection_id"]]}
        for p in priced
    ]

    market_name = m.get("marketName") or ""
    event_name = (m.get("event") or {}).get("name") or ""
    category = detect_category_from_market_name(market_name, event_name)

    return {
        "market_id": market_id,
        "market_name": market_name,
        "event_name": event_name,
        "start_time": m.get("marketStartTime"),
        "category": category.model_dump(),
        "runners": sorted(runners, key=lambda r: r["trap"]),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


