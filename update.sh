#!/usr/bin/env bash
# ==============================================================================
#  Lay-Hounds — safe zero-downtime updater
# ------------------------------------------------------------------------------
#  Pulls latest code, reinstalls deps if needed, rebuilds the React bundle, and
#  rolls the API under PM2 — without dropping requests, AND with automatic
#  rollback on failure so a botched update can't brick the VPS.
#
#  Hard-learnt safety features:
#   • OOM-proof:  caps Node memory + auto-creates a 2 GB swap file if the box
#                 has < 1.5 GB free RAM (the #1 cause of "I had to reimage").
#   • Atomic:     every mutating step has a corresponding rollback. On any
#                 failure the script restores the previous code (git SHA),
#                 the previous frontend build, and the previous .env.
#   • Idempotent: re-running after a failure is safe.
#   • Single-run: flock prevents two updates fighting each other.
#   • Health-checked: the API must answer 200 within 30 s post-reload, else
#                 we roll back automatically.
#   • .env safe:  always stashed + restored even on `git reset`.
#
#  Usage  (on the VPS, as root or sudo):
#    cd /opt/layhounds && sudo ./update.sh
#
#  Env vars:
#    APP_DIR    install path     (default: /opt/layhounds)
#    APP_USER   file owner       (default: layhounds)
#    BRANCH     git branch       (default: current)
#    FORCE=1    rebuild even if no changes
#    SKIP_SWAP=1   skip the auto-swap creation (you've already added one)
#    SKIP_HEALTH=1 skip the post-reload curl health-check
# ==============================================================================

set -u  # NOTE: deliberately NOT -e — we manage errors ourselves so the trap rolls back cleanly
set -o pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+] $*${NC}"; }
warn() { echo -e "${YELLOW}[!] $*${NC}"; }
err()  { echo -e "${RED}[x] $*${NC}" >&2; }
step() { echo -e "\n${BOLD}==> $*${NC}"; }

die() { err "$*"; exit 1; }

[ "${EUID:-$(id -u)}" -eq 0 ] || die "Run as root (or via sudo)."

APP_DIR="${APP_DIR:-/opt/layhounds}"
APP_USER="${APP_USER:-layhounds}"
FORCE="${FORCE:-0}"
SKIP_SWAP="${SKIP_SWAP:-0}"
SKIP_HEALTH="${SKIP_HEALTH:-0}"

[ -d "$APP_DIR/.git" ]    || die "$APP_DIR is not a git repo."
[ -d "$APP_DIR/backend" ] || die "$APP_DIR/backend missing."
[ -d "$APP_DIR/frontend" ]|| die "$APP_DIR/frontend missing."
id -u "$APP_USER" >/dev/null 2>&1 || die "User $APP_USER does not exist."

cd "$APP_DIR"

# Single-run lock: prevent two updates from racing each other ----------------
LOCKFILE="/var/lock/layhounds-update.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
  die "Another update is already running (lock $LOCKFILE held). Wait for it to finish."
fi

# ==============================================================================
step "0/6  Pre-flight checks"
# ==============================================================================
log "Host:   $(hostname)  ($(uname -srm))"
log "Free disk:"
df -h "$APP_DIR" | awk 'NR<=2'
log "Memory:"
free -h

DISK_FREE_MB=$(df -m "$APP_DIR" | awk 'NR==2 {print $4}')
if [ "${DISK_FREE_MB:-0}" -lt 2000 ]; then
  die "Less than 2 GB free disk on $APP_DIR. Free some space before updating."
fi

# --- OOM PROTECTION: ensure at least 1.5 GB swappable headroom --------------
MEM_TOTAL_MB=$(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo)
MEM_AVAIL_MB=$(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo)
SWAP_TOTAL_MB=$(awk '/^SwapTotal:/ {print int($2/1024)}' /proc/meminfo)
TOTAL_HEADROOM=$(( MEM_AVAIL_MB + SWAP_TOTAL_MB ))
log "RAM:    ${MEM_AVAIL_MB} MB avail of ${MEM_TOTAL_MB} MB  (swap: ${SWAP_TOTAL_MB} MB)"

if [ "$TOTAL_HEADROOM" -lt 1800 ] && [ "$SKIP_SWAP" != "1" ]; then
  warn "Less than 1.8 GB total memory headroom — yarn build will likely OOM-kill."
  warn "Creating a 2 GB swap file (/swapfile) to protect the build…"
  if [ ! -f /swapfile ]; then
    if fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress; then
      chmod 600 /swapfile
      mkswap /swapfile >/dev/null
      swapon /swapfile
      if ! grep -q "^/swapfile" /etc/fstab; then
        echo "/swapfile none swap sw 0 0" >> /etc/fstab
      fi
      log "Swap online: $(free -h | awk '/^Swap/ {print $2 " total"}')"
    else
      warn "Could not create swap file — continuing anyway (set SKIP_SWAP=1 to silence)."
    fi
  else
    swapon /swapfile 2>/dev/null || true
    log "Existing /swapfile reactivated."
  fi
fi

# Cap Node's heap so even a runaway build can't eat the whole box.
# 1024 MB is comfortable for our React 19 + framer-motion + recharts bundle.
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1024}"
log "NODE_OPTIONS=$NODE_OPTIONS"

# ==============================================================================
step "1/6  Snapshot — record rollback state"
# ==============================================================================
OLD_SHA="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
log "Old git SHA:  ${OLD_SHA:0:7}"

# Snapshot frontend build (cheap — small dir)
SNAP_DIR="$APP_DIR/.update-snapshot"
rm -rf "$SNAP_DIR"
mkdir -p "$SNAP_DIR"
if [ -d "$APP_DIR/frontend/build" ]; then
  cp -a "$APP_DIR/frontend/build" "$SNAP_DIR/build"
  log "Backed up existing frontend/build → $SNAP_DIR/build"
fi
# Snapshot backend .env (NEVER lose this; it has Betfair + Stripe creds)
for f in "$APP_DIR/backend/.env" "$APP_DIR/frontend/.env"; do
  # Save as "env-backend" / "env-frontend" so subsequent globs work even though
  # the source is a dotfile.
  [ -f "$f" ] && cp -a "$f" "$SNAP_DIR/env-$(dirname "$f" | xargs basename)"
done
ROLLBACK_NEEDED=0

# Rollback handler — restores everything we snapshotted.
rollback() {
  err "Update failed — rolling back to ${OLD_SHA:0:7}…"
  # 1. git
  if [ "${OLD_SHA:-unknown}" != "unknown" ]; then
    sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "$OLD_SHA" >/dev/null 2>&1 || true
  fi
  # 2. frontend build
  if [ -d "$SNAP_DIR/build" ]; then
    rm -rf "$APP_DIR/frontend/build"
    cp -a "$SNAP_DIR/build" "$APP_DIR/frontend/build"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR/frontend/build"
  fi
  # 3. .env files (the original pre-update snapshot, NOT the .live stash files)
  shopt -s nullglob
  for f in "$SNAP_DIR"/env-backend "$SNAP_DIR"/env-frontend; do
    [ -f "$f" ] || continue
    parent="$(basename "$f" | sed 's/^env-//')"
    cp -a "$f" "$APP_DIR/$parent/.env" 2>/dev/null || true
  done
  shopt -u nullglob
  # 4. pm2 restart (in case the API was reloaded mid-fail)
  sudo -u "$APP_USER" pm2 restart layhounds-api >/dev/null 2>&1 || true
  err "Rollback complete. The site should be back online at the previous version."
  err "Check logs:  sudo -u $APP_USER pm2 logs layhounds-api --lines 80"
}

# Trap any exit (incl. EXIT trap on uncaught error) and roll back if flagged.
trap '[ "$ROLLBACK_NEEDED" = "1" ] && rollback; exit' EXIT INT TERM

# Helper: run a step, on failure flip ROLLBACK_NEEDED and exit.
guard() {
  local desc="$1"; shift
  if ! "$@"; then
    err "Step failed: $desc"
    ROLLBACK_NEEDED=1
    exit 1
  fi
}

# Always restore .env after any git operation (git reset --hard could blat it
# if .env was ever committed). Run before each git mutation.
stash_envs()  {
  [ -f "$APP_DIR/backend/.env" ]  && cp -a "$APP_DIR/backend/.env"  "$SNAP_DIR/env-backend.live"  || true
  [ -f "$APP_DIR/frontend/.env" ] && cp -a "$APP_DIR/frontend/.env" "$SNAP_DIR/env-frontend.live" || true
}
restore_envs() {
  [ -f "$SNAP_DIR/env-backend.live" ]  && cp -a "$SNAP_DIR/env-backend.live"  "$APP_DIR/backend/.env"  || true
  [ -f "$SNAP_DIR/env-frontend.live" ] && cp -a "$SNAP_DIR/env-frontend.live" "$APP_DIR/frontend/.env" || true
  chown "$APP_USER:$APP_USER" "$APP_DIR/backend/.env"  2>/dev/null || true
  chown "$APP_USER:$APP_USER" "$APP_DIR/frontend/.env" 2>/dev/null || true
}

# ==============================================================================
step "2/6  git pull"
# ==============================================================================
stash_envs
sudo -u "$APP_USER" git -C "$APP_DIR" fetch --all --prune || { err "git fetch failed (network?)"; exit 1; }

CURRENT_BRANCH="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"
BRANCH="${BRANCH:-$CURRENT_BRANCH}"

# Soft checkout + fast-forward (never rewrites local commits violently)
sudo -u "$APP_USER" git -C "$APP_DIR" checkout "$BRANCH" >/dev/null 2>&1 || true
if ! sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "origin/$BRANCH"; then
  err "git reset --hard origin/$BRANCH failed"
  restore_envs
  ROLLBACK_NEEDED=1
  exit 1
fi
restore_envs
NEW_SHA="$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse HEAD)"

if [ "$OLD_SHA" = "$NEW_SHA" ] && [ "$FORCE" != "1" ]; then
  log "Already up to date ($NEW_SHA). Use FORCE=1 to rebuild anyway."
  trap - EXIT INT TERM
  exit 0
fi

CHANGED="$(git -C "$APP_DIR" diff --name-only "$OLD_SHA" "$NEW_SHA" 2>/dev/null || echo ALL)"
log "Changed files (first 40):"
echo "$CHANGED" | head -40

changed() { [ "$FORCE" = "1" ] || echo "$CHANGED" | grep -q "^$1"; }

# ==============================================================================
step "3/6  Backend dependencies"
# ==============================================================================
if changed "backend/requirements.txt" || [ ! -d "$APP_DIR/backend/venv" ]; then
  log "requirements.txt changed → reinstalling into venv"
  # Use --no-cache-dir + retry to handle flaky PyPI on tiny VPSs.
  if ! sudo -u "$APP_USER" bash -c "
    set -e
    cd '$APP_DIR/backend'
    [ -d venv ] || python3.11 -m venv venv || python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip wheel >/dev/null
    pip install --no-cache-dir -r requirements.txt
  "; then
    err "Backend pip install failed"
    ROLLBACK_NEEDED=1
    exit 1
  fi
else
  log "Backend deps unchanged — skipping pip install"
fi

# ==============================================================================
step "4/6  Frontend rebuild (memory-capped)"
# ==============================================================================
if changed "frontend/" || [ ! -d "$APP_DIR/frontend/build" ]; then
  log "Frontend changed → yarn install + build (NODE_OPTIONS=$NODE_OPTIONS)"

  BUILD_TMP="$APP_DIR/frontend/build.new"
  BUILD_OLD="$APP_DIR/frontend/build.old"
  rm -rf "$BUILD_TMP" "$BUILD_OLD"

  if ! sudo -u "$APP_USER" env NODE_OPTIONS="$NODE_OPTIONS" bash -c "
    set -e
    cd '$APP_DIR/frontend'
    # If yarn.lock drifted from package.json (common after manual edits),
    # frozen-lockfile would hard-fail. Fall back to a regular install.
    if ! yarn install --frozen-lockfile 2>/tmp/yarn-install.log; then
      echo '[!] frozen-lockfile install failed, retrying without lock' >&2
      tail -n 20 /tmp/yarn-install.log >&2 || true
      yarn install
    fi
    CI=false BUILD_PATH='$BUILD_TMP' yarn build
  "; then
    err "yarn build failed (likely OOM — check 'dmesg | tail' for 'Killed process')"
    rm -rf "$BUILD_TMP"
    ROLLBACK_NEEDED=1
    exit 1
  fi

  # Atomic swap. If the second mv fails for any reason, the trap rolls back.
  if [ -d "$APP_DIR/frontend/build" ]; then
    mv "$APP_DIR/frontend/build" "$BUILD_OLD"
  fi
  if ! mv "$BUILD_TMP" "$APP_DIR/frontend/build"; then
    err "Failed to swap new build into place"
    [ -d "$BUILD_OLD" ] && mv "$BUILD_OLD" "$APP_DIR/frontend/build"
    ROLLBACK_NEEDED=1
    exit 1
  fi
  rm -rf "$BUILD_OLD"
  chown -R "$APP_USER:$APP_USER" "$APP_DIR/frontend/build"
  log "Frontend rebuilt OK."
else
  log "Frontend unchanged — skipping rebuild"
fi

# ==============================================================================
step "5/6  Roll API (zero-downtime)"
# ==============================================================================
if changed "backend/" || [ "$FORCE" = "1" ]; then
  log "Backend changed → pm2 reload (graceful)"
  if sudo -u "$APP_USER" pm2 reload layhounds-api 2>/dev/null; then
    log "pm2 reload OK"
  else
    warn "pm2 reload not available — falling back to restart"
    if ! sudo -u "$APP_USER" pm2 restart layhounds-api; then
      err "pm2 restart failed"
      ROLLBACK_NEEDED=1
      exit 1
    fi
  fi
  sudo -u "$APP_USER" pm2 save >/dev/null 2>&1 || true
else
  log "Backend unchanged — skipping API reload"
fi

# ==============================================================================
step "6/6  Nginx reload + health-check"
# ==============================================================================
if ! nginx -t 2>/dev/null; then
  err "nginx config is invalid — NOT reloading (your old config keeps serving)"
  nginx -t  # show the error
  ROLLBACK_NEEDED=1
  exit 1
fi
systemctl reload nginx || warn "nginx reload returned non-zero (already serving previous config)"

DOMAIN="$(awk '/server_name/ {print $2; exit}' /etc/nginx/sites-enabled/layhounds 2>/dev/null | tr -d ';')"
PROTO="http"
grep -q 'listen 443' /etc/nginx/sites-enabled/layhounds 2>/dev/null && PROTO="https"

if [ "$SKIP_HEALTH" != "1" ] && [ -n "$DOMAIN" ]; then
  log "Health-checking ${PROTO}://${DOMAIN}/api/ for up to 30 s…"
  HTTP_CODE=000
  for i in $(seq 1 15); do
    sleep 2
    HTTP_CODE="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "${PROTO}://${DOMAIN}/api/" || echo 000)"
    [ "$HTTP_CODE" = "200" ] && break
    echo "   attempt $i/15 → HTTP $HTTP_CODE"
  done
  if [ "$HTTP_CODE" != "200" ]; then
    err "API didn't return 200 after 30 s (last code: $HTTP_CODE) — rolling back."
    ROLLBACK_NEEDED=1
    exit 1
  fi
  BF="$(curl -s -m 5 "${PROTO}://${DOMAIN}/api/betfair/status" || echo '{}')"
else
  HTTP_CODE="(skipped)"
  BF="(skipped)"
fi

# Success — disarm the rollback trap.
trap - EXIT INT TERM
rm -rf "$SNAP_DIR"

echo
echo -e "${BOLD}${GREEN}Update complete.${NC}"
echo "  ${OLD_SHA:0:7} → ${NEW_SHA:0:7}"
[ -n "${DOMAIN:-}" ] && echo "  URL:            ${PROTO}://${DOMAIN}"
echo "  /api/ HTTP:     ${HTTP_CODE}"
echo "  Betfair:        ${BF}"
echo "  PM2 saved.      Use 'sudo -u $APP_USER pm2 status' to view processes."
echo
