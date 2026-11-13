# VPS preparation

Target host: 1 vCore, 2 GB RAM, 40 GB disk Ubuntu 22.04 or 24.04 LTS, root SSH.

## 0. Before you log in

Buy the VPS, point your domain's `A` record at the IP, and open the console
of your registrar in another tab — you'll need to confirm the SSL challenge
in step 5.

## 1. First SSH

```bash
ssh root@<vps-ip>
```

Change the root password immediately. Create a non-root sudo user only if you
want to administer the box by hand; the deploy pipeline uses its own `luxe`
user, which the bootstrap script creates.

## 2. Pull the repo

The bootstrap script lives in the repo, so clone it once on the VPS:

```bash
cd /root
git clone https://github.com/kairo192/mux-Luxury-.git luxe
```

## 3. Run bootstrap

```bash
cd /root/luxe
# Paste the public key of your GitHub Actions deploy private key here.
# It must be the PUBLIC half of the key you'll put in secrets.PRODUCTION_SSH_PRIVATE_KEY.
export DEPLOY_PUBLIC_KEY='ssh-ed25519 AAAA... deploy@mus-luxury'
export DOMAIN=mus-luxury.com
sudo bash infrastructure/scripts/vps-bootstrap.sh
```

The script is idempotent — re-running it on a configured host does nothing
destructive. It installs Docker, UFW, unattended-upgrades, creates the `luxe`
user, prepares `/opt/luxe/{releases,shared,logs}`, installs the nightly
backup cron, installs the systemd timer for `vps-metrics.sh`, and prints a
checklist for what you still need to do by hand.

## 4. Fill in the runtime env

```bash
sudo -u luxe install -m 0600 /dev/stdin /opt/luxe/shared/.env <<'ENV'
# ...paste the contents of infrastructure/environments/production.env.example,
# with every REPLACE_* substituted...
ENV
```

## 5. Get a TLS certificate

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot certonly --standalone \
    -d mus-luxury.com -d www.mus-luxury.com -d api.mus-luxury.com \
    --agree-tos -m contact@mus-luxury.com --non-interactive
sudo install -m 0644 /etc/letsencrypt/live/mus-luxury.com/fullchain.pem /opt/luxe/shared/nginx-ssl/
sudo install -m 0640 -o luxe -g luxe /etc/letsencrypt/live/mus-luxury.com/privkey.pem /opt/luxe/shared/nginx-ssl/
```

Renewal: certbot installs its own systemd timer. The cron that reloads nginx
after a successful renewal:

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx-container.sh >/dev/null <<'HOOK'
#!/usr/bin/env bash
set -e
cp /etc/letsencrypt/live/mus-luxury.com/fullchain.pem /opt/luxe/shared/nginx-ssl/fullchain.pem
cp /etc/letsencrypt/live/mus-luxury.com/privkey.pem   /opt/luxe/shared/nginx-ssl/privkey.pem
chown luxe:luxe /opt/luxe/shared/nginx-ssl/*.pem
su -c 'docker exec luxe_proxy nginx -s reload' luxe || true
HOOK
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx-container.sh
```

## 6. Verify SSH from GitHub

On your laptop:

```bash
ssh -i ~/.ssh/github-actions-deploy luxe@<vps-ip> 'echo ok && docker info | head -3'
```

Add the public key's fingerprint to GitHub repo **Settings → Secrets and variables → Actions** as:

- `PRODUCTION_SSH_HOST` → `<vps-ip>` or `mus-luxury.com`
- `PRODUCTION_SSH_USER` → `luxe`
- `PRODUCTION_SSH_PRIVATE_KEY` → the matching PRIVATE key, PEM-encoded

Add the corresponding variables (Settings → Variables → Actions → Variables):

- `PRODUCTION_URL` → `https://mus-luxury.com`
- `PRODUCTION_HEALTH_URL` → `https://api.mus-luxury.com/api/v1/health`

Repeat for staging (`STAGING_*`).

## 7. First deploy

Trigger `CD → Production` manually once from the Actions tab with `ref=main`.
The GitHub UI pauses at the environment approval gate; approve it and watch
the logs. First-time deploy has no previous release to roll back to, so if it
fails, SSH in, inspect `/opt/luxe/logs/deploy.log`, fix, and retry.

## 8. Optional but recommended

- **Start Uptime Kuma** per `infrastructure/monitoring/README.md`.
- **Off-site encrypted backups** — set `S3_BACKUP_ENABLED=true` and the four
  `S3_*` vars. Point to an S3-compatible bucket outside Algeria so the entire
  VPS loss is recoverable.
- **Fail2ban** is installed by the bootstrap. Its SSH jail is active by
  default.
- **Swap** — a 2 GB VPS should have a 1 GB swap file to survive a brief RAM
  spike during docker build:

  ```bash
  sudo fallocate -l 1G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```
