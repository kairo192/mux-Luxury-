"""
Mus Luxury — application-level backup, restore and "new database" engine.

One engine, two databases:
  * SQLite  (a PC running the backend locally, dev, tests)
  * PostgreSQL 16 (the VPS, inside Docker)

A backup is a portable snapshot of every table (JSON, gzip), encrypted with
AES-256-GCM using a key derived from BACKUP_ENCRYPTION_KEY. Because the format
does not depend on the database engine, a PC backup can be restored on the
VPS and the other way round.

Used by:
  * the CMS "Sauvegardes & Sécurité" page (owner only) — backup now, restore,
    new empty database;
  * the nightly job on the VPS:  docker exec luxe_api python -m app.backup_cli create --kind nightly
    (infrastructure/backups/backup_postgres_and_media.sh), which ALSO keeps a
    native pg_dump as a second, independent copy.

Safety rules:
  * a restore or a reset always takes a "safety" backup first;
  * the whole replace runs in ONE transaction: it either fully succeeds or
    the database is left untouched;
  * backup files are never served over HTTP (no download endpoint).
"""

from __future__ import annotations

import base64
import datetime as _dt
import decimal
import gzip
import hashlib
import json
import os
import re
import secrets
import tarfile
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .database import PostgresCompatConnection, db_session

FORMAT = "luxe-backup/1"
MAGIC = b"LUXEBK1\n"  # encrypted file = MAGIC + salt(16) + nonce(12) + AES-GCM ciphertext
KDF_ITERATIONS = 200_000

# Never part of a snapshot: migration bookkeeping and the backup journal itself
# (restoring an old snapshot must not erase the record of newer backups).
EXCLUDED_TABLES: Set[str] = {"schema_migrations", "backup_records", "sqlite_sequence"}

# "Nouvelle base de données" keeps what is needed to log in and to sell:
# staff accounts + roles, registered POS devices, the 69 wilayas and their
# delivery tariffs, and the legal pages.
RESET_ALWAYS_KEEP: Set[str] = {
    "roles", "permissions", "role_permissions",
    "admin_users", "admin_recovery_codes",
    "devices",
    "delivery_zones", "delivery_rates",
    "static_pages",
}
# Kept only when the owner ticks "conserver les réglages de la boutique".
RESET_SETTINGS_TABLES: Set[str] = {"store_settings", "homepage_sections"}

BACKUP_NAME_RE = re.compile(r"^luxe_app_[a-z\-]+_\d{8}_\d{6}(_[0-9a-f]{4})?\.json\.gz(\.enc)?$")
_PLACEHOLDER_RE = re.compile(r"(CHANGE_?ME|your[-_]|<|REPLACE|placeholder)", re.IGNORECASE)

_OP_LOCK = threading.Lock()


class BackupError(RuntimeError):
    """Raised with a message that can be shown to the owner as-is."""


# ----------------------------------------------------------------- paths --

def backup_dir() -> Path:
    raw = os.getenv("BACKUP_DIR", "").strip()
    path = Path(raw) if raw else Path(__file__).resolve().parent.parent / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def upload_dir() -> Path:
    raw = os.getenv("UPLOAD_DIR", "").strip()
    return Path(raw) if raw else Path(__file__).resolve().parent.parent / "uploads"


def retention_days() -> int:
    try:
        return max(1, int(os.getenv("BACKUP_RETENTION_DAYS", "30")))
    except ValueError:
        return 30


def _encryption_secret() -> Optional[str]:
    key = os.getenv("BACKUP_ENCRYPTION_KEY", "").strip()
    if len(key) < 24 or _PLACEHOLDER_RE.search(key):
        return None
    return key


def encryption_enabled() -> bool:
    return _encryption_secret() is not None


# ------------------------------------------------------------ encryption --

def _derive_key(secret: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITERATIONS)
    return kdf.derive(secret.encode("utf-8"))


def _encrypt(data: bytes, secret: str) -> bytes:
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    return MAGIC + salt + nonce + AESGCM(_derive_key(secret, salt)).encrypt(nonce, data, MAGIC)


def _decrypt(blob: bytes, secret: Optional[str]) -> bytes:
    if not blob.startswith(MAGIC):
        raise BackupError("Fichier de sauvegarde non reconnu.")
    if not secret:
        raise BackupError("Cette sauvegarde est chiffrée : la clé BACKUP_ENCRYPTION_KEY du serveur est absente.")
    salt = blob[len(MAGIC):len(MAGIC) + 16]
    nonce = blob[len(MAGIC) + 16:len(MAGIC) + 28]
    try:
        return AESGCM(_derive_key(secret, salt)).decrypt(nonce, blob[len(MAGIC) + 28:], MAGIC)
    except Exception as exc:  # InvalidTag
        raise BackupError(
            "Impossible de déchiffrer la sauvegarde : elle a été créée avec une autre clé BACKUP_ENCRYPTION_KEY."
        ) from exc


# ------------------------------------------------------ database helpers --

def _is_pg(conn) -> bool:
    return isinstance(conn, PostgresCompatConnection)


def _raw(conn):
    """The driver connection: psycopg for PostgreSQL, sqlite3 otherwise."""
    return conn._conn if _is_pg(conn) else conn


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _ph(conn) -> str:
    return "%s" if _is_pg(conn) else "?"


def _query(conn, sql: str, params: Iterable[Any] = ()) -> Tuple[List[str], List[tuple]]:
    cur = _raw(conn).cursor()
    cur.execute(sql, tuple(params))
    cols = [d[0] for d in (cur.description or [])]
    rows = []
    for r in cur.fetchall():
        if isinstance(r, dict):
            rows.append(tuple(r[c] for c in cols))
        else:
            rows.append(tuple(r))
    return cols, rows


def _exec(conn, sql: str, params: Iterable[Any] = ()) -> None:
    cur = _raw(conn).cursor()
    cur.execute(sql, tuple(params))


def list_tables(conn) -> List[str]:
    if _is_pg(conn):
        _, rows = _query(
            conn,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name",
        )
    else:
        _, rows = _query(
            conn, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    return [r[0] for r in rows if r[0] not in EXCLUDED_TABLES]


def _table_columns(conn, table: str) -> List[str]:
    if _is_pg(conn):
        _, rows = _query(
            conn,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
            (table,),
        )
        return [r[0] for r in rows]
    _, rows = _query(conn, f"PRAGMA table_info({_q(table)})")
    return [r[1] for r in rows]


def _fk_parents(conn, tables: List[str]) -> Dict[str, Set[str]]:
    """table -> tables it references (its parents)."""
    wanted = set(tables)
    parents: Dict[str, Set[str]] = {t: set() for t in tables}
    if _is_pg(conn):
        _, rows = _query(
            conn,
            """SELECT tc.table_name, ccu.table_name
                 FROM information_schema.table_constraints tc
                 JOIN information_schema.constraint_column_usage ccu
                   ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'""",
        )
        for child, parent in rows:
            if child in wanted and parent in wanted and child != parent:
                parents[child].add(parent)
    else:
        for t in tables:
            _, rows = _query(conn, f"PRAGMA foreign_key_list({_q(t)})")
            for r in rows:
                parent = r[2]
                if parent in wanted and parent != t:
                    parents[t].add(parent)
    return parents


def _topological(tables: List[str], parents: Dict[str, Set[str]]) -> List[str]:
    """Parents before children. Cycles (rare) are broken deterministically."""
    ordered: List[str] = []
    placed: Set[str] = set()
    pending = sorted(tables)
    while pending:
        ready = [t for t in pending if parents.get(t, set()) <= placed]
        if not ready:
            ready = [pending[0]]
        for t in ready:
            ordered.append(t)
            placed.add(t)
        pending = [t for t in pending if t not in placed]
    return ordered


def _encode(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, memoryview):
        v = v.tobytes()
    if isinstance(v, (bytes, bytearray)):
        return {"$b64": base64.b64encode(bytes(v)).decode("ascii")}
    return v


def _decode(v: Any) -> Any:
    if isinstance(v, dict) and "$b64" in v:
        return base64.b64decode(v["$b64"])
    return v


def _row_counts(conn, tables: Iterable[str]) -> Dict[str, int]:
    counts = {}
    for t in tables:
        _, rows = _query(conn, f"SELECT COUNT(*) FROM {_q(t)}")
        counts[t] = int(rows[0][0])
    return counts


# --------------------------------------------------------------- export --

def export_snapshot(conn) -> Dict[str, Any]:
    tables = list_tables(conn)
    data: Dict[str, Any] = {}
    for t in tables:
        cols, rows = _query(conn, f"SELECT * FROM {_q(t)}")
        data[t] = {"columns": cols, "rows": [[_encode(v) for v in r] for r in rows]}
    return {
        "format": FORMAT,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "engine": "postgresql" if _is_pg(conn) else "sqlite",
        "tables": data,
        "counts": {t: len(v["rows"]) for t, v in data.items()},
    }


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _media_archive(stamp: str, kind: str) -> Optional[Dict[str, Any]]:
    """Product photos are public on the storefront, so the media archive is
    not encrypted; it carries a checksum like the database file."""
    src = upload_dir()
    if not src.is_dir():
        return None
    name = f"luxe_media_{kind}_{stamp}.tar.gz"
    path = backup_dir() / name
    tmp = path.with_suffix(".gz.tmp")
    with tarfile.open(tmp, "w:gz") as tar:
        tar.add(str(src), arcname=".")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return {"name": name, "size": path.stat().st_size, "sha256": _sha256_file(path)}


def _record_backup(filename: str, backup_type: str, size: int, sha: str, status: str, actor_id: Optional[int]) -> None:
    try:
        with db_session(commit=True) as conn:
            conn.execute(
                "INSERT INTO backup_records (filename, backup_type, size_bytes, sha256_checksum, status, triggered_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (filename, backup_type, size, sha, status, actor_id),
            )
    except Exception:
        # The journal is informative; never fail a good backup because of it.
        pass


def create_backup(kind: str = "manual", actor_id: Optional[int] = None, include_media: bool = False) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-z\-]{2,20}", kind):
        raise BackupError("Type de sauvegarde invalide.")
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(2)

    with db_session() as conn:
        snap = export_snapshot(conn)

    total_rows = sum(snap["counts"].values())
    if not snap["tables"] or "roles" not in snap["tables"] or snap["counts"].get("roles", 0) == 0:
        # A database without roles is not a real store database (wrong file,
        # empty volume...). Refuse instead of producing a useless backup.
        _record_backup(f"luxe_app_{kind}_{stamp}", "database", 0, "-" * 64, "failed", actor_id)
        raise BackupError("La base de données semble vide ou inaccessible : sauvegarde annulée.")

    raw = gzip.compress(json.dumps(snap, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), compresslevel=6)
    secret = _encryption_secret()
    encrypted = secret is not None
    payload = _encrypt(raw, secret) if encrypted else raw
    name = f"luxe_app_{kind}_{stamp}.json.gz" + (".enc" if encrypted else "")
    path = backup_dir() / name
    _write_atomic(path, payload)
    sha = _sha256_file(path)

    media = _media_archive(stamp, kind) if include_media else None

    meta = {
        "name": name,
        "kind": kind,
        "created_at": snap["created_at"],
        "engine": snap["engine"],
        "encrypted": encrypted,
        "size": path.stat().st_size,
        "sha256": sha,
        "total_rows": total_rows,
        "counts": snap["counts"],
        "media": media,
    }
    _write_atomic(backup_dir() / (name + ".meta.json"), json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
    _record_backup(name, "full" if media else "database", meta["size"], sha, "verified", actor_id)
    prune_backups()
    return meta


# ---------------------------------------------------------------- listing --

def _meta_for(path: Path) -> Dict[str, Any]:
    side = path.with_name(path.name + ".meta.json")
    if side.is_file():
        try:
            return json.loads(side.read_text(encoding="utf-8"))
        except Exception:
            pass
    st = path.stat()
    return {
        "name": path.name,
        "kind": path.name.split("_")[2] if path.name.count("_") >= 3 else "unknown",
        "created_at": _dt.datetime.fromtimestamp(st.st_mtime, _dt.timezone.utc).isoformat(),
        "encrypted": path.name.endswith(".enc"),
        "size": st.st_size,
        "sha256": None,
        "total_rows": None,
        "counts": {},
        "media": None,
    }


def list_backups() -> List[Dict[str, Any]]:
    items = [_meta_for(p) for p in backup_dir().glob("luxe_app_*.json.gz*") if BACKUP_NAME_RE.match(p.name)]
    items.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    return items


def prune_backups(keep_min: int = 10) -> int:
    """Deletes app backups older than BACKUP_RETENTION_DAYS but always keeps
    the newest `keep_min`, whatever their age."""
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=retention_days())
    removed = 0
    for meta in list_backups()[keep_min:]:
        try:
            created = _dt.datetime.fromisoformat(meta["created_at"])
        except Exception:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=_dt.timezone.utc)
        if created >= cutoff:
            continue
        base = backup_dir() / meta["name"]
        for p in (base, base.with_name(base.name + ".meta.json")):
            p.unlink(missing_ok=True)
        if meta.get("media") and meta["media"].get("name"):
            (backup_dir() / meta["media"]["name"]).unlink(missing_ok=True)
        removed += 1
    return removed


def _resolve(name: str) -> Path:
    if not BACKUP_NAME_RE.match(name or ""):
        raise BackupError("Nom de sauvegarde invalide.")
    path = backup_dir() / name
    if not path.is_file():
        raise BackupError("Sauvegarde introuvable sur le serveur.")
    return path


def load_snapshot(name: str) -> Dict[str, Any]:
    path = _resolve(name)
    meta = _meta_for(path)
    if meta.get("sha256") and _sha256_file(path) != meta["sha256"]:
        raise BackupError("La sauvegarde est corrompue (empreinte SHA-256 différente).")
    blob = path.read_bytes()
    raw = _decrypt(blob, _encryption_secret()) if blob.startswith(MAGIC) else blob
    try:
        snap = json.loads(gzip.decompress(raw).decode("utf-8"))
    except Exception as exc:
        raise BackupError("La sauvegarde est illisible (archive endommagée).") from exc
    if snap.get("format") != FORMAT or "tables" not in snap:
        raise BackupError("Format de sauvegarde non pris en charge.")
    return snap


def verify_backup(name: str) -> Dict[str, Any]:
    snap = load_snapshot(name)
    return {"name": name, "ok": True, "engine": snap.get("engine"), "total_rows": sum(snap.get("counts", {}).values())}


# --------------------------------------------------------- replace / wipe --

def _begin_bulk(conn) -> None:
    raw = _raw(conn)
    if _is_pg(conn):
        # Skip FK triggers for the bulk replace when the role allows it (the
        # Docker POSTGRES_USER is a superuser). SET LOCAL ends with the
        # transaction, so a pooled connection is never left in this mode.
        # Without the privilege the topological order is enough.
        try:
            _exec(conn, "SET LOCAL session_replication_role = replica")
        except Exception:
            raw.rollback()
    else:
        raw.commit()  # PRAGMA foreign_keys is ignored inside a transaction
        raw.execute("PRAGMA foreign_keys = OFF")


def _end_bulk(conn) -> None:
    if not _is_pg(conn):
        _raw(conn).execute("PRAGMA foreign_keys = ON")


def _check_integrity(conn) -> None:
    if not _is_pg(conn):
        _, bad = _query(conn, "PRAGMA foreign_key_check")
        if bad:
            raise BackupError(f"Contrôle d'intégrité échoué ({len(bad)} liens orphelins) : opération annulée.")


def _reset_sequences(conn, tables: Iterable[str], restart: bool) -> None:
    if _is_pg(conn):
        for t in tables:
            if "id" not in _table_columns(conn, t):
                continue
            _, rows = _query(conn, "SELECT pg_get_serial_sequence(%s, 'id')", (t,))
            seq = rows[0][0] if rows else None
            if not seq:
                continue
            if restart:
                _exec(conn, f"ALTER SEQUENCE {seq} RESTART WITH 1")
            else:
                _exec(conn, f"SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {_q(t)}), 0) + 1, false)", (seq,))
    else:
        names = list(tables)
        try:
            if restart and names:
                _exec(conn, f"DELETE FROM sqlite_sequence WHERE name IN ({','.join('?' * len(names))})", names)
        except Exception:
            pass  # no AUTOINCREMENT table yet → no sqlite_sequence


def _replace_all(conn, snap: Dict[str, Any]) -> Dict[str, int]:
    current = list_tables(conn)
    order = _topological(current, _fk_parents(conn, current))
    for t in reversed(order):
        _exec(conn, f"DELETE FROM {_q(t)}")
    restored: Dict[str, int] = {}
    ph = _ph(conn)
    for t in order:
        block = snap["tables"].get(t)
        if not block or not block["rows"]:
            restored[t] = 0
            continue
        live_cols = set(_table_columns(conn, t))
        idx = [i for i, c in enumerate(block["columns"]) if c in live_cols]
        cols = [block["columns"][i] for i in idx]
        sql = f"INSERT INTO {_q(t)} ({', '.join(_q(c) for c in cols)}) VALUES ({', '.join([ph] * len(cols))})"
        cur = _raw(conn).cursor()
        cur.executemany(sql, [tuple(_decode(row[i]) for i in idx) for row in block["rows"]])
        restored[t] = len(block["rows"])
    _reset_sequences(conn, order, restart=False)
    return restored


def _new_epoch(conn) -> str:
    """A new catalog epoch tells every POS PC to drop its offline copy of the
    catalog and download it again (see /api/v1/pos/catalog/snapshot)."""
    epoch = secrets.token_hex(8)
    _exec(conn, f"DELETE FROM store_settings WHERE setting_key = {_ph(conn)}", ("catalog_epoch",))
    _exec(
        conn,
        f"INSERT INTO store_settings (setting_key, setting_value) VALUES ({_ph(conn)}, {_ph(conn)})",
        ("catalog_epoch", epoch),
    )
    return epoch


def _audit(conn, actor_id: Optional[int], action: str, details: Dict[str, Any]) -> None:
    ph = _ph(conn)
    _exec(
        conn,
        f"INSERT INTO audit_logs (admin_user_id, action, entity_type, entity_id, details_json) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
        (actor_id, action, "database", "store", json.dumps(details, ensure_ascii=False)),
    )


def restore_backup(name: str, actor_id: Optional[int] = None) -> Dict[str, Any]:
    if not _OP_LOCK.acquire(blocking=False):
        raise BackupError("Une autre opération sur la base de données est déjà en cours.")
    try:
        snap = load_snapshot(name)  # validate BEFORE touching anything
        safety = create_backup("pre-restore", actor_id)
        with db_session() as conn:
            _begin_bulk(conn)
            try:
                restored = _replace_all(conn, snap)
                _check_integrity(conn)
                epoch = _new_epoch(conn)
                _audit(conn, actor_id, "database_restore", {"backup": name, "safety_backup": safety["name"]})
                _raw(conn).commit()
            except Exception:
                _raw(conn).rollback()
                raise
            finally:
                _end_bulk(conn)
        return {"restored": True, "backup": name, "safety_backup": safety["name"], "rows": sum(restored.values()), "catalog_epoch": epoch}
    finally:
        _OP_LOCK.release()


def reset_database(actor_id: Optional[int] = None, keep_settings: bool = True) -> Dict[str, Any]:
    """Empties the store: catalog, stock, orders, customers, POS sales, cash,
    expenses, suppliers, coupons, banners, audit history. Staff accounts,
    roles, POS devices, wilayas/tariffs and legal pages stay so the shop can
    keep working immediately."""
    if not _OP_LOCK.acquire(blocking=False):
        raise BackupError("Une autre opération sur la base de données est déjà en cours.")
    try:
        safety = create_backup("pre-reset", actor_id)
        keep = set(RESET_ALWAYS_KEEP) | (RESET_SETTINGS_TABLES if keep_settings else set())
        with db_session() as conn:
            current = list_tables(conn)
            wipe = [t for t in current if t not in keep]
            order = _topological(current, _fk_parents(conn, current))
            before = _row_counts(conn, wipe)
            _begin_bulk(conn)
            try:
                for t in reversed(order):
                    if t in wipe:
                        _exec(conn, f"DELETE FROM {_q(t)}")
                _reset_sequences(conn, wipe, restart=True)
                _check_integrity(conn)
                epoch = _new_epoch(conn)
                _audit(conn, actor_id, "database_reset", {
                    "safety_backup": safety["name"],
                    "keep_settings": keep_settings,
                    "rows_deleted": sum(before.values()),
                })
                _raw(conn).commit()
            except Exception:
                _raw(conn).rollback()
                raise
            finally:
                _end_bulk(conn)
        return {
            "reset": True,
            "safety_backup": safety["name"],
            "rows_deleted": sum(before.values()),
            "tables_emptied": sorted(wipe),
            "catalog_epoch": epoch,
        }
    finally:
        _OP_LOCK.release()


# ------------------------------------------------------------------ status --

KEY_TABLES = [
    ("categories", "Catégories"), ("products", "Produits"), ("product_variants", "Variantes"),
    ("customers", "Clients"), ("orders", "Commandes en ligne"), ("pos_sales", "Ventes caisse"),
    ("inventory_movements", "Mouvements de stock"), ("expenses", "Dépenses"),
    ("suppliers", "Fournisseurs"), ("admin_users", "Comptes staff"),
]


def database_info() -> Dict[str, Any]:
    with db_session() as conn:
        tables = list_tables(conn)
        counts = _row_counts(conn, [t for t, _ in KEY_TABLES if t in tables])
        total_rows = sum(_row_counts(conn, tables).values())
        if _is_pg(conn):
            _, rows = _query(conn, "SELECT pg_database_size(current_database()), version()")
            size, version = int(rows[0][0]), str(rows[0][1]).split(",")[0]
            engine, location = "PostgreSQL", "Serveur (VPS) — conteneur luxe_postgres"
        else:
            _, rows = _query(conn, "PRAGMA database_list")
            path = next((r[2] for r in rows if r[1] == "main"), "") or ""
            size = Path(path).stat().st_size if path and Path(path).is_file() else 0
            _, v = _query(conn, "SELECT sqlite_version()")
            engine, version, location = "SQLite", f"SQLite {v[0][0]}", "Fichier local sur ce poste"

    backups = list_backups()
    last = backups[0] if backups else None
    warnings: List[str] = []
    if not encryption_enabled():
        warnings.append("Les sauvegardes ne sont pas chiffrées : BACKUP_ENCRYPTION_KEY n'est pas configurée sur le serveur.")
    if not last:
        warnings.append("Aucune sauvegarde n'existe encore.")
    else:
        try:
            age_h = (_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.fromisoformat(last["created_at"])).total_seconds() / 3600
            if age_h > 26:
                warnings.append(f"Dernière sauvegarde il y a {int(age_h)} h : la sauvegarde automatique de nuit ne tourne pas.")
        except Exception:
            pass
    if os.getenv("S3_BACKUP_ENABLED", "false").strip().lower() != "true":
        warnings.append(
            "Aucune copie hors serveur : les sauvegardes restent sur le même serveur que la boutique. "
            "Activez S3_BACKUP_ENABLED (stockage S3) pour survivre à la perte du VPS."
        )

    return {
        "engine": engine,
        "version": version,
        "location": location,
        "size_bytes": size,
        "total_rows": total_rows,
        "counts": [{"table": t, "label": label, "rows": counts.get(t, 0)} for t, label in KEY_TABLES if t in counts],
        "encryption": encryption_enabled(),
        "retention_days": retention_days(),
        "backups": backups[:30],
        "last_backup": last,
        "warnings": warnings,
        "reset_keeps": sorted(RESET_ALWAYS_KEEP),
        "reset_settings_tables": sorted(RESET_SETTINGS_TABLES),
    }
