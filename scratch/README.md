# `scratch/` — do not commit generated secrets

Default output directory for files that are never allowed on GitHub:

| File                    | Written by                                        |
| ----------------------- | ------------------------------------------------- |
| `production.env`        | `backend/scripts/generate_production_env.py`      |
| `staging.env`           | same, with `--out scratch/staging.env`            |
| Any other `*.env`       | caught by the catch-all in `.gitignore`           |

The `.env` files in this directory are `.gitignore`'d by the `*.env`
catch-all. Existing Python helper scripts (`patch_*.py`, `build_*.py`,
etc.) stay tracked under `scratch/*`.

After you've copied a `.env` file to the VPS (see the generator's
final output), you can safely `rm` the local copy — the generator is
deterministic from new entropy, not from any stored seed.
