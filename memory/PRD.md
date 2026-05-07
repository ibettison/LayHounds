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

### Marketing site (May 2026)
- `pages/Landing.jsx` — one-page hero + features grid + how-it-works + **interactive 10-race demo** + pricing + FAQ + contact form. Bright SaaS aesthetic, framer-motion fade-up scroll reveals.
- `marketing/InteractiveDemo.jsx` — self-contained 10-race auto-playing animation with real recovery math, pause/reset controls, hand-scripted races for narrative drama (clean wins → recovery L1/L2 → big-pop wins). Auto-loops after completion.
- Sticky glassmorphism `MarketingHeader`, dark `MarketingFooter` with responsible-gambling disclaimer (GamCare + BeGambleAware links).
- Pricing card with **Stripe Card** + **PayPal** buttons (Phase 1 stubs).
- `pages/{Terms,Privacy,Refund}.jsx` — full UK-GDPR-compliant legal copy.
- `pages/Checkout.jsx` — `CheckoutSuccess` + `CheckoutCancel` redirect targets.
- New API endpoints (Phase 1 stubs):
  - `POST /api/payments/stripe/checkout`
  - `POST /api/payments/paypal/checkout`
  - `POST /api/contact` (persists to MongoDB `contact_messages`).

## Test status
- **Backend**: **35/35 pytest pass** (`/app/backend/tests/test_simulator.py`, `test_new_features.py`, `test_marketing.py`).
- **Frontend**: full e2e verified by testing agent — all 16 flows pass (iteration_3.json).
- Live mode: not testable from US preview pod (GEO_BLOCKED), code-reviewed only.

## Roadmap

### Phase 2 — Real payments + licence keys (next)
- Real Stripe Checkout Session creation + webhook.
- Real PayPal Subscriptions API + webhook.
- Licence-key issuance on successful checkout (email delivery).
- `/api/licenses/activate` endpoint + simulator UI for pasting key.
- Gate Paper-Live + Live modes behind valid licence.

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
