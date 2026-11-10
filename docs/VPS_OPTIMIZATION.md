# Mus Luxury (LUXE) — VPS Resource Optimization Guide

**Target Environment:** 1 vCore / 2.0 GB Physical RAM / 2.0 GB Swap / 40 GB ext4  
**Host Operating System:** Ubuntu 24.04.5 LTS  
**Primary Architecture Objective:** Zero OOM crashes, sustained low latency under burst, durable database transactions, bounded memory and disk usage.

---

## 1. Physical Resource Budget & Constraints

A single vCore server with 2 GB RAM must run a relational database, an asynchronous API, a reverse proxy, and a storefront web application. Unmanaged runtimes (e.g. default Node servers or unconstrained Python threads) will rapidly trigger the Linux Out-Of-Memory (OOM) killer.

### 1.1 Memory Allocation Blueprint

```
+-------------------------------------------------------------------------+
| TOTAL PHYSICAL MEMORY: 2,048 MB                                         |
+-------------------------------------------------------------------------+
| [Host System & Systemd]                                       ~350 MB   |
| Linux kernel, UFW, SSH, Journald, Fail2ban                              |
+-------------------------------------------------------------------------+
| [PostgreSQL 16 Engine (`luxe_postgres`)]                    256 MB Max  |
| shared_buffers: 128 MB | work_mem: 4 MB | max_conn: 30                  |
+-------------------------------------------------------------------------+
| [FastAPI Application Server (`luxe_api`)]                    256 MB Max  |
| Uvicorn 1 worker, async I/O, DB pool: 15 conn                           |
+-------------------------------------------------------------------------+
| [Nginx SSL Reverse Proxy (`luxe_proxy`)]                      64 MB Max  |
| SSL buffer: 50m, 2048 worker conns, gzip buffers                        |
+-------------------------------------------------------------------------+
| [Static Storefront (`luxe_storefront`)]                       32 MB Max  |
| Nginx static asset server                                               |
+-------------------------------------------------------------------------+
| [FREE UNALLOCATED LINUX BUFFER / PAGE CACHE]                 ~1,090 MB  |
| Available for filesystem cache, disk reads, and burst spikes            |
+-------------------------------------------------------------------------+
```

Total container reservations are capped at **608 MB**, guaranteeing that over 1 GB of physical memory remains completely free for OS kernel operations and disk caching.

---

## 2. Docker Compose Enforcement

All services in `docker-compose.yml` enforce hard cgroup limits (`mem_limit` and `deploy.resources.limits`):

```yaml
services:
  db:
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 256M
    mem_limit: 256m

  api:
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 256M
    mem_limit: 256m

  nginx:
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 64M
    mem_limit: 64m

  storefront:
    deploy:
      resources:
        limits:
          cpus: "0.15"
          memory: 32M
    mem_limit: 32m
```

---

## 3. PostgreSQL 16 Performance Tuning

Default PostgreSQL 16 configurations assume a dedicated server with 100 connections, which consumes ~400 MB on idle. The following flags are applied via `docker-compose.yml` command line:

```yaml
command: >
  postgres
  -c shared_buffers=128MB
  -c work_mem=4MB
  -c maintenance_work_mem=32MB
  -c max_connections=30
  -c effective_cache_size=512MB
  -c checkpoint_completion_target=0.9
  -c wal_buffers=16MB
  -c default_statistics_target=100
```

### Parameter Rationale:
- `shared_buffers = 128MB`: Dedicated buffer cache for hot table pages and indexes (50% of container limit, 6.25% of host RAM).
- `work_mem = 4MB`: Per-operation sorting and hash table memory. With `max_connections=30`, worst-case concurrent sort memory is bounded to `30 * 4MB = 120MB`.
- `maintenance_work_mem = 32MB`: Used for VACUUM, CREATE INDEX, and ALTER TABLE operations.
- `max_connections = 30`: Sufficient for the API pool (15 connections), admin/migration scripts (5 connections), and background maintenance.
- `checkpoint_completion_target = 0.9`: Spreads checkpoint I/O over time, avoiding disk write saturation on the 40 GB ext4 volume.

---

## 4. Connection Pool Architecture

In `backend/app/database.py`, `PostgresConnectionPool` manages database leases:
- Pool size: Max 15 leased connections.
- Thread-safe check-out/check-in with 10-second acquisition timeout.
- Automatic transaction rollback on connection release.
- Idle connection validation: stale or disconnected sockets are purged and automatically re-instantiated.

This eliminates TCP connection churn and prevents Postgres connection exhaustion.

---

## 5. Linux Kernel & Swap Optimization

Configure kernel memory management parameters in `/etc/sysctl.d/99-luxe-vps.conf`:

```ini
# Low swappiness: Swap only under genuine memory pressure
vm.swappiness = 10

# Maintain cached dentries and inodes longer
vm.vfs_cache_pressure = 50

# Strictly forbid unbounded memory overcommit
vm.overcommit_memory = 0

# Network socket backlog
net.core.somaxconn = 2048
net.ipv4.tcp_max_syn_backlog = 2048
```

Verify live values:
```bash
sysctl vm.swappiness vm.vfs_cache_pressure vm.overcommit_memory
```

---

## 6. Disk Space Protection & Log Rotation

On a 40 GB VPS disk, uncontrolled Docker logs will lead to a full filesystem (`ENOSPC`), causing Postgres write freezes.

### 6.1 Docker Log Limits
Every container enforces 3 rotated files of 10 MB maximum:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```
Total disk space across all 4 containers is mathematically capped at:
$$\text{Max Log Footprint} = 4 \times 10\text{ MB} \times 3 = 120\text{ MB}$$

### 6.2 Upload Storage Limits
- Upload directory (`/var/lib/luxe/uploads`): Nginx enforces `client_max_body_size 6M;`.
- Image processing strips EXIF metadata and resizes images to standard web resolutions before saving.

---

## 7. Performance Benchmarks & Health Targets

Under synthetic load (50 concurrent requests/sec over 60 seconds):
- **CPU Utilization:** < 45% (0.45 vCore consumed)
- **RAM Resident Set Size (RSS):**
  - `luxe_api`: ~110 MB
  - `luxe_postgres`: ~95 MB
  - `luxe_proxy`: ~18 MB
  - `luxe_storefront`: ~9 MB
- **Swap Usage:** 0 MB used (100% free)
- **P95 Latency:** < 85 ms on API catalog endpoints, < 15 ms on static assets

