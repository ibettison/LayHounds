# Licensing Split

LayHounds is now separated into two deployable roles.

## Public customer app

This is the version intended for the public GitHub download. It contains:

- simulator, paper-live, and live Betfair betting logic
- customer-side licence activation and cached validation
- local routes under `/api/licence/*`

It does not need Stripe and does not contain the central licence issuer. The
customer app validates against:

```env
LICENCE_SERVER_URL=https://your-private-licence-host.example
```

## Private licensing app

This version should live in a private repository/deployment. It contains:

- marketing website, pricing pages, checkout success/cancel pages, and legal pages
- `backend/licence_server.py`
- `backend/requirements-licensing.txt`
- any manual licence seed/admin scripts
- Stripe checkout/status/webhook handling
- contact-form/payment routes
- central `/api/licences/*` validation endpoints

Enable it only on the private host:

```env
LICENCE_SERVER_MODE=true
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

The public repository ignores the private licensing files so they are not
accidentally shipped to customers.

During the split, the private-side source was copied locally to `private_app/`
as an ignored staging folder that can be used to seed the private repository.

## Install Examples

Public customer app:

```bash
sudo APP_ROLE=public \
  DOMAIN=app.lay-hounds.co.uk \
  EMAIL=you@example.com \
  APP_DIR=/opt/layhounds-public \
  REPO=https://github.com/YOURNAME/LayHounds.git \
  LICENCE_SERVER_URL=https://lay-hounds.co.uk \
  ./install.sh
```

Private marketing/licensing app:

```bash
sudo APP_ROLE=private \
  DOMAIN=lay-hounds.co.uk \
  EMAIL=you@example.com \
  APP_DIR=/opt/layhounds-private \
  REPO=https://github.com/YOURNAME/LayHounds-Licensing.git \
  ./install.sh
```

## Update Examples

Public customer app:

```bash
cd /opt/layhounds-public
sudo APP_ROLE=public ./update.sh
```

Private marketing/licensing app:

```bash
cd /opt/layhounds-private
sudo APP_ROLE=private ./update.sh
```
