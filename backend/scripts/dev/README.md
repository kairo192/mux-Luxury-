# Developer tools (not used in production)

| Script | What it does |
|---|---|
| `benchmark_baseline.py`, `benchmark_post_perf.py` | Time a few public API endpoints of a running local server (before / after a performance change). |
| `run_architect_security_audit.py` | Static checklist audit of the backend source (headers, auth, SQL usage). Informative only; the real gates are the CI tests. |

Operator tools (production) stay in `backend/scripts/`: `generate_production_env.py`, `generate_secrets.py`,
`emergency_reset_owner.py`, `reset_fresh_store.py`.
