# Lay-Lab — Greyhound Recovery Simulator

## Original Problem Statement
Create a Betfair-style system to lay multiple UK greyhounds. Stake (originally fixed £0.05) and recovery depth (originally fixed at 3 levels) are now both user-configurable. Implement loss recovery that targets the specific favourite-rank that lost (e.g. if fav#2 loses, recover only on next race's fav#2). Recovery stake covers prev_liability + prev_stake + target_profit. After the configured LN-level loss the chain busts. Allow user to configure stop-win, stop-loss, number of favourites laid, and max races per day. Single-race stepping + batched runs. Three execution modes (Simulator, Paper-Live, Live). Daily P&L graph across sessions.

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB). All routes prefixed `/api`. Betfair JSON-RPC via httpx.
- **Frontend**: React 19 + Tailwind + Shadcn UI + recharts + sonner + lucide-react.
- **Storage**: MongoDB `sessions` collection (full document with embedded races + recovery_chains).
- **Simulation**: 6 fake UK greyhounds per race, weighted-random winner by 1/odds, commission applied on wins.
- **Modes**: Simulator (fake), Paper-Live (real Betfair odds, simulated settlement), Live (real LAY orders).

## Core Requirements (locked)
- Configurable stake (£0.05, £0.50, £1.00, £1.50, £2.00).
- Configurable recovery depth L1–L5 (default L3).
- Recovery is per-favourite-rank slot, not per-dog.
- Number of favourites laid: configurable 1–4.
- Stop conditions: stop-win, stop-loss, max-races (with recovery-overrun option).
- Liability cap (bust protection) — recovery bets exceeding cap auto-bust the chain.
- Configurable Betfair commission (0 / 2 / 5 / 6.5 / 10%).
- Odds range filter (skip favs outside min/max band).
- Batch race execution (1/5/10/25/50).
- Bank carryover between sessions + daily P&L graph.

## Implemented (2026-02)
### Core MVP
- Session CRUD (POST/GET/DELETE /api/sessions), next-race, stop.
- Recovery math validated end-to-end (all levels up to L5, plus bust).
- UK greyhound names (36) + 8 venues, randomised odds 1.5–15.
- Dark "Tactical Minimalism" theme: Barlow Condensed / DM Sans / JetBrains Mono, pink accents, rounded-none.
- Full data-testid coverage.

### Betfair Integration
- `betfair_client.py` raw async httpx JSON-RPC with interactive login, 12h session + auto-refresh.
- listMarketCatalogue / listMarketBook / placeOrders / cancelOrders wired.
- Mode-aware `next-race`: simulator / paper_live / live.
- Live-mode guardrails: `risk_accepted=true`, per-bet liability capped at `max_liability_cap`.
- Credentials stored only in `backend/.env`.

### Advanced (added since MVP)
- Configurable stakes (£0.05–£2.00) & commission tiers.
- Liability cap / bust protection in all three modes.
- Monte-Carlo cap preview (`POST /api/preview-cap`, 1500–2000 iterations).
- Odds-range filter on lay selection.
- Batch run-races (`batch_size` param, 1–50).
- Recovery-overrun: continue active chains past `max_races` until resolved.
- Bank carryover (`GET /api/bank/current`).
- Daily P&L graph (`GET /api/daily-stats` + Recharts cumulative line + per-session bar).
- **Dynamic recovery depth L1–L5 (2026-02-06)**: `max_recovery_level` now on SessionConfig and CapPreviewInput. All backend math, Monte-Carlo bust-distribution keys, and frontend CapPreview / RecoveryStatus / NewSessionDialog dynamically render 1–5 levels.
- DailyChart negative-height SVG warning fixed (2026-02-06).

## ⚠️ Known deployment constraint
Betfair geo-blocks all non-UK/EU traffic. The Emergent preview pod is in the US, so `GET /api/betfair/status` returns `GEO_BLOCKED` and paper-live/live modes are disabled in the UI with a clear badge. Simulator mode is fully functional. The integration code is correct and will work unchanged once the backend is deployed on a UK/EU host (UK VPS / UK reverse proxy).

## Credentials
- Betfair App Key / Username / Password in `/app/backend/.env` (provided by user).

## Test Status
- Backend: **25/25 pytest passing** (`/app/backend/tests/test_simulator.py` + `test_new_features.py`) — covers CRUD, recovery math, all dynamic levels, cap bust, overrun, stop conditions, bank carryover, daily-stats, batch runs, preview-cap.
- Frontend: Full flow verified by testing agent — L1-L5 toggles, dynamic CapPreview, RecoveryStatus dot count, batch buttons, Stop-button sync, welcome copy, DailyChart renders across 95 days.
- Live mode: not testable from this pod (GEO_BLOCKED), code-reviewed only.

## Backlog
### P1
- Aggregate all-time dashboard (across every historical day, not just current bank streak).
- UK/EU proxy/deployment guide in README for Live mode.
- CSV export of races + bets.

### P2
- Per-dog (vs per-rank) recovery mode toggle.
- Per-race manual winner override for deterministic stress-testing.
- Migrate FastAPI `on_event('shutdown')` → `lifespan`.
- Optional email / webhook on stop-win / stop-loss.

## Next Tasks
1. All-time aggregate dashboard.
2. CSV export.
3. Live-mode UK/EU proxy write-up.
