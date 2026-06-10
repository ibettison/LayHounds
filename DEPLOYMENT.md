# LayHounds Public App Deployment Guide

This guide deploys the public LayHounds customer app on a UK or EU VPS.

The public app includes the live Betfair system, simulator, and customer licence
activation. Licence issuing and payment handling are not part of the public
download. Paper-Live and Live modes require a licence key and licence server URL
provided after purchase.

> Betfair geo-blocks API traffic from many non-UK/EU locations. If you want
> Paper-Live or Live mode to work reliably, host the app on a UK or EU server.

---

## 1. What You Need

| Item | Recommended | Notes |
|---|---|---|
| UK/EU VPS | Ubuntu VPS with 2 GB RAM | UK or EU regions work best for Betfair API access. |
| OS | Ubuntu 24.04 LTS or 22.04 LTS | The installer supports both. |
| Domain | Any domain or subdomain | Required for clean HTTPS access. |
| Betfair credentials | App Key, username, password | Created at developer.betfair.com. Never commit these. |
| Licence details | Key plus `LICENCE_SERVER_URL` | Supplied after purchase when going live. |

Need a VPS? This referral link can be used to create a UK VPS suitable for
LayHounds:

[Launch a Fasthosts VPS](https://www.fasthosts.co.uk/referral?referral=37u6fp7gtbgc9n)

Choose Ubuntu 22.04 or 24.04, with at least 2 GB RAM where possible.

---

## 2. Public App Layout

```text
UK/EU VPS
  Nginx :443
    /        -> React frontend build
    /api/*   -> FastAPI on 127.0.0.1:8001

  FastAPI
    -> MongoDB database: layhounds_public
    -> Betfair API
    -> External licence server URL
```

Default public deployment names:

| Component | Value |
|---|---|
| App directory | `/opt/layhounds-public` |
| API port | `8001` |
| PM2 process | `layhounds-public-api` |
| Nginx site | `layhounds-public` |
| Mongo database | `layhounds_public` |

---

## 3. Fork The Public Repository

Before deploying, create your own GitHub copy of the public LayHounds
repository. This is called a fork. Your fork is the repository your VPS will
pull from during install and future updates.

1. Sign in to GitHub.
2. Open the LayHounds public repository page.
3. Click **Fork** in the top-right of the page.
4. Choose your own GitHub account as the owner.
5. Keep the repository name, or rename it if preferred.
6. Leave **Copy the main branch only** ticked unless you need other branches.
7. Click **Create fork**.

Your fork URL will look like this:

```text
https://github.com/your-username/LayHounds.git
```

Use that fork URL as the `REPO` value in the install command below.

The fork must be public for the one-command `curl` install to work without
GitHub authentication. If GitHub shows `404` for the raw `deploy.sh` URL, check
that the repository is public, the branch name is correct, and `deploy.sh` has
been pushed to that branch.

---

## 4. One-Command Public Install

On a fresh Ubuntu VPS, SSH in as root or a sudo-capable user and run:

```bash
curl -fsSL https://raw.githubusercontent.com/your-username/LayHounds/main/deploy.sh \
  | sudo \
      DOMAIN=app.example.com \
      EMAIL=you@example.com \
      APP_DIR=/opt/layhounds-public \
      REPO=https://github.com/your-username/LayHounds.git \
      LICENCE_SERVER_URL=https://your-licence-server.example \
      bash
```

Replace:

| Placeholder | Meaning |
|---|---|
| `your-username` | Your GitHub username or organisation. |
| `LayHounds` | The name of your forked repository if you renamed it. |
| `app.example.com` | The domain pointed at the VPS. |
| `you@example.com` | Email used by Let's Encrypt. |
| `LICENCE_SERVER_URL` | The licence server URL supplied with the licence setup. |

Do not include angle brackets such as `<you>` or `<public-repo>` in the real
command. Those were placeholders. For example, if your GitHub username is
`jbloggs` and your fork is called `LayHounds`, the first URL should be:

```text
https://raw.githubusercontent.com/jbloggs/LayHounds/main/deploy.sh
```

If that URL gives a `404`, check whether your repository default branch is
called `master` instead of `main`. In that case, use:

```text
https://raw.githubusercontent.com/jbloggs/LayHounds/master/deploy.sh
```

You can test the raw script URL in a browser first. If the browser also shows
`404`, the username, repository name, branch name, or file path is wrong.

GitHub also returns `404` when the repository is private. For public customer
installs, make the deployment repository public first or publish the customer
version to a separate public repository.

The installer will prompt for the licence server URL and Betfair credentials
when needed. These prompts work when using `curl | sudo ... bash` because the
script reads from the VPS terminal. For non-interactive installs, pass
`LICENCE_SERVER_URL`, `BETFAIR_APP_KEY`, `BETFAIR_USERNAME`, and
`BETFAIR_PASSWORD` in the command. The installer then installs system packages,
MongoDB, Node/Yarn, Python dependencies, the React build, PM2, Nginx, and HTTPS
certificates.

If you have already cloned the repository on the VPS, you can run the wrapper:

```bash
cd ~/layhounds-public
sudo \
  DOMAIN=app.example.com \
  EMAIL=you@example.com \
  APP_DIR=/opt/layhounds-public \
  LICENCE_SERVER_URL=https://your-licence-server.example \
  ./install.sh
```

The wrapper copies that checkout into `/opt/layhounds-public` and records the
source path in `/opt/layhounds-public/.source-dir`. Keep the original
`~/layhounds-public` clone on the VPS so future updates can pull from it.

---

## 5. Environment Files

The public backend environment lives on the server at:

```text
/opt/layhounds-public/backend/.env
```

Typical values:

```bash
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=layhounds_public
CORS_ORIGINS=https://app.example.com

BETFAIR_APP_KEY=<your-betfair-app-key>
BETFAIR_USERNAME=<your-betfair-username>
BETFAIR_PASSWORD=<your-betfair-password>

LICENCE_SERVER_URL=https://your-licence-server.example
```

The public frontend environment lives at:

```text
/opt/layhounds-public/frontend/.env
```

Typical value:

```bash
REACT_APP_BACKEND_URL=https://app.example.com
```

Never commit real Betfair credentials, licence server secrets, or customer
licence keys to GitHub. Keep them only in server-side `.env` files.

---

## 6. Manual Deployment

Use this only if you do not want the installer to do the setup.

Install the main packages:

```bash
sudo apt update
sudo apt -y upgrade
sudo apt install -y nginx git curl gnupg ufw python3-venv python3-pip
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
sudo npm install -g yarn pm2
sudo timedatectl set-timezone Europe/London
```

Install MongoDB using the official MongoDB instructions for your Ubuntu version,
then enable it:

```bash
sudo systemctl enable --now mongod
```

Clone the public repo:

```bash
cd ~
git clone https://github.com/<you>/<public-repo>.git layhounds-public
cd layhounds-public
```

Install the backend:

```bash
cd ~/layhounds-public/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create `backend/.env` using the public values shown above, then:

```bash
chmod 600 .env
pm2 start "venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001" \
  --name layhounds-public-api \
  --cwd ~/layhounds-public/backend
pm2 save
pm2 startup systemd -u $USER --hp $HOME
```

Build the frontend:

```bash
cd ~/layhounds-public/frontend
printf "REACT_APP_BACKEND_URL=https://app.example.com\n" > .env
yarn install
yarn build
```

Create `/etc/nginx/sites-available/layhounds-public`:

```nginx
server {
    listen 80;
    server_name app.example.com;

    root /home/ubuntu/layhounds-public/frontend/build;
    index index.html;

    location /api/ {
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
}
```

Enable Nginx and HTTPS:

```bash
sudo ln -s /etc/nginx/sites-available/layhounds-public /etc/nginx/sites-enabled/layhounds-public
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
sudo certbot --nginx -d app.example.com
```

---

## 7. Verify The Install

From the VPS:

```bash
curl -s http://127.0.0.1:8001/api/
curl -s http://127.0.0.1:8001/api/betfair/status
curl -s http://127.0.0.1:8001/api/licence/diag | python3 -m json.tool
```

In the browser:

| Check | Expected |
|---|---|
| App loads at your domain | React app opens without console errors. |
| Betfair status | Shows configured and logged in. |
| Licence panel | Accepts a valid purchased licence key. |
| Simulator mode | Works without a live licence. |
| Paper-Live or Live mode | Unlocks only after licence activation. |

---

## 8. Updating The Public App

After pushing changes to the public GitHub repo, run:

```bash
cd ~/layhounds-public
sudo APP_DIR=/opt/layhounds-public ./update.sh
```

If your clone and runtime are the same directory:

```bash
cd /opt/layhounds-public
sudo APP_DIR=/opt/layhounds-public ./update.sh
```

If `/opt/layhounds-public` is a runtime copy rather than a Git checkout,
`update.sh` reads `.source-dir`, pulls updates in the original clone, then
copies the updated source back into `/opt`.

Useful options:

```bash
sudo APP_DIR=/opt/layhounds-public FORCE=1 ./update.sh
sudo APP_DIR=/opt/layhounds-public BRANCH=staging ./update.sh
sudo APP_DIR=/opt/layhounds-public SKIP_HEALTH=1 ./update.sh
```

The updater keeps server `.env` files intact, rebuilds the frontend when needed,
updates Python dependencies when `requirements.txt` changes, reloads
`layhounds-public-api`, reloads Nginx, and rolls back if the health check fails.

For public installs, the update process excludes private-only files such as the
licence server implementation, private app seed files, and licensing-only
requirements.

---

## 9. Hardening Checklist

| Concern | Fix |
|---|---|
| Credentials in GitHub | Keep Betfair credentials and licence details in server `.env` files only. |
| MongoDB exposure | Keep MongoDB bound to `127.0.0.1`; verify with `ss -lntp`. |
| Environment permissions | Run `chmod 600 /opt/layhounds-public/backend/.env`. |
| Live liability | Keep the liability cap low until you have confirmed live placement behaviour. |
| Logs | Use `pm2 logs layhounds-public-api` and `sudo journalctl -u nginx`. |
| Backups | Add `mongodump --db=layhounds_public --out=/backups/$(date +%F)` to cron. |

---

## 10. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Could not reach licence server` | `LICENCE_SERVER_URL` is wrong or the licence host is unavailable. | Check `/api/licence/diag`, confirm the URL supplied with the purchase, and retry. |
| `Licence key not found` | The key has not been issued or was typed incorrectly. | Re-enter the key exactly as supplied, then contact the licence provider if it still fails. |
| `Live Unlock required` | Paper-Live or Live mode was started before licence activation. | Activate the licence or use Simulator mode. |
| `GEO_BLOCKED` | VPS is outside a Betfair-supported region. | Move to a confirmed UK/EU VPS region. |
| `502 Bad Gateway` | API process is stopped or Nginx is pointing at the wrong port. | Run `pm2 status`, `pm2 logs layhounds-public-api`, and confirm port `8001`. |
| Betfair login fails | Credentials are wrong or shell-special characters were not quoted in `.env`. | Re-enter credentials carefully and quote values containing `$`, `[`, `]`, or spaces. |
| CORS errors | `CORS_ORIGINS` does not match the site URL. | Set `CORS_ORIGINS=https://app.example.com` and reload the API. |

---

## 11. Cost Estimate

| Item | Low | Mid | High |
|---|---|---|---|
| VPS | GBP 4-6/mo | GBP 6-10/mo | GBP 13+/mo |
| Domain | Around GBP 8-12/yr | Same | Same |
| Backups | GBP 1-3/mo | Same | Provider-dependent |

Delayed-data Betfair App Keys are free. Betfair may charge separately for
live-data access depending on the account/API setup.

---

_Last updated: 2026-06-09_
