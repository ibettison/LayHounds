# Lay-Lab — Greyhound Recovery Simulator

## Original Problem Statement
Create a Betfair-style system to lay multiple UK greyhounds at fixed £0.05 stake. Implement a 3-level loss recovery that targets the specific favourite-rank that lost (e.g. if fav#2 loses, recover only on next race's fav#2). Recovery stake covers prev_liability + prev_stake + £0.05 profit. After 3rd-level loss the chain stops. Allow user to configure stop-win, stop-loss, number of favourites laid, and max races per day. Single-race stepping for analysis.

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB). All routes prefixed `/api`.
- **Frontend**: React 19 + Tailwind + Shadcn UI + sonner toasts + lucide-react icons.
- **Storage**: MongoDB collection `sessions` (full session document with embedded races + recovery_chains).
- **Simulation**: 6 fake UK greyhounds per race, weighted-random winner by 1/odds.

## User Personas
- **Strategy tester** — wants to validate the staircase recovery on lay-betting before risking real money.

## Core Requirements (locked)
- Fixed stake £0.05 (initial), target profit £0.05.
- Recovery: max 3 levels, then bust.
- Recovery is per-favourite-rank slot, not per-dog.
- Number of favourites laid: configurable 1–4.
- Stop conditions: stop-win, stop-loss, max-races.
- One-race-at-a-time stepping with full analysis state visible.

## Implemented (2026-02 — initial MVP)
- Backend models: SessionConfig, Greyhound, LayBet, Race, RecoveryChain, Session.
- Endpoints: POST /api/sessions, GET /api/sessions, GET /api/sessions/{id}, POST /api/sessions/{id}/next-race, POST /api/sessions/{id}/stop, DELETE /api/sessions/{id}.
- Recovery math validated end-to-end (L0→L3 chain plus bust).
- UK greyhound names list (36) + 8 venues, randomised odds 1.5–15.
- Frontend: header, session list, config panel, status bar, 4-stat KPI grid, race card with trap colours + winner highlight, recovery status with level dots, race history, new session dialog, manual stop.
- Dark "Tactical Minimalism" theme: Barlow Condensed / DM Sans / JetBrains Mono, Betfair pink accents, 1px borders, rounded-none.
- All interactive elements tagged with data-testid.

## Implemented (2026-02 — Betfair integration)
- `/app/backend/betfair_client.py` — raw async httpx JSON-RPC client, interactive login, 12h session + auto-refresh, listMarketCatalogue + listMarketBook + placeOrders + cancelOrders.
- SessionConfig extended with `mode` (simulator | paper_live | live), `max_liability_cap`, `risk_accepted`.
- Race extended with `source`, `market_id`, `market_start_time`, `betfair_bet_ids`.
- New endpoints: GET /api/betfair/status, GET /api/betfair/races.
- `next-race` is now mode-aware:
  - simulator: fake races (unchanged).
  - paper_live: fetches real Betfair GB/IE greyhound market (next 60 min), real runners + real odds, outcome simulated via weighted 1/odds.
  - live: fetches real market, actually places LAY orders on Betfair (returns betIds), then the user settles via the Betfair web UI. Max-liability cap auto-busts runaway recoveries.
- Live-mode guardrails: creation requires `risk_accepted=true`, per-bet liability capped at `max_liability_cap`.
- Credentials in backend/.env only — never exposed to frontend.

## ⚠️ Known deployment constraint
Betfair geo-blocks all non-UK/EU traffic (Cloudflare "Restricted" 403). The current Emergent preview pod runs in the US (IP 34.16.56.64) and cannot reach Betfair APIs. The Betfair status endpoint returns `GEO_BLOCKED`. The integration code is correct and will work unchanged once the backend is deployed on a UK/EU host (e.g. self-hosted UK VPS, or routed via a UK reverse proxy).

## Backlog
### P1
- Live-mode auto-settlement: poll listMarketBook until CLOSED, match WINNER selection back to runners via persisted selection_id per Greyhound (currently missing).
- UK/EU proxy/deployment guide in README.
- Per-race manual winner override (toggle) for deterministic stress-testing.
- Bank progression line chart (recharts).

### P2
- Monte-Carlo batch mode (run config × 1000 silently).
- CSV export, variable initial stake, configurable recovery depth, per-dog (vs per-rank) recovery mode.

## Test Status
- Backend: 9/9 pytest tests passing (`/app/backend/tests/test_simulator.py`) — covers CRUD, race-gen invariants, full L0→L3→bust chain, stop conditions, 404s.
- Frontend: critical flow verified by testing agent (90%+); Stop button → badge sync logic confirmed correct in code (manual curl test shows backend returns stopped_manual; setCurrent(updated) propagates to UI).

## Next Tasks
1. Add deterministic winner-override toggle (P1).
2. Add bank progression line chart (P1).
3. CSV export of races + bets (P1).
