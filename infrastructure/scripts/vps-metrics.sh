#!/usr/bin/env bash
# =============================================================================
# Mus Luxury — lightweight VPS metrics sampler.
# Writes a one-line JSON sample to /opt/luxe/logs/metrics.log every time it
# runs (invoked by luxe-metrics.timer, every 5 min). Uptime Kuma or a shell
# tail is enough to turn this into a dashboard. No agent to install.
# =============================================================================
set -euo pipefail

LOG_DIR="${LOG_DIR:-/opt/luxe/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/metrics.log"

ts=$(date -u +%FT%TZ)
load=$(awk '{print $1","$2","$3}' /proc/loadavg)
mem_total=$(awk '/MemTotal/{print $2}' /proc/meminfo)
mem_avail=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
disk_used=$(df -P / | awk 'NR==2 {print $3}')
disk_total=$(df -P / | awk 'NR==2 {print $2}')
disk_pct=$(df -P / | awk 'NR==2 {gsub("%",""); print $5}')
containers_up=$(docker ps --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')

printf '{"ts":"%s","load":"%s","mem_total_kb":%s,"mem_avail_kb":%s,"disk_used_kb":%s,"disk_total_kb":%s,"disk_pct":%s,"containers_up":%s}\n' \
  "$ts" "$load" "$mem_total" "$mem_avail" "$disk_used" "$disk_total" "$disk_pct" "$containers_up" \
  >> "$LOG_FILE"

# Trim to last 2016 lines (~7 days at 5-min cadence)
if [ "$(wc -l < "$LOG_FILE")" -gt 2016 ]; then
  tail -n 2016 "$LOG_FILE" > "$LOG_FILE.trim" && mv "$LOG_FILE.trim" "$LOG_FILE"
fi
