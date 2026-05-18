# Lay-Hounds — Greyhound Recovery Simulator + Marketing Site

> Renamed from Lay-Lab to **Lay-Hounds** on 6 May 2026, when the marketing site shipped.

## Original Problem Statement
Build a Betfair-style system to lay multiple UK greyhounds with a configurable staircase recovery strategy (L1–L5), Monte-Carlo previews, batch racing, daily P&L journal, three execution modes (Simulator / Paper-Live / Live), and — added 6 May 2026 — a public marketing/promotion website at the root URL with Stripe + PayPal checkout for a £19.99/mo Live Unlock.

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB) + httpx (Betfair JSON-RPC). All routes prefixed `/api`.
- **Frontend**: React 19 + react-router-dom 7 + Tailwind + Shadcn UI + Recharts + framer-motion + sonner.
- **Storage**: MongoDB (`sessions`, `contact_messages`).
- **Routing**:
  - `/` — Marketing landing (one-page scroll: Hero, Features, How, Demo, Pricing, FAQ, Contact, Footer)
  - `/app` — The simulator (formerly the entire app)
  - `/terms`, `/privacy`, `/refund` — Legal pages
  - `/checkout/success`, `/checkout/cancel` — Payment redirects
- **Modes**: Simulator (free, fake races) / Paper-Live (real odds, simulated settlement) / Live (real lay bets) — Paper-Live + Live gated behind a future licence-key check (Phase 2).

## Brand
- Name: **Lay-Hounds**
- Domain: lay-hounds.co.uk
- Location: Durham, United Kingdom
- Contact: hello@lay-hounds.co.uk

## Pricing model
- **Free Simulator** — permanent, no card, all simulator features.
- **Live Unlock** — £19.99/month (Stripe or PayPal), unlocks Paper-Live + Live modes. Cancel anytime. 14-day money-back guarantee.

## Implemented (2026-02 → 2026-05)
### Simulator core (Feb 2026)
- Configurable stake (£0.05–£2.00), commission (0–10%), liability cap (bust protection).
- Recovery depth L1–L5 user-configurable.
- Monte-Carlo cap preview (1500 iterations, dynamic level mapping).
- Odds-range filter, batch run-races (1/5/10/25/50), recovery overrun.
- Bank carryover, daily P&L cumulative line + per-session bar chart.
- One-click Reset (DELETE /api/sessions wipes all).
- Dark "Tactical Minimalism" UI with pink #EC4899 accent, Barlow Condensed display + JetBrains Mono.

### Betfair integration (Feb 2026)
- `betfair_client.py` raw httpx JSON-RPC client (login, listMarketCatalogue, listMarketBook, placeOrders, cancelOrders).
- Mode-aware `next-race` endpoint (simulator / paper_live / live).
- Live-mode safeguards (risk_accepted flag, liability cap).
- ⚠️ Live API requires UK/EU host — current preview pod returns GEO_BLOCKED (graceful UI fallback).

### Deployment toolchain (Feb–May 2026)
- `/app/DEPLOYMENT.md` — full UK/EU deploy walkthrough (Hetzner / OVH / Linode / Fasthosts).
- `/app/deploy.sh` — one-command bootstrap on Ubuntu 22.04 (`jammy`) and 24.04 (`noble`); auto-detects codename, picks Python 3.11/3.12 + MongoDB 7.0/8.0; supports `SKIP_TLS=1` and IP-only deployments.
- `/app/update.sh` — zero-downtime updater (atomic frontend swap, `pm2 reload`, smart dep reinstall).
- Slim `requirements.txt` — removed `emergentintegrations` and other Emergent template boilerplate so external deploys install cleanly from public PyPI.

### Betfair Live integration (May 2026, iter 4–5)
- **`betfair_client.get_account_funds()`** — calls `AccountAPING/v1.0/getAccountFunds` (different endpoint to the SportsAPING — added `account=True` flag to `_rpc`).
- **`betfair_client._snap_to_tick()`** — snaps any price to the nearest valid Betfair tick (1.01-2.00 = 0.01 steps, 2-3 = 0.02, ... up to 100-1000 = 10). Prevents `INVALID_BACK_LAY_COMBINATION` rejections.
- **`betfair_client.place_lay_bet()` reworked** — surfaces per-instruction failures (was silently swallowing them, the user's reported "live bet bug"), adds `customer_order_ref` for idempotency, enforces Betfair UK £1.00 minimum stake with a friendly error.
- **`GET /api/betfair/funds`** — returns `{available_to_bet, exposure, exposure_limit, retained_commission, wallet}`.
- **`POST /api/sessions/{id}/refresh-bank`** — re-fetches Betfair balance for a live session and updates `bank` + `total_pnl` delta. Live mode only (paper-live settles locally).
- **`create_session`** — for paper-live + live modes, auto-overrides `starting_bank` with the live Betfair `availableToBetBalance`. Hard-fails with 502 if Betfair can't be reached (no more silent zero-bank sessions).
- **NewSessionDialog** — for paper-live/live, the Starting-Bank input is replaced with a "Live Betfair balance · auto-synced" readout.
- **Simulator header** — new **Sync Bank** button (only for live sessions) pulls the latest Betfair balance and updates the session in place.

### Live race countdown + auto-place (May 2026, iter 5)
- **`SessionConfig.auto_place`** (bool, default False) — only used by live mode.
- **NewSessionDialog** — Switch added inside the Live Mode block: "Auto-place bets 60s before start".
- **`components/LiveCountdown.jsx`** — only shown for active live sessions. Polls `/api/betfair/races` every 30s, locks onto the soonest upcoming UK greyhound market, renders a `MM:SS` countdown to its scheduled start, glows pink and pulses when ≤ 60s. If `auto_place` is ON it fires `runNextRace({ auto: true })` exactly once at T-60s per market (deduped via `firedRef` Set).
- **`runNextRace`** — refactored into a `useCallback` and now accepts an `{ auto: true }` flag so AUTO-placed bets show with an "AUTO · " prefix in success/error toasts.
- **Defensive URL guard in `lib/api.js`** — `resolveBackendUrl()` strips trailing slashes, auto-prefixes `https://` for bare hostnames, falls back to `window.location.origin` if the env was empty at build time, and throws a clear human error if `REACT_APP_BACKEND_URL` is malformed (fixes "Failed to construct URL" UX).

### Marketing site (May 2026)
- `pages/Landing.jsx` — one-page hero + features grid + how-it-works + **interactive 10-race demo** + pricing + FAQ + contact form. Bright SaaS aesthetic, framer-motion fade-up scroll reveals.
- `marketing/InteractiveDemo.jsx` — self-contained 10-race auto-playing animation with real recovery math, pause/reset controls, hand-scripted races for narrative drama. **3 scenarios** (Recovery Pop / Steady Grinder / Cap Crisis) cyclable via the "Try Different" toolbar button — each with its own stake, starting bank, race script, and (for Cap Crisis) liability cap. Auto-loops after completion.
- Sticky glassmorphism `MarketingHeader`, dark `MarketingFooter` with responsible-gambling disclaimer (GamCare + BeGambleAware links).
- Pricing card with **Stripe Card** + **PayPal** buttons (Phase 1 stubs).
- `pages/{Terms,Privacy,Refund}.jsx` — full UK-GDPR-compliant legal copy.
- `pages/Checkout.jsx` — `CheckoutSuccess` + `CheckoutCancel` redirect targets.
- New API endpoints (Phase 1 stubs):
  - `POST /api/payments/stripe/checkout`
  - `POST /api/payments/paypal/checkout`
  - `POST /api/contact` (persists to MongoDB `contact_messages`).

### Bulletproof update.sh + auto-swap (May 2026, iter 8) — fixes "I had to reimage the VPS"
Root cause of the recurring reimage: small VPSs (Fasthosts £5/mo, 1-2 GB RAM, **no swap**) get OOM-killed by `yarn build` (the React 19 + framer-motion + recharts bundle peaks at ~1.8 GB). The OOM-killer takes Mongo + Nginx down with it → user thinks the box is bricked.

Fixes shipped:
- **`update.sh` v2** — full rewrite (~280 lines, was ~150):
  - Auto-creates a 2 GB `/swapfile` if total RAM+swap headroom < 1.8 GB (persists in `/etc/fstab`). Skip with `SKIP_SWAP=1`.
  - Caps Node heap at 1 GB via `NODE_OPTIONS=--max-old-space-size=1024`.
  - **Snapshot** of `git SHA + frontend/build/ + .env` files into `$APP_DIR/.update-snapshot/` before any mutation.
  - **trap-based auto-rollback** on ANY failure (pip install crash, yarn build OOM, nginx config invalid, API not 200 within 30 s, atomic-swap mv fails) — restores commit + build + `.env` + restarts PM2.
  - **`flock` single-run lock** at `/var/lock/layhounds-update.lock` prevents two updates racing.
  - `.env` files explicitly stashed + restored around the `git reset --hard` so credentials are never lost.
  - Post-reload health check: polls `/api/` for up to 30 s; if not 200, automatic rollback.
  - Pre-flight prints `free -h` + `df -h` so the operator sees the box state before mutation.
- **`deploy.sh`** — same auto-swap on first install, same `NODE_OPTIONS=--max-old-space-size=1024` on the first `yarn build`.
- **`DEPLOYMENT.md`** — full rewrite of the "Updating the app later" section documenting the new safety features + new env vars (`SKIP_SWAP`, `SKIP_HEALTH`).
- Bash syntax-checked; rollback path sandbox-tested with a fake APP_DIR.

### Race categories + win-rate calibration (May 2026, iter 7)
- **`race_categories.py`** — new module with industry-published favourite-win rates by:
  - **UK Grades**: A1-A11, OR (Open Race), H1-H3 (Hurdles).
  - **Distance bands**: Sprint (≤320m), Standard (321-499m), Stayer (500-619m), Marathon (620m+).
- Every race now carries a `RaceCategory` (grade + distance_m + distance_band) — auto-detected per race:
  - **Simulator**: weighted-random grade + distance from realistic UK card distribution.
  - **Paper-Live / Live**: parsed from the Betfair `marketName` via regex (e.g. "Romford 19:24 R3 480m A4" → grade=A4, distance=480m, band=Standard).
- **Blended winner picking**: `pick_winner(runners, category)` now uses `target_rate[rank] * (1/odds)^0.15`. Long-run distribution calibrated to ~32% / 22% / 17% / 13% / 10% / 7% by favourite rank (±1% on a 20k-race Monte-Carlo) while odds still drive within-race variance.
- **Frontend**: `RaceCard` shows pink **grade** + grey **distance** + band-label badges below the venue. `RaceHistory` adds a compact `R# VENUE A4 · 480m` line for each historical race.
- **Tests**: `test_race_categories.py` adds 29 new tests — grade/band tables sum to 1.0, regex detection covers OR + hurdles + marathon, long-run-distribution test asserts every rank within ±2% of target over 20k races, integration test against `/api/sessions/{id}/next-race` confirms category is persisted on the Race document.

### Central licensing system (May 2026, iter 5–6) — Phase 2 SHIPPED
- **`licences.py`** — dual-role module (central + customer). LICENCE_SERVER_MODE=true makes this box the licence host; LICENCE_SERVER_URL points each customer VPS at it.
- **Central role** (lay-hounds.co.uk): `POST /api/licences/{activate,release,validate}` — UUID install_id binding, 409 on cross-install reuse, 30-day current_period_end.
- **Customer role** (each VPS): `GET /api/licence/status`, `POST /api/licence/{activate,release,refresh}` — local Mongo `app_meta` caches install_id + validation state, hourly background revalidate loop with 7-day offline grace.
- **Stripe Checkout** — **rewritten to use the official `stripe` Python SDK directly** (iter-6) so external VPS deploys install cleanly from public PyPI — removed `emergentintegrations` from requirements.txt because it lives on a private Emergent mirror and was blocking `pip install -r requirements.txt` on user VPSs. `POST /api/payments/stripe/checkout` creates a Checkout Session (`mode=payment`, line_items price_data £19.99 GBP, idempotent), `GET /api/payments/stripe/status/{sid}` polls + mints a licence on first `paid`, `POST /api/webhook/stripe` handles async path with optional `STRIPE_WEBHOOK_SECRET` signature verification.
- **Friendly placeholder check** — server returns a 500 with a copy-pasteable hint ("get a key from dashboard.stripe.com/test/apikeys") instead of a raw Stripe AuthenticationError when STRIPE_API_KEY is the dev placeholder `sk_test_emergent`.
- **Licence gate on session create** — `POST /api/sessions` with `mode in (paper_live, live)` returns **HTTP 402 "Live Unlock required"** when no active licence is bound; passes through to Betfair (502 GEO_BLOCKED in US pod / real funds on UK VPS) once activated.
- **`LicencePanel.jsx`** — left-sidebar widget on `/app` showing status badge, masked key, renews-on date, last-validated timestamp, release button. Pulls from `/api/licence/status`, surfaces activation toasts, hides itself entirely if the licence module isn't wired.

## Test status
- **Backend**: **54/54 pytest pass** (`test_simulator.py`, `test_new_features.py`, `test_marketing.py`, `test_betfair_integration.py`, `test_licensing.py` NEW).
- **Frontend**: full e2e verified by testing agent — iteration_5.json — all LicencePanel flows (mount, activate, refresh, release) + Stripe checkout URL generation pass.
- Live mode: not testable from US preview pod (GEO_BLOCKED), code-reviewed only.

## Test credentials
See `/app/memory/test_credentials.md`. Seeded test licence key: `LH-TEST-AAAA-BBBB-CCCC` (valid 30 days, manual provider). Auto-released at module teardown by `test_betfair_integration.py` autouse fixture.

## Roadmap

### Phase 2.5 — Real recurring + PayPal + email
- Switch Stripe from one-time £19.99 → recurring price_id with auto-renewal webhook handling.
- Real PayPal Subscriptions API + webhook.
- Resend email delivery of licence keys on first paid event.
- Customer portal page for self-service licence-key management (view bound install, release, change card).

### Phase 3 — backlog
- Aggregate all-time dashboard across all historical days.
- CSV export of races + bets.
- Per-dog (vs per-rank) recovery toggle.
- Email/Telegram alert on stop-win / stop-loss.
- Auto-settlement of live bets via market polling.
- Migrate `@app.on_event('shutdown')` → lifespan.
- Split `server.py` (now ~700 lines) into route modules (`/app/backend/routes/{sessions,marketing,payments}.py`).
- Strategy Comparison overlay (run two configs side-by-side).
- Carry-forward: DailyChart Recharts negative-height warnings (cosmetic, chart still functional).

## Files of reference
- `/app/frontend/src/App.js` — Router shell
- `/app/frontend/src/pages/Landing.jsx` — Marketing one-page
- `/app/frontend/src/pages/Simulator.jsx` — The simulator (was App.js)
- `/app/frontend/src/marketing/MarketingLayout.jsx`, `LegalShell.jsx`
- `/app/backend/server.py` — All API routes
- `/app/deploy.sh`, `/app/update.sh`, `/app/DEPLOYMENT.md`
- `/app/design_guidelines.json` — Marketing site design system

## Credentials
- Betfair: `backend/.env` (App Key + username + password). User-supplied per install.
- Stripe / PayPal: env-var placeholders; real keys to land in Phase 2.
