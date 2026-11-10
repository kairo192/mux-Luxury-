# Mus Luxury (`LUXE`) — Operational Troubleshooting & Diagnostics Guide

## 1. Quick Diagnostic Decision Tree

```text
Problem Encountered?
 ├── SSH Connection Timed Out ──────────────────► Section 2: VPS Host & Network Diagnostics
 ├── Nginx 502 Bad Gateway ─────────────────────► Section 3: API Container & Database Health
 ├── Desktop POS "Offline" Banner Stays Active ─► Section 4: POS Synchronization & Network Queue
 ├── Memory Pressure / OOM Container Kill ──────► Section 5: Memory Tuning on 2 GB VPS
 └── Cash Drawer / Thermal Receipt Not Firing ──► Section 6: POS Hardware Peripheral Troubleshooting
```

---

## 2. VPS Host & Network Diagnostics

### Symptom: `ssh: connect to host 5.196.163.6 port 22: Connection timed out`
1. **Check Octenium Control Panel:**
   - Log in to the Octenium VPS management portal.
   - Verify server power status (Running / Stopped / Suspended).
   - Check if the VPS IP `5.196.163.6` matches the provisioned interface.
2. **Reboot VPS via Control Panel:**
   - If the server kernel panicked or the interface froze, initiate a graceful reboot from the portal console.
3. **Inspect UFW / Security Group:**
   - Verify port 22 is permitted in Octenium cloud firewall rules.
   - Ensure rate limiting on SSH did not temporarily ban your IP via fail2ban.

---

## 3. Nginx 502 Bad Gateway & API Failures

### Symptom: Browser displays `502 Bad Gateway` when accessing `api.mus-luxury.com`
1. **Inspect Container Status:**
   ```bash
   docker compose ps
   ```
   If `luxe_api` is exited or restarting, check its logs:
   ```bash
   docker compose logs --tail=100 api
   ```
2. **Verify Database Health:**
   ```bash
   docker compose exec db pg_isready -U luxe_app_user -d luxe_ecommerce
   ```
3. **Inspect Python Exception Traces:**
   Look for database connection timeouts or missing environment variables (`SECRET_KEY`, `DATABASE_URL`).

---

## 4. Desktop POS Synchronization Diagnostics

### Symptom: Desktop CMS indicates "Hors ligne" even when internet is restored
1. **Check Central API Reachability:**
   Open a browser on the POS terminal and navigate to:
   `https://api.mus-luxury.com/api/v1/health`
   Expected response: `{"status": "ok", "app": "Mus Luxury (LUXE)"}`.
2. **Inspect Offline Queue in Desktop App:**
   - Click the Network Telemetry pill in the top header.
   - Verify `pending_mutations` count.
   - Click **Actualiser (↻)** to trigger an immediate delta synchronization.
3. **Check POS Local Mirror:**
   SQLite file `%APPDATA%\com.musluxury.cms\pos_mirror.sqlite3` maintains local transactions. Never delete this file while pending mutations exist.

---

## 5. Memory Pressure & OOM Containment (2 GB VPS)

### Symptom: Container killed with Exit Code 137 (Out of Memory)
1. **Check Kernel OOM Log:**
   ```bash
   dmesg -T | grep -i oom
   ```
2. **Verify Container Resource Limits:**
   Ensure `docker-compose.yml` limits are enforced (`db`: 256 MB, `api`: 256 MB, `storefront`: 32 MB, `nginx`: 64 MB).
3. **Verify Swap Activation:**
   ```bash
   free -m
   swapon --show
   ```
   If swap is 0 MB, immediately create a 2 GB swapfile:
   ```bash
   fallocate -l 2G /swapfile
   chmod 600 /swapfile
   mkswap /swapfile
   swapon /swapfile
   echo '/swapfile none swap sw 0 0' >> /etc/fstab
   ```

---

## 6. Hardware Peripheral Troubleshooting

### Receipt Printer Not Printing:
1. Verify Windows Default Printer name in `apps/desktop-cms/src/components/PrinterSettingsModal.tsx`.
2. Ensure thermal printer driver is installed in "Generic / Text Only" or vendor RAW mode.
3. Test printer paper roll orientation.

### Cash Drawer Not Opening:
1. Ensure the RJ11 cable is securely plugged from the drawer into the receipt printer DK port (not a phone jack).
2. The cash drawer kick is triggered by the receipt printer via ESC/POS command `ESC p 0 25 250`. Test printing a receipt first.
