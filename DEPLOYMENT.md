# Lay-Lab — UK/EU Deployment Guide

This guide walks you through deploying Lay-Lab on a UK or EU server so that the
Betfair API integration works end-to-end (Paper-Live and Live modes).

> **Why this is needed** — Betfair geo-blocks all non-UK/EU traffic at the
> Cloudflare edge (403 "Restricted"). The app code is correct; it just needs to
> make its outbound requests from an allowed country.

---

## 1. What you need

| Item | Recommended | Notes |
|---|---|---|
| UK/EU VPS | Hetzner CX11 (Falkenstein, EU) — ~£4/mo | Any UK/EU provider works: OVH, Scaleway, Linode London, DigitalOcean London, AWS eu-west-2, Azure UK South, Contabo UK, IONOS UK. |
| OS | Ubuntu 22.04 LTS | Instructions below assume this. |
| Domain | any registrar (~£8/yr) | Optional but required for HTTPS. Free sub-domains via DuckDNS also work. |
| Betfair credentials | App Key + username + password | Already in `backend/.env`. A delayed-data App Key is enough for paper-live. |
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
> # On a fresh Ubuntu 22.04 VPS, as root:
> curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy.sh \
>   | DOMAIN=lay.example.com EMAIL=me@example.com \
>     REPO=https://github.com/<you>/<repo>.git bash
> ```
>
> The script installs every dependency, creates a `laylab` user, builds the
> frontend, starts the API under PM2, configures Nginx and provisions
> Let's Encrypt — typically ~3 minutes end-to-end. Continue reading the manual
> steps below if you'd rather walk through it yourself.

---

SSH into your fresh Ubuntu 22.04 box as a sudo user (e.g. `ubuntu`) and run:

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
git clone https://github.com/<your-username>/<your-repo>.git laylab
cd laylab
```

---

## 5. Backend

```bash
cd ~/laylab/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create the env file **manually on the server** (never commit it):

```bash
cat > .env <<'EOF'
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=laylab
CORS_ORIGINS=*

BETFAIR_APP_KEY=YsAUSaAAUO10jdDw
BETFAIR_USERNAME=ibettison
BETFAIR_PASSWORD=0J[A5yG[[BHT18DgZnXQ
EOF
chmod 600 .env
```

Start the API with PM2 (auto-restart on crash / reboot):

```bash
pm2 start "venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001" \
       --name laylab-api --cwd /home/ubuntu/laylab/backend
pm2 save
pm2 startup systemd -u $USER --hp $HOME   # follow the printed command
```

Smoke-test:

```bash
curl -s http://127.0.0.1:8001/api/ | head
curl -s http://127.0.0.1:8001/api/betfair/status
# expected: {"configured":true,"logged_in":true,...}   <-- no GEO_BLOCKED!
```

---

## 6. Frontend

The React app needs to know the public URL of the backend at **build time**
(not runtime) because `process.env.REACT_APP_BACKEND_URL` is baked into the
bundle.

```bash
cd ~/laylab/frontend

# Point the bundle at your public HTTPS URL
echo "REACT_APP_BACKEND_URL=https://your-domain.com" > .env

yarn install
yarn build          # outputs a static bundle in ./build
```

---

## 7. Nginx reverse proxy

Create `/etc/nginx/sites-available/laylab`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Serve the React build
    root /home/ubuntu/laylab/frontend/build;
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
sudo ln -s /etc/nginx/sites-available/laylab /etc/nginx/sites-enabled/laylab
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

When you push new commits from Emergent to GitHub:

```bash
cd ~/laylab
git pull

# Backend (only if requirements.txt or server.py changed)
cd backend && source venv/bin/activate && pip install -r requirements.txt
pm2 restart laylab-api

# Frontend (any UI change)
cd ../frontend && yarn install && yarn build

sudo systemctl reload nginx
```

Consider wiring this into a GitHub Actions workflow or a simple `deploy.sh` if
you iterate often.

---

## 11. Hardening checklist (optional)

| Concern | Fix |
|---|---|
| Anyone can hit `/api/*` | Add Nginx `basic_auth` or an API token header; the app is single-user. |
| MongoDB exposed | Default `mongod.conf` binds to `127.0.0.1` only — verify with `ss -lntp`. |
| `.env` permissions | `chmod 600 backend/.env`. |
| Live-mode safeguard | Keep `Max Liability Cap` ≤ £5 while you confirm bet placement works correctly. |
| Logs | `pm2 logs laylab-api` for API, `sudo journalctl -u nginx` for web. |
| Backups | Add a nightly `mongodump --db=laylab --out=/backups/$(date +%F)` cron. |

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `GEO_BLOCKED` still showing | VPS is in a non-UK/EU region; some AWS edges also blocked | Pick a confirmed-UK/EU region: Hetzner FSN1/NBG1, OVH UK, Linode London, AWS eu-west-2. |
| `502 Bad Gateway` | Backend not running or wrong port | `pm2 status`, `pm2 logs laylab-api`. |
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

_Last updated: 2026-02-06_
