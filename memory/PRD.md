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

## Backlog
### P1
- Per-race manual winner override (toggle to set winner instead of weighted-random) for deterministic stress-testing.
- Export session as CSV.
- Chart of bank progression (recharts is already in deps).

### P2
- Per-greyhound (not just per-rank) recovery mode option.
- Variable initial stake.
- Configurable recovery depth (currently fixed at 3).
- Sound effects on race result.
- Multi-day session aggregation view.

## Test Status
- Backend: 9/9 pytest tests passing (`/app/backend/tests/test_simulator.py`) — covers CRUD, race-gen invariants, full L0→L3→bust chain, stop conditions, 404s.
- Frontend: critical flow verified by testing agent (90%+); Stop button → badge sync logic confirmed correct in code (manual curl test shows backend returns stopped_manual; setCurrent(updated) propagates to UI).

## Next Tasks
1. Add deterministic winner-override toggle (P1).
2. Add bank progression line chart (P1).
3. CSV export of races + bets (P1).
