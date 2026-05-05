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

    async def _rpc(self, method: str, params: Dict[str, Any]) -> Any:
        await self.ensure_session()
        self._req_id += 1
        http = await self._client()
        headers = {
            "Content-Type": "application/json",
            "X-Application": self.app_key,
            "X-Authentication": self.session_token or "",
            "Accept": "application/json",
        }
        payload = {"jsonrpc": "2.0", "method": f"SportsAPING/v1.0/{method}", "params": params, "id": self._req_id}
        resp = await http.post(EXCHANGE_URL, headers=headers, json=payload)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            err = body["error"]
            msg = err.get("data", {}).get("APINGException", {}).get("errorCode") or err.get("message", str(err))
            if "INVALID_SESSION_INFORMATION" in str(msg):
                self.session_token = None
                await self.ensure_session()
                return await self._rpc(method, params)
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

    async def place_lay_bet(self, market_id: str, selection_id: int, price: float, size: float) -> Dict[str, Any]:
        if price < 1.01:
            raise BetfairError("Odds must be >= 1.01")
        instruction = {
            "orderType": "LIMIT",
            "selectionId": selection_id,
            "handicap": 0,
            "side": "LAY",
            "limitOrder": {"size": size, "price": price, "persistenceType": "LAPSE"},
        }
        return await self._rpc("placeOrders", {"marketId": market_id, "instructions": [instruction]})

    async def cancel_all(self, market_id: str) -> Dict[str, Any]:
        return await self._rpc("cancelOrders", {"marketId": market_id})

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


# Singleton
betfair = BetfairClient()
