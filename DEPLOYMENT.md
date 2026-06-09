# LayHounds — UK/EU Deployment Guide

This guide walks you through deploying LayHounds on a UK or EU server so that the
Betfair API integration works end-to-end (Paper-Live and Live modes).

> **Why this is needed** — Betfair geo-blocks all non-UK/EU traffic at the
> Cloudflare edge (403 "Restricted"). The app code is correct; it just needs to
> make its outbound requests from an allowed country.

---

## 1. What you need

| Item | Recommended | Notes |
|---|---|---|
| UK/EU VPS | Hetzner CX11 (Falkenstein, EU) — ~£4/mo | Any UK/EU provider works: OVH, Scaleway, Linode London, DigitalOcean London, AWS eu-west-2, Azure UK South, Contabo UK, IONOS UK. |
| OS | Ubuntu 24.04 LTS (recommended) or 22.04 LTS | The bundled `deploy.sh` auto-detects which one you're on and installs the matching Python (3.12 / 3.11) and MongoDB (8.0 / 7.0). |
| Domain | any registrar (~£8/yr) | Optional but required for HTTPS. Free sub-domains via DuckDNS also work. |
| Betfair credentials | App Key + username + password | Created by you at developer.betfair.com — **never paste them into any tracked file**. A delayed-data App Key is enough for paper-live. |
| RAM / CPU | 2 GB / 1 vCPU | Enough for a single user. MongoDB is the heaviest component. |

---

## 2. Architecture on the VPS

```
┌───────────────── UK VPS (Ubuntu 22.04) ─────────────────┐
│                                                          │
│  Nginx :443 (HTTPS)                                      │
│     │                                                    │
│     ├─▶ /              static React build (frontend/)    │
│     └─▶ /api/*  ──▶ :8001  uvicorn FastAPI (backend/)    │
│                        │                                 │
│                        ├─▶ MongoDB :27017 (localhost)    │
│                        └─▶ Betfair API  (now allowed!)   │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Server bootstrap (one-time)

> 💡 **Want it all done in one command?** Skip steps 3–8 and use `deploy.sh`:
>
> ```bash
> # On a fresh Ubuntu 22.04 or 24.04 VPS, as root:
> curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy.sh \
>   | DOMAIN=lay.example.com EMAIL=me@example.com \
>     REPO=https://github.com/<you>/<repo>.git bash
> ```
>
> The script auto-detects 22.04 (`jammy`) vs 24.04 (`noble`), installs the
> matching Python and MongoDB versions, creates a `layhounds` user, builds the
> frontend, starts the API under PM2, configures Nginx and provisions
> Let's Encrypt — typically ~3 minutes end-to-end. Continue reading the manual
> steps below if you'd rather walk through it yourself.

---

SSH into your fresh Ubuntu box as a sudo user (e.g. `ubuntu`) and run:

```bash
# --- System packages
sudo apt update && sudo apt -y upgrade
sudo apt install -y python3.11 python3.11-venv python3-pip \
                    nginx git curl gnupg ufw

# --- Node 20 + Yarn
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
sudo npm install -g yarn pm2

# --- MongoDB 7.0
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb.gpg --dearmor
echo "deb [signed-by=/usr/share/keyrings/mongodb.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update && sudo apt install -y mongodb-org
sudo systemctl enable --now mongod

# --- Timezone (so Betfair market-start times display correctly)
sudo timedatectl set-timezone Europe/London

# --- Firewall
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
```

---

## 4. Pull the code

Use the **"Save to GitHub"** button inside the Emergent chat input to export
the repo, then clone it on the VPS:

```bash
cd ~
git clone https://github.com/<your-username>/<your-repo>.git layhounds
cd layhounds
```

---

## 5. Backend

```bash
cd ~/layhounds/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create the env file **manually on the server** (never commit it — `.env` is
already in `.gitignore`):

> **SECURITY WARNING**: Never paste your real Betfair App Key, username, or
> password into this document, the README, or any file that could be committed
> to git. Treat them like a credit-card number. If you ever accidentally commit
> them, **rotate them immediately** at
> [developer.betfair.com](https://developer.betfair.com) (regenerate App Key)
> and change your Betfair account password.

```bash
cat > .env <<'EOF'
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=layhounds
CORS_ORIGINS=*

# Replace the placeholders below with YOUR credentials.
# Generate the App Key at https://developer.betfair.com/visualisers/api-accounts-operations/
BETFAIR_APP_KEY=<your-betfair-app-key>
BETFAIR_USERNAME=<your-betfair-username>
BETFAIR_PASSWORD=<your-betfair-password>

# ── Licence server config ─────────────────────────────────────────────
# CUSTOMER installs (every customer's VPS): point at the central server
LICENCE_SERVER_URL=https://lay-hounds.co.uk

# CENTRAL install (lay-hounds.co.uk ONLY — also accepts customers).
# Drop a REAL Stripe secret key here (get one free from
# https://dashboard.stripe.com/test/apikeys after creating an account).
# Lay-Hounds talks directly to Stripe via the official `stripe` Python SDK.
# LICENCE_SERVER_MODE=true
# STRIPE_API_KEY=sk_live_xxxxxxxxxx
# STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxx   # optional but recommended in prod
EOF
chmod 600 .env
```

Start the API with PM2 (auto-restart on crash / reboot):

```bash
pm2 start "venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001" \
       --name layhounds-api --cwd /home/ubuntu/layhounds/backend
pm2 save
pm2 startup systemd -u $USER --hp $HOME   # follow the printed command
```

Smoke-test:

```bash
curl -s http://127.0.0.1:8001/api/ | head
curl -s http://127.0.0.1:8001/api/betfair/status
# expected: {"configured":true,"logged_in":true,...}   <-- no GEO_BLOCKED!

curl -s http://127.0.0.1:8001/api/licence/diag | python3 -m json.tool
# Shows: install_id, config snapshot, # of licences seeded in this DB,
# and whether LICENCE_SERVER_URL is reachable. The single best place to
# look first when "Licence server: not found" or activation issues show up.
```

### Issuing licences

The public/customer app no longer contains licence-issuing tools. Licence
generation, Stripe checkout, Stripe webhooks, and any manual seed/admin scripts
belong in the private licensing repository/deployment only.

Customer installs should only set:

```bash
LICENCE_SERVER_URL=https://your-private-licence-host.example
```

The licence server URL is provided with your purchase/licence details.

---

## 6. Frontend

The React app needs to know the public URL of the backend at **build time**
(not runtime) because `process.env.REACT_APP_BACKEND_URL` is baked into the
bundle.

```bash
cd ~/layhounds/frontend

# Point the bundle at your public HTTPS URL
echo "REACT_APP_BACKEND_URL=https://your-domain.com" > .env

yarn install
yarn build          # outputs a static bundle in ./build
```

---

## 7. Nginx reverse proxy

Create `/etc/nginx/sites-available/layhounds`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Serve the React build
    root /home/ubuntu/layhounds/frontend/build;
    index index.html;

    # API proxy
    location /api/ {
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/layhounds /etc/nginx/sites-enabled/layhounds
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. HTTPS (Let's Encrypt)

Point your domain's A record at the VPS IP, then:

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
sudo certbot --nginx -d your-domain.com
```

Certbot auto-configures Nginx and installs a renewal cron.

---

## 9. Verify end-to-end

Open `https://your-domain.com` in the browser, then confirm:

- [ ] Header shows **BETFAIR OK** (pink) instead of **GEO-BLOCKED** (amber).
- [ ] `New Session → Mode` — both **Paper-Live** and **Live** tiles are clickable.
- [ ] `curl https://your-domain.com/api/betfair/races?minutes_ahead=60` returns
      a non-empty `markets` array.
- [ ] Creating a Paper-Live session and clicking "Run Next Race" returns real
      Betfair runners and odds (check the Race Card shows real dog names).

If all four pass — you're live.

---

## 10. Updating the app later

When you push new commits from Emergent to GitHub, just run the bundled
**`update.sh`** on the VPS.

### Layout: where does the repo live?

`update.sh` supports two layouts and auto-detects which one you're using:

**Two-stage (recommended)** — keep your git clone in your home directory, the
runtime in `/opt/layhounds`:
```bash
~/layhounds/    ← git clone (owned by your user)
/opt/layhounds/ ← runtime (owned by 'layhounds' user; venv/build/node_modules/.env live here)
```
Run it like this:
```bash
cd ~/layhounds && sudo ./update.sh
```
The script will `git pull` in `~/layhounds`, then `rsync` the source into
`/opt/layhounds` — explicitly EXCLUDING `.env`, `frontend/build`, `backend/venv`,
and `node_modules` so the runtime stays self-consistent.

**Single-stage** — repo and runtime are the same dir:
```bash
cd /opt/layhounds && sudo ./update.sh
```
The script auto-detects this layout (REPO_DIR == APP_DIR) and skips the rsync step.

Override either path explicitly:
```bash
sudo REPO_DIR=/home/me/code/lay-hounds APP_DIR=/srv/lh ./update.sh
```

### Safety features

The script (v2, hardened May 2026):

- **OOM-proofs the box** — if your VPS has < 1.8 GB of total RAM+swap headroom, it
  auto-creates a 2 GB `/swapfile` before doing anything risky. This is the **#1
  cause of "I had to reimage my VPS"** — small Fasthosts/Linode/OVH plans (1-2 GB
  RAM, no swap) get killed by `yarn build` and take Mongo + Nginx down with them.
- **Caps Node heap** at 1 GB (`NODE_OPTIONS=--max-old-space-size=1024`) so even a
  runaway build can't eat the whole machine.
- **Snapshots before mutating** — saves the current git SHA, the current
  `frontend/build/`, and both `.env` files into `$APP_DIR/.update-snapshot/`.
- **Auto-rollback on ANY failure** — `pip install` blows up? `yarn build`
  OOM-killed? Nginx config invalid? API doesn't answer 200 within 30 s? The
  script restores the previous commit + previous build + previous `.env` and
  restarts PM2, leaving you at the version you were on before.
- **`.env` files NEVER overwritten** — the rsync step explicitly excludes them,
  so credentials in `/opt/layhounds/backend/.env` survive every update.
- **Single-run lock** (`flock`) prevents two updates from racing each other.
- Pulls the latest commit, detects which paths changed, only reinstalls Python
  deps if `requirements.txt` moved, only rebuilds the React bundle if anything
  under `frontend/` changed — and builds into `build.new/` first, then
  **atomically swaps** so Nginx never serves a half-built bundle.
- Rolls the API with `pm2 reload` (graceful, zero-downtime — in-flight requests
  finish on the old workers before the new ones take over).
- Reloads Nginx, then **polls `/api/` for up to 30 s** — if it doesn't return
  200, the script rolls back automatically.

Force a full rebuild even when nothing changed:

```bash
sudo FORCE=1 ./update.sh
```

Switch branch on the way:

```bash
sudo BRANCH=staging ./update.sh
```

Skip the health-check at the end (e.g. if the domain isn't yet pointed at this
box):

```bash
sudo SKIP_HEALTH=1 ./update.sh
```

Skip the auto-swap creation (you've already added your own):

```bash
sudo SKIP_SWAP=1 ./update.sh
```

Wire it to a cron / GitHub webhook later if you want auto-deploys.

---

## 11. Hardening checklist (optional)

| Concern | Fix |
|---|---|
| **Credentials in tracked files** | **NEVER paste real Betfair App Key, username, password, Stripe keys, or any secret into `DEPLOYMENT.md`, `README.md`, or anywhere else that gets pushed to git. They live in `backend/.env` (which is already in `.gitignore`) and nowhere else. If you ever notice a real secret in a tracked file: (1) rotate it at the provider IMMEDIATELY (regenerate Betfair App Key at developer.betfair.com; change Betfair password; revoke + recreate Stripe key); (2) `git rm` the offending content and `git commit --amend` if the leaking commit is the last one, or `git filter-repo` / BFG if it's deeper in history. |
| Anyone can hit `/api/*` | Add Nginx `basic_auth` or an API token header; the app is single-user. |
| MongoDB exposed | Default `mongod.conf` binds to `127.0.0.1` only — verify with `ss -lntp`. |
| `.env` permissions | `chmod 600 backend/.env`. |
| Live-mode safeguard | Keep `Max Liability Cap` ≤ £5 while you confirm bet placement works correctly. |
| Logs | `pm2 logs layhounds-api` for API, `sudo journalctl -u nginx` for web. |
| Backups | Add a nightly `mongodump --db=layhounds --out=/backups/$(date +%F)` cron. |

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Licence server: Licence key not found` | The licence key you typed does not exist in the private central licensing database. | Issue the key from the private licensing deployment, or complete the real Stripe checkout to mint one. Confirm the customer app can reach the host via `curl http://127.0.0.1:8001/api/licence/diag`. |
| `Could not reach licence server` | `LICENCE_SERVER_URL` is wrong, the central host is down, or a firewall is in the way. | Check `curl http://127.0.0.1:8001/api/licence/diag` — the `connectivity` block tells you exactly which URL was tried and the error. |
| `Live Unlock required` (HTTP 402 on session create) | Paper-Live/Live mode requires an active licence. | Activate a key issued by the private licensing service, or use Simulator mode for free testing. |
| `GEO_BLOCKED` still showing | VPS is in a non-UK/EU region; some AWS edges also blocked | Pick a confirmed-UK/EU region: Hetzner FSN1/NBG1, OVH UK, Linode London, AWS eu-west-2. |
| `502 Bad Gateway` | Backend not running or wrong port | `pm2 status`, `pm2 logs layhounds-api`. |
| Betfair login 401 | Password contains shell-special chars in `.env` not quoted | Wrap the value in single quotes or escape `$`, `[`, `]`. |
| Live bets not settling | App does not poll Betfair for CLOSED markets yet | Settle manually via Betfair web UI; auto-settlement is on the P1 roadmap. |
| CORS errors in browser | `CORS_ORIGINS` too strict | Set `CORS_ORIGINS=https://your-domain.com` or `*` for sandbox. |

---

## 13. Cost estimate (per month, £)

| Item | Low | Mid | High |
|---|---|---|---|
| VPS | Hetzner CX11 — £4 | DO London 1 GB — £5 | AWS t3.small London — £13 |
| Domain | £8/yr ≈ £0.70 | same | same |
| Backups (optional) | £1 (Hetzner snapshot) | £1 | £3 (AWS EBS) |
| **Total** | **~£6** | **~£7** | **~£17** |

Delayed-data Betfair App Key is free. Live-data key requires a one-off £299
developer fee from Betfair.

---

_Last updated: 2026-05-18_
