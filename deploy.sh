#!/usr/bin/env bash
# ==============================================================================
#  Lay-Hounds — one-command UK/EU deployment bootstrap
# ------------------------------------------------------------------------------
#  Takes a fresh Ubuntu 22.04 LTS VPS (root or sudo user) to a live HTTPS site
#  with the Betfair integration working end-to-end.
#
#  Usage:
#    curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy.sh | \
#      sudo DOMAIN=lay.example.com EMAIL=me@example.com \
#           REPO=https://github.com/<you>/<repo>.git bash
#
#  Or, if you've already cloned the repo:
#    sudo DOMAIN=lay.example.com EMAIL=me@example.com ./deploy.sh
#
#  Required env vars:
#    DOMAIN   — public DNS name already pointed at this VPS
#    EMAIL    — for Let's Encrypt expiry notices
#
#  Optional env vars:
#    REPO             — git URL to clone (skip if running from inside the repo)
#    APP_DIR          — install path (default: /opt/layhounds)
#    APP_USER         — owner of app files (default: layhounds)
#    BETFAIR_APP_KEY  — prompted if missing
#    BETFAIR_USERNAME — prompted if missing
#    BETFAIR_PASSWORD — prompted if missing
#    SKIP_TLS=1       — skip certbot (HTTP-only, e.g. for staging)
# ==============================================================================

set -euo pipefail

# ---------- Helpers -----------------------------------------------------------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
log()   { echo -e "${GREEN}[+] $*${NC}"; }
warn()  { echo -e "${YELLOW}[!] $*${NC}"; }
die()   { echo -e "${RED}[x] $*${NC}" >&2; exit 1; }
step()  { echo -e "\n${BOLD}==> $*${NC}"; }

[ "${EUID:-$(id -u)}" -eq 0 ] || die "Run as root (or via sudo)."
[ -f /etc/os-release ] && . /etc/os-release
[ "${ID:-}" = "ubuntu" ]        || warn "Tested on Ubuntu 22.04 / 24.04 (detected: ${ID:-unknown})."

: "${DOMAIN:?Set DOMAIN=your-domain.com OR your server IP}"

APP_DIR="${APP_DIR:-/opt/layhounds}"
APP_USER="${APP_USER:-layhounds}"
REPO="${REPO:-}"
SKIP_TLS="${SKIP_TLS:-0}"

# If DOMAIN looks like an IPv4 address, force HTTP-only (Let's Encrypt won't
# issue certs for raw IPs).
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  if [ "$SKIP_TLS" != "1" ]; then
    warn "DOMAIN looks like an IP address — forcing SKIP_TLS=1 (HTTPS needs a real DNS name)."
    SKIP_TLS=1
  fi
fi

# EMAIL only required when we're actually going to run certbot.
if [ "$SKIP_TLS" != "1" ]; then
  : "${EMAIL:?Set EMAIL=you@example.com (for Lets Encrypt) or pass SKIP_TLS=1}"
fi
EMAIL="${EMAIL:-noreply@example.com}"

# ---------- Prompt for missing Betfair creds ----------------------------------
prompt_if_empty() {
  local var="$1" msg="$2" silent="${3:-0}"
  if [ -z "${!var:-}" ]; then
    if [ "$silent" = "1" ]; then
      read -rsp "$msg: " val; echo
    else
      read -rp "$msg: " val
    fi
    export "$var=$val"
  fi
}
prompt_if_empty BETFAIR_APP_KEY  "Betfair App Key"
prompt_if_empty BETFAIR_USERNAME "Betfair username"
prompt_if_empty BETFAIR_PASSWORD "Betfair password" 1

# ==============================================================================
step "1/8  System packages"
# ==============================================================================
export DEBIAN_FRONTEND=noninteractive

# Detect Ubuntu release → pick matching Python and MongoDB versions.
. /etc/os-release
CODENAME="${VERSION_CODENAME:-jammy}"

case "$CODENAME" in
  jammy)   # Ubuntu 22.04
    PY_PKG="python3.11"
    PY_BIN="python3.11"
    MONGO_VER="7.0"
    MONGO_CODENAME="jammy"
    ;;
  noble)   # Ubuntu 24.04
    PY_PKG="python3.12"
    PY_BIN="python3.12"
    MONGO_VER="8.0"
    MONGO_CODENAME="noble"
    ;;
  *)
    warn "Untested Ubuntu codename '$CODENAME' — falling back to system python3 + MongoDB 8.0/noble repo."
    PY_PKG="python3"
    PY_BIN="python3"
    MONGO_VER="8.0"
    MONGO_CODENAME="noble"
    ;;
esac
log "Detected Ubuntu '$CODENAME' → $PY_BIN + MongoDB $MONGO_VER ($MONGO_CODENAME repo)"

apt-get update -y
apt-get install -y "$PY_PKG" "${PY_PKG}-venv" python3-pip \
                   nginx git curl gnupg ufw ca-certificates lsb-release rsync

# ── OOM protection: tiny VPSs (≤2 GB RAM, no swap) get killed by `yarn build`.
# Auto-create a 2 GB swap file if we have < 1.8 GB of total memory headroom.
if [ "${SKIP_SWAP:-0}" != "1" ]; then
  MEM_TOTAL_MB=$(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo)
  SWAP_TOTAL_MB=$(awk '/^SwapTotal:/ {print int($2/1024)}' /proc/meminfo)
  if [ $((MEM_TOTAL_MB + SWAP_TOTAL_MB)) -lt 1800 ] && [ ! -f /swapfile ]; then
    log "Memory headroom is ${MEM_TOTAL_MB}MB RAM + ${SWAP_TOTAL_MB}MB swap — creating /swapfile (2 GB) to survive yarn build."
    if fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048; then
      chmod 600 /swapfile
      mkswap /swapfile >/dev/null
      swapon /swapfile
      grep -q "^/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
      log "Swap online."
    fi
  fi
fi

# Node 20 + yarn + pm2
if ! command -v node >/dev/null || [ "$(node -v | cut -c2-3)" != "20" ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
npm install -g yarn pm2 >/dev/null

# MongoDB
if ! command -v mongod >/dev/null; then
  curl -fsSL "https://pgp.mongodb.com/server-${MONGO_VER}.asc" | \
    gpg -o /usr/share/keyrings/mongodb.gpg --dearmor
  echo "deb [signed-by=/usr/share/keyrings/mongodb.gpg] https://repo.mongodb.org/apt/ubuntu ${MONGO_CODENAME}/mongodb-org/${MONGO_VER} multiverse" \
    > "/etc/apt/sources.list.d/mongodb-org-${MONGO_VER}.list"
  apt-get update -y
  apt-get install -y mongodb-org
fi
systemctl enable --now mongod

# Timezone (Europe/London so Betfair market times display correctly)
timedatectl set-timezone Europe/London || true

# Firewall
ufw allow OpenSSH          >/dev/null || true
ufw allow 'Nginx Full'     >/dev/null || true
ufw --force enable         >/dev/null || true

# ==============================================================================
step "2/8  Application user + source code"
# ==============================================================================
id -u "$APP_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$APP_USER"

if [ -n "$REPO" ]; then
  if [ -d "$APP_DIR/.git" ]; then
    log "Repo already at $APP_DIR — pulling latest"
    sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
  else
    log "Cloning $REPO → $APP_DIR"
    mkdir -p "$APP_DIR"
    chown "$APP_USER:$APP_USER" "$APP_DIR"
    sudo -u "$APP_USER" git clone "$REPO" "$APP_DIR"
  fi
else
  # Running from inside the repo
  SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ "$SELF_DIR" != "$APP_DIR" ]; then
    log "Copying repo from $SELF_DIR → $APP_DIR"
    mkdir -p "$APP_DIR"
    rsync -a --delete --exclude='.git' --exclude='node_modules' \
          --exclude='frontend/build' --exclude='backend/venv' \
          "$SELF_DIR/" "$APP_DIR/"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
  fi
fi

[ -d "$APP_DIR/backend"  ] || die "Missing $APP_DIR/backend — bad REPO or wrong cwd."
[ -d "$APP_DIR/frontend" ] || die "Missing $APP_DIR/frontend — bad REPO or wrong cwd."

# ==============================================================================
step "3/8  Backend venv + dependencies"
# ==============================================================================
sudo -u "$APP_USER" bash <<EOF
set -e
cd "$APP_DIR/backend"
[ -d venv ] || ${PY_BIN} -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel >/dev/null
pip install -r requirements.txt
EOF

# ==============================================================================
step "4/8  Backend .env"
# ==============================================================================
PROTO_BUILD="https"
[ "$SKIP_TLS" = "1" ] && PROTO_BUILD="http"
PUBLIC_URL="${PROTO_BUILD}://${DOMAIN}"

BE_ENV="$APP_DIR/backend/.env"
cat > "$BE_ENV" <<EOF
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=layhounds
CORS_ORIGINS=${PUBLIC_URL}
BETFAIR_APP_KEY=${BETFAIR_APP_KEY}
BETFAIR_USERNAME=${BETFAIR_USERNAME}
BETFAIR_PASSWORD=${BETFAIR_PASSWORD}
EOF
chown "$APP_USER:$APP_USER" "$BE_ENV"
chmod 600 "$BE_ENV"

# ==============================================================================
step "5/8  Frontend build"
# ==============================================================================
echo "REACT_APP_BACKEND_URL=${PUBLIC_URL}" > "$APP_DIR/frontend/.env"
chown "$APP_USER:$APP_USER" "$APP_DIR/frontend/.env"

sudo -u "$APP_USER" env NODE_OPTIONS="--max-old-space-size=1024" bash <<EOF
set -e
cd "$APP_DIR/frontend"
yarn install --frozen-lockfile
CI=false yarn build
EOF

# ==============================================================================
step "6/8  Start API with PM2 (auto-start on boot)"
# ==============================================================================
sudo -u "$APP_USER" bash <<EOF
set -e
cd "$APP_DIR/backend"
pm2 delete layhounds-api >/dev/null 2>&1 || true
pm2 start "venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001" \
          --name layhounds-api --cwd "$APP_DIR/backend"
pm2 save
EOF

# Install the systemd unit so PM2 resurrects on reboot
env PATH="$PATH:/usr/bin" pm2 startup systemd -u "$APP_USER" \
    --hp "/home/$APP_USER" >/dev/null || true
systemctl enable "pm2-$APP_USER" >/dev/null 2>&1 || true
systemctl restart "pm2-$APP_USER" >/dev/null 2>&1 || true

# ==============================================================================
step "7/8  Nginx reverse proxy"
# ==============================================================================
NGINX_CONF="/etc/nginx/sites-available/layhounds"
cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    root ${APP_DIR}/frontend/build;
    index index.html;

    # Long-cache hashed assets
    location /static/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api/ {
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    # SPA fallback
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;

    client_max_body_size 2m;
}
EOF

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/layhounds
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# ==============================================================================
step "8/8  HTTPS via Let's Encrypt"
# ==============================================================================
if [ "$SKIP_TLS" = "1" ]; then
  warn "SKIP_TLS=1 — leaving site on plain HTTP."
else
  if ! command -v certbot >/dev/null; then
    snap install --classic certbot
    ln -sf /snap/bin/certbot /usr/bin/certbot
  fi
  certbot --nginx --non-interactive --agree-tos \
          --email "$EMAIL" -d "$DOMAIN" --redirect
fi

# ==============================================================================
step "Done — verification"
# ==============================================================================
sleep 2
PROTO="https"; [ "$SKIP_TLS" = "1" ] && PROTO="http"
API_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "${PROTO}://${DOMAIN}/api/" || true)"
BF_STATUS="$(curl -s "${PROTO}://${DOMAIN}/api/betfair/status" || true)"

echo
echo -e "${BOLD}Lay-Hounds deployment complete.${NC}"
echo "  URL:              ${PROTO}://${DOMAIN}"
echo "  API /api/:        HTTP ${API_STATUS}"
echo "  Betfair status:   ${BF_STATUS}"
echo
echo "  Backend logs:     sudo -u $APP_USER pm2 logs layhounds-api"
echo "  Restart API:      sudo -u $APP_USER pm2 restart layhounds-api"
echo "  Nginx config:     $NGINX_CONF"
echo "  App dir:          $APP_DIR"
echo
if echo "$BF_STATUS" | grep -q GEO_BLOCKED; then
  warn "Betfair still reports GEO_BLOCKED — this VPS region is not UK/EU."
  warn "Move to Hetzner FSN1/NBG1, OVH UK, Linode London, or AWS eu-west-2."
else
  log "Betfair API reachable from this host."
fi
