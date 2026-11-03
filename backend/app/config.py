import os
from typing import Dict

def load_dotenv_files() -> Dict[str, str]:
    """
    Zero-dependency .env file loader that reads root `.env` or `backend/.env`
    (with fallback to `.env.example` defaults when neither is set in os.environ)
    without overwriting existing environment variables explicitly set by tests or Docker.
    """
    app_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(app_dir)
    repo_root = os.path.dirname(backend_dir)

    candidates = [
        os.path.join(repo_root, ".env"),
        os.path.join(backend_dir, ".env"),
    ]
    loaded: Dict[str, str] = {}
    for path in candidates:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    if val.startswith("<CHANGE_ME") or "<CHANGE_ME" in val:
                        continue
                    loaded[key] = val
                    if key not in os.environ:
                        os.environ[key] = val
            break
    return loaded

# Load .env on module import
LOADED_ENV = load_dotenv_files()

def get_database_credentials_summary() -> dict:
    """
    Returns non-secret database connection topology and environment status for health/config audits.
    """
    return {
        "postgres_host": os.getenv("POSTGRES_HOST", "db"),
        "postgres_port": int(os.getenv("POSTGRES_PORT", "5432")),
        "postgres_db": os.getenv("POSTGRES_DB", "luxe_ecommerce"),
        "postgres_user": os.getenv("POSTGRES_USER", "luxe_app_user"),
        "sqlite_path": os.getenv("LUXE_SQLITE_PATH", "./backend/luxe_store.sqlite3"),
        "database_url_configured": bool(os.getenv("DATABASE_URL")),
    }


_NON_PROD_ENVS = {"development", "dev", "local", "test", "testing"}

def app_env() -> str:
    return (os.getenv("APP_ENV") or "production").strip().lower()

def is_production() -> bool:
    return app_env() not in _NON_PROD_ENVS
