# Monitoring

Lightweight-first: Uptime Kuma + the `vps-metrics.sh` sampler already installed
by `vps-bootstrap.sh` are enough for a single-VPS retail stack. No Prometheus
or Grafana — those would double the VPS's RAM footprint.

## What watches what

| Signal              | Where                                               | Who reads it      |
| ------------------- | --------------------------------------------------- | ----------------- |
| Storefront up       | Uptime Kuma HTTPS monitor, `https://mus-luxury.com/`  | Owner's phone     |
| API up              | Uptime Kuma HTTPS monitor, `/api/v1/health`         | Owner's phone     |
| POS compat          | Uptime Kuma keyword monitor, `/api/v1/pos/compat`   | Owner's phone     |
| VPS load / mem / disk | `vps-metrics.sh` → `/opt/luxe/logs/metrics.log`   | Uptime Kuma Push  |
| Backups succeeded   | cron → `/opt/luxe/logs/backup.log` (last line)      | Uptime Kuma Push  |
| Container restarts  | `docker events` on the VPS                          | Operator (manual) |

## First-time setup

```bash
cd /opt/luxe/current/infrastructure/monitoring
docker compose -f docker-compose.monitoring.yml up -d
# Visit http://<vps-ip>:3001 through an SSH tunnel (never open 3001 publicly):
#    ssh -L 3001:127.0.0.1:3001 luxe@<vps-ip>
# Create the admin, then configure the monitors listed above.
```

## Push monitors (VPS → Kuma)

`vps-metrics.sh` can push its heartbeat to Kuma by adding a line at the end:

```bash
curl -fsS --max-time 5 "http://127.0.0.1:3001/api/push/<TOKEN>?status=up&msg=OK" >/dev/null || true
```

Replace `<TOKEN>` with the push URL Kuma generates per monitor.

## Alerting

Configure in Kuma → Settings → Notifications. Suggested channels:

- **Telegram bot** — fastest, free, phone-friendly (built into Kuma: bot token + chat id).
- **Email** — fallback; the mail account is entered in Kuma itself, the shop has no e-mail settings.

Keep alert thresholds conservative on a single-VPS stack: a 2-minute outage is
rarely worth waking someone up for; a 10-minute one definitely is.
