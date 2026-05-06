#!/usr/bin/env bash
# ==============================================================================
#  Lay-Lab — zero-downtime updater
# ------------------------------------------------------------------------------
#  Pulls latest code, reinstalls deps if their lockfiles changed, rebuilds the
#  React bundle, and rolls the API under PM2 — all without dropping requests.
#
#  Usage (on the VPS, as root or sudo):
#    cd /opt/laylab && sudo ./update.sh
#
#  Optional env vars:
#    APP_DIR   — install path  (default: /opt/laylab)
#    APP_USER  — file owner    (default: laylab)
#    BRANCH    — git branch    (default: current)
#    FORCE=1   — rebuild frontend + reinstall deps even if nothing changed
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+] $*${NC}"; }
warn() { echo -e "${YELLOW}[!] $*${NC}"; }
die()  { echo -e "${RED}[x] $*${NC}" >&2; exit 1; }
step() { echo -e "\n${BOLD}==> $*${NC}"; }

[ "${EUID:-$(id -u)}" -eq 0 ] || die "Run as root (or via sudo)."

APP_DIR="${APP_DIR:-/opt/laylab}"
APP_USER="${APP_USER:-laylab}"
FORCE="${FORCE:-0}"

[ -d "$APP_DIR/.git" ]    || die "$APP_DIR is not a git repo."
[ -d "$APP_DIR/backend" ] || die "$APP_DIR/backend missing."
[ -d "$APP_DIR/frontend" ]|| die "$APP_DIR/frontend missing."
id -u "$APP_USER" >/dev/null 2>&1 || die "User $APP_USER does not exist."

cd "$APP_DIR"

# ==============================================================================
step "1/5  git pull"
# ==============================================================================
sudo -u "$APP_USER" git -C "$APP_DIR" fetch --all --prune

CURRENT_BRANCH="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"
BRANCH="${BRANCH:-$CURRENT_BRANCH}"

OLD_SHA="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse HEAD)"
sudo -u "$APP_USER" git -C "$APP_DIR" checkout "$BRANCH"
sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "origin/$BRANCH"
NEW_SHA="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse HEAD)"

if [ "$OLD_SHA" = "$NEW_SHA" ] && [ "$FORCE" != "1" ]; then
  log "Already up to date ($NEW_SHA). Use FORCE=1 to rebuild anyway."
  exit 0
fi

CHANGED="$(git -C "$APP_DIR" diff --name-only "$OLD_SHA" "$NEW_SHA" 2>/dev/null || echo "ALL")"
echo "$CHANGED" | head -40

# Helper: did anything in <prefix> change?
changed() { [ "$FORCE" = "1" ] || echo "$CHANGED" | grep -q "^$1"; }

# ==============================================================================
step "2/5  Backend dependencies"
# ==============================================================================
if changed "backend/requirements.txt" || [ ! -d "$APP_DIR/backend/venv" ]; then
  log "requirements.txt changed → reinstalling"
  sudo -u "$APP_USER" bash -c "
    set -e
    cd '$APP_DIR/backend'
    [ -d venv ] || python3.11 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip wheel >/dev/null
    pip install -r requirements.txt
  "
else
  log "Backend deps unchanged — skipping pip install"
fi

# ==============================================================================
step "3/5  Frontend rebuild"
# ==============================================================================
if changed "frontend/" || [ ! -d "$APP_DIR/frontend/build" ]; then
  log "Frontend changed → yarn install + build"

  # Build into a tmp dir, then atomic-swap so Nginx never serves a half-built bundle.
  BUILD_TMP="$APP_DIR/frontend/build.new"
  BUILD_OLD="$APP_DIR/frontend/build.old"
  rm -rf "$BUILD_TMP" "$BUILD_OLD"

  sudo -u "$APP_USER" bash -c "
    set -e
    cd '$APP_DIR/frontend'
    if [ -f yarn.lock ]; then
      yarn install --frozen-lockfile
    else
      yarn install
    fi
    CI=false BUILD_PATH='$BUILD_TMP' yarn build
  "

  if [ -d "$APP_DIR/frontend/build" ]; then
    mv "$APP_DIR/frontend/build" "$BUILD_OLD"
  fi
  mv "$BUILD_TMP" "$APP_DIR/frontend/build"
  rm -rf "$BUILD_OLD"
  chown -R "$APP_USER:$APP_USER" "$APP_DIR/frontend/build"
else
  log "Frontend unchanged — skipping rebuild"
fi

# ==============================================================================
step "4/5  Roll API (zero-downtime)"
# ==============================================================================
if changed "backend/" || [ "$FORCE" = "1" ]; then
  log "Backend changed → pm2 reload (graceful)"
  # `pm2 reload` waits for in-flight requests to finish before swapping workers,
  # giving zero-downtime restarts. Falls back to `restart` if reload unavailable.
  if sudo -u "$APP_USER" pm2 reload laylab-api 2>/dev/null; then
    log "pm2 reload OK"
  else
    warn "pm2 reload failed — falling back to restart"
    sudo -u "$APP_USER" pm2 restart laylab-api
  fi
else
  log "Backend unchanged — skipping API reload"
fi

# ==============================================================================
step "5/5  Nginx reload + verify"
# ==============================================================================
nginx -t && systemctl reload nginx

DOMAIN="$(awk '/server_name/ {print $2; exit}' /etc/nginx/sites-enabled/laylab 2>/dev/null | tr -d ';')"
if [ -n "$DOMAIN" ]; then
  sleep 1
  PROTO="https"
  grep -q 'listen 443' /etc/nginx/sites-enabled/laylab 2>/dev/null || PROTO="http"
  HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "${PROTO}://${DOMAIN}/api/" || echo 000)"
  BF="$(curl -s "${PROTO}://${DOMAIN}/api/betfair/status" || echo '{}')"

  echo
  echo -e "${BOLD}Update complete.${NC}"
  echo "  ${OLD_SHA:0:7} → ${NEW_SHA:0:7}"
  echo "  URL:            ${PROTO}://${DOMAIN}"
  echo "  /api/ HTTP:     ${HTTP_CODE}"
  echo "  Betfair status: ${BF}"
  echo
  if [ "$HTTP_CODE" != "200" ]; then
    warn "API did not return 200 — check 'sudo -u $APP_USER pm2 logs laylab-api --lines 50'"
    exit 1
  fi
else
  log "Update complete (${OLD_SHA:0:7} → ${NEW_SHA:0:7})"
fi
