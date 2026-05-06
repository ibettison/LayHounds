# Lay-Lab — Greyhound Recovery Simulator

A full-stack lay-betting lab for UK greyhound racing. Test configurable
staircase-recovery strategies in a **Simulator**, against real Betfair odds
(**Paper-Live**), or with real lay bets (**Live**).

## Stack

- **Frontend**: React 19 + Tailwind + Shadcn UI + Recharts
- **Backend**: FastAPI + Motor (async MongoDB) + httpx (Betfair JSON-RPC)
- **Storage**: MongoDB

## Features

- 3 modes: Simulator / Paper-Live / Live
- Configurable stake (£0.05 – £2.00), commission (0 – 10%), liability cap
- Recovery depth **L1 – L5** per-favourite-rank
- Monte-Carlo cap-impact preview (1,500 iterations)
- Odds-range filter, batch race execution (1 / 5 / 10 / 25 / 50)
- End-of-day recovery overrun
- Bank carryover across sessions + daily P&L graph
- One-click Reset for clean slates

## Running locally

Development is done inside the Emergent preview pod — hot-reload is enabled for
both frontend and backend.

- Backend: `http://localhost:8001` (supervisor-managed)
- Frontend: `http://localhost:3000` (supervisor-managed)
- MongoDB: `mongodb://localhost:27017`

## Deploying to a UK/EU server

Betfair geo-blocks all non-UK/EU traffic. The preview pod runs in the US, so
Paper-Live and Live modes are disabled here and the header shows
**GEO-BLOCKED**. To use the real Betfair API, deploy to any UK/EU VPS.

**Quick-start** (Ubuntu 22.04, root):

```bash
curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy.sh \
  | DOMAIN=lay.example.com EMAIL=me@example.com \
    REPO=https://github.com/<you>/<repo>.git bash
```

That's it — ~3 minutes later you'll have an HTTPS site with Betfair connected.

👉 **See [DEPLOYMENT.md](./DEPLOYMENT.md)** for the manual step-by-step,
provider comparison, and troubleshooting.

## Repo layout

```
/app
├── backend/
│   ├── server.py            # FastAPI app, all /api routes, sim engine
│   ├── betfair_client.py    # Betfair JSON-RPC httpx client
│   ├── requirements.txt
│   └── tests/               # pytest suite (25 tests)
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── lib/api.js
│   │   └── components/      # Shadcn + custom panels
│   └── package.json
├── memory/
│   ├── PRD.md               # product spec + roadmap
│   └── test_credentials.md
└── DEPLOYMENT.md            # UK/EU production deploy guide
```

## Credentials

Betfair App Key, username and password live in `backend/.env`. Never commit
this file. Deployment hosts get their own `.env` created manually — see
`DEPLOYMENT.md §5`.

## License

Private — for ibettison's personal use.
