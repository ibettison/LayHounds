# LayHounds Public App

LayHounds is a self-hosted greyhound lay-betting simulator and Betfair live-betting tool.

This public repository contains the customer application only:

- Simulator mode
- Paper-live mode using real Betfair prices
- Live mode for real Betfair lay bets
- Customer-side licence activation and cached validation
- Betfair session, settlement, recovery, and bankroll tools

Paper-live and Live mode require a valid licence key, supplied after purchase.

## Requirements

- Ubuntu 22.04 or 24.04 VPS
- UK/EU hosting location for Betfair API access
- Domain or subdomain pointing at the VPS
- Betfair App Key, username, and password
- Private licence server URL, for example `https://lay-hounds.co.uk`

Betfair geo-blocks many non-UK/EU hosts, so a local US/non-EU preview environment may show `GEO_BLOCKED` even when the code is correct.

## Need A VPS?

LayHounds needs to run from a UK/EU server for Betfair API access. If you do not already have one, you can use this referral link to set up a UK VPS:

[Launch a Fasthosts VPS](https://www.fasthosts.co.uk/referral?referral=37u6fp7gtbgc9n)

Recommended minimum: Ubuntu 22.04 or 24.04, 2 GB RAM, 1 vCPU, and enough disk for MongoDB, Node, and build artifacts.

## Quick Public Install

On a fresh Ubuntu VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/YOURNAME/LayHounds/main/deploy.sh \
  | sudo \
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
- create public app `.env` files
- start the backend as `layhounds-public-api`
- configure Nginx for the supplied domain
- request HTTPS via Let's Encrypt

During install, it prompts for the licence server URL and Betfair credentials if
they are not supplied as environment variables. For non-interactive installs,
add `LICENCE_SERVER_URL`, `BETFAIR_APP_KEY`, `BETFAIR_USERNAME`, and
`BETFAIR_PASSWORD` to the command.

If you have already cloned the repo on the VPS, run the wrapper instead:

```bash
sudo \
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
sudo ./update.sh
```

The updater pulls the latest repo code, preserves `.env`, rebuilds only what changed, reloads the PM2 backend process, reloads Nginx, and performs a health check.

## Licence Keys

Simulator mode can be used without a licence key. Paper-live and Live mode are unlocked by activating the licence key supplied after purchase.

The app validates that key against the configured licence server:

```env
LICENCE_SERVER_URL=https://lay-hounds.co.uk
```

Use the Licence panel inside the app to paste and activate your key.

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
