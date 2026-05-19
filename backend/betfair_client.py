"""Betfair Exchange API client — raw async JSON-RPC over HTTPS."""
import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

EVENT_TYPE_GREYHOUND = "4339"
IDENTITY_URL = "https://identitysso.betfair.com/api"
EXCHANGE_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"
ACCOUNT_URL = "https://api.betfair.com/exchange/account/json-rpc/v1"


class BetfairError(Exception):
    pass


class BetfairClient:
    def __init__(self):
        self.app_key = os.environ.get("BETFAIR_APP_KEY", "").strip()
        self.username = os.environ.get("BETFAIR_USERNAME", "").strip()
        self.password = os.environ.get("BETFAIR_PASSWORD", "")
        self.session_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._req_id = 0
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(self.app_key and self.username and self.password)

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10, keepalive_expiry=30)
            self._http = httpx.AsyncClient(limits=limits, timeout=20.0)
        return self._http

    async def close(self):
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def _token_valid(self) -> bool:
        if not self.session_token or not self.token_expiry:
            return False
        return datetime.now(timezone.utc) < self.token_expiry - timedelta(minutes=30)

    async def login(self) -> str:
        if not self.is_configured():
            raise BetfairError("Betfair credentials not configured")
        http = await self._client()
        headers = {
            "Accept": "application/json",
            "X-Application": self.app_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (compatible; LayLab/1.0)",
        }
        data = {"username": self.username, "password": self.password}
        try:
            resp = await http.post(f"{IDENTITY_URL}/login", headers=headers, data=data)
        except httpx.HTTPError as e:
            raise BetfairError(f"Network error contacting Betfair: {e}")
        if resp.status_code == 403 and "Restricted" in resp.text:
            raise BetfairError(
                "GEO_BLOCKED: Betfair restricts API access by IP region. "
                "This server is in a blocked region. Deploy backend in UK/EU to enable live data."
            )
        if resp.status_code != 200:
            raise BetfairError(f"Login HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        if body.get("status") != "SUCCESS":
            raise BetfairError(f"Login failed: {body.get('error') or body}")
        self.session_token = body["token"]
        self.token_expiry = datetime.now(timezone.utc) + timedelta(hours=12)
        logger.info("Betfair login successful")
        return self.session_token

    async def ensure_session(self):
        async with self._lock:
            if not self._token_valid():
                await self.login()

    async def _rpc(self, method: str, params: Dict[str, Any], *, account: bool = False) -> Any:
        await self.ensure_session()
        self._req_id += 1
        http = await self._client()
        headers = {
            "Content-Type": "application/json",
            "X-Application": self.app_key,
            "X-Authentication": self.session_token or "",
            "Accept": "application/json",
        }
        prefix = "AccountAPING" if account else "SportsAPING"
        url = ACCOUNT_URL if account else EXCHANGE_URL
        payload = {"jsonrpc": "2.0", "method": f"{prefix}/v1.0/{method}", "params": params, "id": self._req_id}
        try:
            resp = await http.post(url, headers=headers, json=payload)
        except httpx.HTTPError as e:
            raise BetfairError(f"Network error contacting Betfair: {type(e).__name__}: {e}")
        if resp.status_code == 403 and ("Restricted" in resp.text or "geographic" in resp.text.lower()):
            raise BetfairError(
                "GEO_BLOCKED: Betfair restricts API access by IP region. "
                "This server appears to be in a blocked region."
            )
        if resp.status_code != 200:
            raise BetfairError(f"Betfair HTTP {resp.status_code}: {resp.text[:240]}")
        try:
            body = resp.json()
        except ValueError as e:
            raise BetfairError(f"Betfair returned non-JSON response: {e} (body={resp.text[:200]})")
        if "error" in body:
            err = body["error"]
            msg = err.get("data", {}).get("APINGException", {}).get("errorCode") or \
                  err.get("data", {}).get("AccountAPINGException", {}).get("errorCode") or \
                  err.get("message", str(err))
            if "INVALID_SESSION_INFORMATION" in str(msg):
                self.session_token = None
                await self.ensure_session()
                return await self._rpc(method, params, account=account)
            raise BetfairError(f"API error: {msg}")
        return body.get("result")

    async def list_greyhound_markets(self, minutes_ahead: int = 30, max_results: int = 10) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        params = {
            "filter": {
                "eventTypeIds": [EVENT_TYPE_GREYHOUND],
                "marketCountries": ["GB", "IE"],
                "marketTypeCodes": ["WIN"],
                "marketStartTime": {
                    "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": (now + timedelta(minutes=minutes_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            },
            "sort": "FIRST_TO_START",
            "maxResults": max_results,
            "marketProjection": ["RUNNER_DESCRIPTION", "MARKET_START_TIME", "EVENT"],
        }
        return await self._rpc("listMarketCatalogue", params) or []

    async def get_market_book(self, market_id: str) -> Optional[Dict[str, Any]]:
        params = {"marketIds": [market_id], "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}}
        books = await self._rpc("listMarketBook", params) or []
        return books[0] if books else None

    @staticmethod
    def _snap_to_tick(price: float) -> float:
        """Snap a price to the nearest valid Betfair price tick.

        Betfair only accepts prices on a fixed ladder; arbitrary decimals like 3.45 are rejected.
        Ladder steps: 1.01-2.00 = 0.01, 2-3 = 0.02, 3-4 = 0.05, 4-6 = 0.1,
                      6-10 = 0.2, 10-20 = 0.5, 20-30 = 1, 30-50 = 2, 50-100 = 5, 100-1000 = 10.
        Rounded UP for LAY orders so we keep our intended price-or-better.
        """
        bands = [
            (1.01, 2.0, 0.01), (2.0, 3.0, 0.02), (3.0, 4.0, 0.05),
            (4.0, 6.0, 0.1), (6.0, 10.0, 0.2), (10.0, 20.0, 0.5),
            (20.0, 30.0, 1.0), (30.0, 50.0, 2.0), (50.0, 100.0, 5.0),
            (100.0, 1000.01, 10.0),
        ]
        if price < 1.01:
            return 1.01
        if price > 1000.0:
            return 1000.0
        for lo, hi, step in bands:
            if lo <= price < hi:
                # Round up to the next tick to be conservative for a LAY
                ticks = round((price - lo) / step + 0.5)
                snapped = round(lo + ticks * step, 2)
                return min(snapped, hi - step) if snapped >= hi else snapped
        return round(price, 2)

    async def place_lay_bet(self, market_id: str, selection_id: int, price: float, size: float,
                            *, customer_order_ref: Optional[str] = None) -> Dict[str, Any]:
        """Place a single LAY bet on a market.

        Raises BetfairError if Betfair rejects the placement at any level —
        top-level status, individual instruction status, or zero size matched at FOK.
        Returns the raw PlaceExecutionReport on success.
        """
        if price < 1.01:
            raise BetfairError("Odds must be >= 1.01")
        if size < 1.0:
            return await self.place_sub_minimum_lay(
            market_id=market_id,
            selection_id=selection_id,
            price=price,
            size=size,
            customer_order_ref=customer_order_ref,
            )

    #if size < 1.0:
            # Betfair UK minimum lay stake is £1 unless using the "small bet" allowance.
            # Bubble this up clearly so the user understands why the bet was rejected.
            #raise BetfairError(
             #   f"Lay stake ({size:.2f}) below Betfair UK £1.00 minimum. "
              #  "Increase your stake or your recovery target."
           # )
        snapped = self._snap_to_tick(price)
        instruction = {
            "orderType": "LIMIT",
            "selectionId": selection_id,
            "handicap": 0,
            "side": "LAY",
            "limitOrder": {"size": round(size, 2), "price": snapped, "persistenceType": "LAPSE"},
        }
        if customer_order_ref:
            # Betfair allows a-zA-Z0-9_-.+:; up to 32 chars
            instruction["customerOrderRef"] = customer_order_ref[:32]

        result = await self._rpc("placeOrders", {
            "marketId": market_id,
            "instructions": [instruction],
        })

        # The PlaceExecutionReport top-level can be SUCCESS / FAILURE / PROCESSED_WITH_ERRORS.
        top_status = (result or {}).get("status")
        if top_status not in ("SUCCESS", None):
            err_code = result.get("errorCode") or "UNKNOWN"
            raise BetfairError(f"Betfair rejected order: {top_status} ({err_code})")

        reports = (result or {}).get("instructionReports", []) or []
        if not reports:
            raise BetfairError("Betfair returned no instruction report — bet not placed")

        rep = reports[0]
        if rep.get("status") != "SUCCESS":
            err_code = rep.get("errorCode") or "UNKNOWN_ERROR"
            raise BetfairError(
                f"Betfair rejected lay bet: {err_code} "
                f"(market={market_id}, sel={selection_id}, price={snapped}, size={size})"
            )
        return result

    async def cancel_all(self, market_id: str) -> Dict[str, Any]:
        return await self._rpc("cancelOrders", {"marketId": market_id})

    async def place_small_lay_bet(self, market_id: str, selection_id: int,
                                  target_price: float, target_size: float,
                                  *, customer_order_ref: Optional[str] = None,
                                  park_price: float = 1.10, park_size: float = 1.00,
                                  ) -> Dict[str, Any]:
        """Lay bet UNDER the £1 Betfair minimum, using the well-known "parking"
        technique. The sub-£1 final stake never matches at >= £1, so this is
        safe for live-mode testing without risking large liability.

        Flow (Betfair compliant):
          1. placeOrders  — full park_size=£1.00 at park_price=1.10 (lay).
             Sits UNMATCHED on the book because BETFAIR will not place a bet at 1.10.
          2. cancelOrders — partial cancel with sizeReduction = (park_size − target_size).
             The £1 minimum does NOT apply to size reductions, so the remaining
             unmatched size can be as low as £0.01.
          3. replaceOrders — change price to the realistic `target_price`.
             The remaining sub-£1 size now sits at a matchable price and will
             match like any normal lay.

        Returns dict with: place_report, cancel_report, replace_report, final_bet_id.
        Raises BetfairError if any step fails — and TRIES to clean up the parked
        order before bubbling the error up, so we never leave residue.
        """
        if target_price < 1.01:
            raise BetfairError("Target price must be >= 1.01")
        if target_size < 0.01:
            raise BetfairError("Target size must be >= £0.01")
        if target_size >= 1.0:
            raise BetfairError(
                f"Target size £{target_size:.2f} is >= £1.00 — use place_lay_bet() instead."
            )
        if park_size < 1.0:
            raise BetfairError("park_size must be >= £1.00 (Betfair minimum)")
        if park_size <= target_size:
            raise BetfairError("park_size must be strictly greater than target_size")

        target_price_snapped = self._snap_to_tick(target_price)
        size_reduction = round(park_size - target_size, 2)

        # ---- Step 1: park unmatched at an extreme price ----------------------
        park_instruction: Dict[str, Any] = {
            "orderType": "LIMIT",
            "selectionId": selection_id,
            "handicap": 0,
            "side": "LAY",
            "limitOrder": {
                "size": round(park_size, 2),
                "price": park_price,
                "persistenceType": "LAPSE",
            },
        }
        if customer_order_ref:
            park_instruction["customerOrderRef"] = (customer_order_ref + "-park")[:32]

        place_report = await self._rpc("placeOrders", {
            "marketId": market_id,
            "instructions": [park_instruction],
        })

        top = (place_report or {}).get("status")
        if top not in ("SUCCESS", None):
            raise BetfairError(
                f"Small-lay park failed: {top} ({place_report.get('errorCode', '?')})"
            )
        reports = (place_report or {}).get("instructionReports", []) or []
        if not reports or reports[0].get("status") != "SUCCESS":
            err = (reports[0] if reports else {}).get("errorCode", "UNKNOWN_ERROR")
            raise BetfairError(f"Small-lay park rejected: {err}")
        bet_id = reports[0].get("betId")
        if not bet_id:
            raise BetfairError("Small-lay park returned no betId")

        async def _try_clean_up(reason: str):
            try:
                await self._rpc("cancelOrders", {
                    "marketId": market_id,
                    "instructions": [{"betId": bet_id}],
                })
                logger.warning("Cancelled parked order %s after failure: %s", bet_id, reason)
            except Exception as e:
                logger.error("FAILED to clean up parked bet %s: %s (you may have a stray £%s order at %s)",
                             bet_id, e, park_size, park_price)

        # ---- Step 2: size-reduce down to target_size -------------------------
        try:
            cancel_report = await self._rpc("cancelOrders", {
                "marketId": market_id,
                "instructions": [{
                    "betId": bet_id,
                    "sizeReduction": size_reduction,
                }],
            })
        except Exception as e:
            await _try_clean_up(f"cancel/sizeReduce raised {type(e).__name__}: {e}")
            raise BetfairError(f"Small-lay size-reduce failed: {e}")

        if (cancel_report or {}).get("status") not in ("SUCCESS", None):
            await _try_clean_up(f"cancel/sizeReduce status={cancel_report.get('status')}")
            raise BetfairError(
                f"Small-lay size-reduce failed: {cancel_report.get('status')} "
                f"({cancel_report.get('errorCode', '?')})"
            )

        # ---- Step 3: replace to the real price -------------------------------
        try:
            replace_report = await self._rpc("replaceOrders", {
                "marketId": market_id,
                "instructions": [{
                    "betId": bet_id,
                    "newPrice": target_price_snapped,
                }],
            })
        except Exception as e:
            await _try_clean_up(f"replaceOrders raised {type(e).__name__}: {e}")
            raise BetfairError(f"Small-lay price-replace failed: {e}")

        if (replace_report or {}).get("status") not in ("SUCCESS", None):
            await _try_clean_up(f"replace status={replace_report.get('status')}")
            raise BetfairError(
                f"Small-lay price-replace failed: {replace_report.get('status')} "
                f"({replace_report.get('errorCode', '?')})"
            )
        rep_reports = (replace_report or {}).get("instructionReports", []) or []
        new_bet_id = bet_id
        if rep_reports:
            rep0 = rep_reports[0]
            place_inside = rep0.get("placeInstructionReport") or {}
            new_bet_id = place_inside.get("betId") or bet_id

        return {
            "place_report": place_report,
            "cancel_report": cancel_report,
            "replace_report": replace_report,
            "final_bet_id": new_bet_id,
            "parked_at_price": park_price,
            "matched_at_price": target_price_snapped,
            "matched_size": round(target_size, 2),
        }

    async def get_account_funds(self) -> Dict[str, Any]:
        """Returns Betfair account funds. Keys: availableToBetBalance, exposure,
        exposureLimit, retainedCommission, discountRate, pointsBalance, wallet."""
        return await self._rpc("getAccountFunds", {"wallet": "UK"}, account=True) or {}

    async def status(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"configured": False, "logged_in": False, "reason": "missing_credentials"}
        try:
            await self.ensure_session()
            return {
                "configured": True,
                "logged_in": True,
                "token_expiry": self.token_expiry.isoformat() if self.token_expiry else None,
                "app_key_tail": self.app_key[-4:],
            }
        except Exception as e:
            return {"configured": True, "logged_in": False, "reason": str(e)[:200]}

async def replace_lay_order(
    self, market_id: str, bet_id: str, new_price: float,) -> Dict[str, Any]:
    """
    Replace the price of an existing unmatched lay order.
    Betfair replaceOrders only changes price.
    """

    snapped = self._snap_to_tick(new_price)

    result = await self._rpc("replaceOrders", {
        "marketId": market_id,
        "instructions": [{
            "betId": bet_id,
            "newPrice": snapped,
        }],
    })

    top_status = (result or {}).get("status")
    if top_status not in ("SUCCESS", None):
        err_code = result.get("errorCode") or "UNKNOWN"
        raise BetfairError(
            f"replaceOrders failed ({top_status}) ({err_code})"
        )

    reports = (result or {}).get("instructionReports", []) or []
    if not reports:
        raise BetfairError("replaceOrders returned no instruction reports")

    rep = reports[0]

    if rep.get("status") != "SUCCESS":
        err_code = rep.get("errorCode") or "UNKNOWN_ERROR"
        raise BetfairError(
            f"replaceOrders rejected: {err_code}"
        )

    return result

async def place_sub_minimum_lay(
    self, market_id: str, selection_id: int, price: float, size: float, *, customer_order_ref: Optional[str] = None,) -> Dict[str, Any]:
    """
    Experimental workaround for sub-£1 lay stakes.

    Flow:
    1. Place £1 seed lay at 1.2
    2. Immediately cancel unwanted amount
    3. Replace odds with target price

    WARNING:
    Seed order must remain unmatched.
    """

    seed_price = 1.2
    seed_size = 1.0

    # STEP 1 — PLACE SEED ORDER
    seed_result = await self.place_lay_bet(
        market_id=market_id,
        selection_id=selection_id,
        price=seed_price,
        size=seed_size,
        customer_order_ref=customer_order_ref,
    )

    reports = seed_result.get("instructionReports", [])
    if not reports:
        raise BetfairError("Seed order returned no reports")

    report = reports[0]

    bet_id = report.get("betId")
    if not bet_id:
        raise BetfairError("Seed order returned no betId")

    # STEP 2 — CANCEL DOWN TO TARGET SIZE
    cancel_size = round(seed_size - size, 2)

    if cancel_size > 0:
        cancel_result = await self._rpc("cancelOrders", {
            "marketId": market_id,
            "instructions": [{
                "betId": bet_id,
                "sizeReduction": cancel_size,
            }],
        })

        cancel_reports = cancel_result.get("instructionReports", [])
        if not cancel_reports:
            raise BetfairError("cancelOrders returned no reports")

        cancel_rep = cancel_reports[0]

        if cancel_rep.get("status") != "SUCCESS":
            raise BetfairError(
                f"cancelOrders failed: {cancel_rep.get('errorCode')}"
            )

    # STEP 3 — REPLACE PRICE
    replace_result = await self.replace_lay_order(
        market_id=market_id,
        bet_id=bet_id,
        new_price=price,
    )

    return {
        "seed": seed_result,
        "replace": replace_result,
        "betId": bet_id,
    }

# Singleton
betfair = BetfairClient()
