# LayHounds Public App

LayHounds is a self-hosted greyhound lay-betting simulator and Betfair live-betting tool.

This public repository contains the customer application only:

- Simulator mode
- Paper-live mode using real Betfair prices
- Live mode for real Betfair lay bets
- Customer-side licence activation and cached validation
- Betfair session, settlement, recovery, and bankroll tools

It deliberately does not contain the private marketing, checkout, Stripe, or licence-issuing system. Those belong in the private licensing/marketing repository.

See [LICENSING_SPLIT.md](./LICENSING_SPLIT.md) for the full public/private split.

## Requirements

- Ubuntu 22.04 or 24.04 VPS
- UK/EU hosting location for Betfair API access
- Domain or subdomain pointing at the VPS
- Betfair App Key, username, and password
- Private licence server URL, for example `https://lay-hounds.co.uk`

Betfair geo-blocks many non-UK/EU hosts, so a local US/non-EU preview environment may show `GEO_BLOCKED` even when the code is correct.

## Quick Public Install

On a fresh Ubuntu VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/YOURNAME/LayHounds/main/deploy.sh \
  | sudo APP_ROLE=public \
      DOMAIN=app.lay-hounds.co.uk \
      EMAIL=you@example.com \
      APP_DIR=/opt/layhounds-public \
      REPO=https://github.com/YOURNAME/LayHounds.git \
      LICENCE_SERVER_URL=https://lay-hounds.co.uk \
      bash
```

The installer will:

- install Python, Node, MongoDB, Nginx, PM2, and Certbot
- clone the public app repo
- create a backend virtualenv
- build the React frontend
- create role-specific `.env` files
- start the backend as `layhounds-public-api`
- configure Nginx for the supplied domain
- request HTTPS via Let's Encrypt

During install, it prompts for Betfair credentials if they are not supplied as environment variables.

If you have already cloned the repo on the VPS, run the wrapper instead:

```bash
sudo APP_ROLE=public \
  DOMAIN=app.lay-hounds.co.uk \
  EMAIL=you@example.com \
  APP_DIR=/opt/layhounds-public \
  LICENCE_SERVER_URL=https://lay-hounds.co.uk \
  ./install.sh
```

## Public App Environment

The installer writes `backend/.env` similar to:

```env
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=layhounds_public
CORS_ORIGINS=https://app.lay-hounds.co.uk
LICENCE_SERVER_URL=https://lay-hounds.co.uk
BETFAIR_APP_KEY=...
BETFAIR_USERNAME=...
BETFAIR_PASSWORD=...
```

Never commit `.env`, Betfair credentials, licence keys, or API secrets.

## Updating

On the VPS:

```bash
cd /opt/layhounds-public
sudo APP_ROLE=public ./update.sh
```

The updater pulls the latest repo code, preserves `.env`, rebuilds only what changed, reloads the PM2 backend process, reloads Nginx, and performs a health check.

## Private Licensing/Marketing App

The private app should live in a separate private repository, for example `LayHounds-Licensing`.

It should contain:

- marketing website
- pricing and checkout pages
- legal pages
- Stripe checkout/status/webhook handling
- central licence database
- `/api/licences/*` validation endpoints
- manual licence seed/admin tools

The public app validates licences against that private service via `LICENCE_SERVER_URL`.

## Useful Commands

View backend logs:

```bash
sudo -u layhounds pm2 logs layhounds-public-api
```

Restart backend:

```bash
sudo -u layhounds pm2 restart layhounds-public-api
```

Check API:

```bash
curl https://app.lay-hounds.co.uk/api/
curl https://app.lay-hounds.co.uk/api/betfair/status
curl https://app.lay-hounds.co.uk/api/licence/diag
```

## More Detail

For the full deployment walkthrough, manual setup, Nginx notes, troubleshooting, and VPS recommendations, read [DEPLOYMENT.md](./DEPLOYMENT.md).

## Licence

Private/proprietary. All rights reserved.
