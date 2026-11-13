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
import contextlib
import datetime as _dt
import decimal
import gzip
import hashlib
import io
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

FORMAT = "luxe-backup/2"       # JSON Lines, tables in restore order (streamed both ways)
FORMAT_V1 = "luxe-backup/1"    # one JSON document (older backups, still restorable)
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
            # Distinct aliases: with dict rows two columns both named
            # "table_name" would collapse into one and every FK would be lost.
            """SELECT DISTINCT tc.table_name AS child_table, ccu.table_name AS parent_table
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

def _iter_table(conn, table: str, batch: int = 500):
    """Rows of a table in id order, a batch at a time: the backup never holds
    a whole table in memory (the API container has 256 MB on a 2 GB VPS).
    PostgreSQL uses a server-side cursor; a normal one downloads everything."""
    order = " ORDER BY id" if "id" in _table_columns(conn, table) else ""
    sql = f"SELECT * FROM {_q(table)}{order}"
    raw = _raw(conn)
    cur = raw.cursor(name=f"bk_{secrets.token_hex(4)}") if _is_pg(conn) else raw.cursor()
    try:
        cur.execute(sql)
        cols: Optional[List[str]] = None
        while True:
            chunk = cur.fetchmany(batch)
            if cols is None:
                cols = [d[0] for d in (cur.description or [])]
                yield cols
            if not chunk:
                return
            for r in chunk:
                yield tuple(r[c] for c in cols) if isinstance(r, dict) else tuple(r)
    finally:
        cur.close()


def _begin_consistent_read(conn) -> None:
    """Every table of a backup is read from ONE view of the database, so an
    order committed while the backup runs is either fully in it (with its
    customer and lines) or not at all."""
    conn.commit()                 # start from no open transaction
    if _is_pg(conn):
        # First statement of the new transaction: all later reads share its snapshot.
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    else:
        conn.execute("BEGIN")     # SQLite: the read snapshot is held until the transaction ends


def write_snapshot(conn, out_path: Path) -> Dict[str, Any]:
    """Writes the whole store database as gzip-compressed JSON Lines:

        {"format": "luxe-backup/2", "created_at": ..., "engine": ...}
        {"table": "roles", "columns": [...]}
        [row], [row], ...                      one line per row, in id order
        {"table": ...} ...
        {"end": true, "counts": {...}}

    Tables come in restore order (parents before children), so a restore can
    stream the file once with little memory — the API container has 256 MB."""
    created = _dt.datetime.now(_dt.timezone.utc).isoformat()
    engine = "postgresql" if _is_pg(conn) else "sqlite"
    counts: Dict[str, int] = {}
    dump = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    tables = list_tables(conn)
    order = _topological(tables, _fk_parents(conn, tables))
    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=6) as f:
        f.write(dump({"format": FORMAT, "created_at": created, "engine": engine}) + "\n")
        for table in order:
            rows = _iter_table(conn, table)
            f.write(dump({"table": table, "columns": next(rows)}) + "\n")
            n = 0
            for row in rows:
                f.write(dump([_encode(v) for v in row]) + "\n")
                n += 1
            counts[table] = n
        f.write(dump({"end": True, "counts": counts}) + "\n")
    return {"created_at": created, "engine": engine, "counts": counts}


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


def create_backup(kind: str = "manual", actor_id: Optional[int] = None, include_media: bool = False,
                  protect: Iterable[str] = ()) -> Dict[str, Any]:
    if not re.fullmatch(r"[a-z\-]{2,20}", kind):
        raise BackupError("Type de sauvegarde invalide.")
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(2)

    name_plain = f"luxe_app_{kind}_{stamp}.json.gz"
    tmp = backup_dir() / (name_plain + ".part")
    try:
        with db_session() as conn:
            _begin_consistent_read(conn)
            try:
                snap = write_snapshot(conn, tmp)
            finally:
                conn.rollback()           # read-only: just end the transaction
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    total_rows = sum(snap["counts"].values())
    if not snap["counts"] or snap["counts"].get("roles", 0) == 0:
        # A database without roles is not a real store database (wrong file,
        # empty volume...). Refuse instead of producing a useless backup.
        tmp.unlink(missing_ok=True)
        _record_backup(f"luxe_app_{kind}_{stamp}", "database", 0, "-" * 64, "failed", actor_id)
        raise BackupError("La base de données semble vide ou inaccessible : sauvegarde annulée.")

    secret = _encryption_secret()
    encrypted = secret is not None
    name = name_plain + (".enc" if encrypted else "")
    path = backup_dir() / name
    if encrypted:
        # The compressed file is small (about a tenth of the data).
        _write_atomic(path, _encrypt(tmp.read_bytes(), secret))
        tmp.unlink(missing_ok=True)
    else:
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
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
    prune_backups(protect=protect)
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


# A backup being restored is marked with a file in the backup folder, so that
# ANY process (the nightly `backup_cli create` runs in its own process) leaves
# it and its photo archive alone until the restore is over. A marker older
# than PROTECT_MAX_AGE_S (a crashed restore) no longer counts.
PROTECT_PREFIX = ".restoring_"
PROTECT_MAX_AGE_S = 6 * 3600


@contextlib.contextmanager
def _protected_from_pruning(name: str):
    marker = backup_dir() / (PROTECT_PREFIX + name)
    marker.write_text(_dt.datetime.now(_dt.timezone.utc).isoformat(), encoding="utf-8")
    try:
        yield
    finally:
        marker.unlink(missing_ok=True)


def _names_being_restored() -> Set[str]:
    now = _dt.datetime.now().timestamp()
    names = set()
    for marker in backup_dir().glob(PROTECT_PREFIX + "*"):
        try:
            if now - marker.stat().st_mtime < PROTECT_MAX_AGE_S:
                names.add(marker.name[len(PROTECT_PREFIX):])
        except OSError:
            continue
    return names


def prune_backups(keep_min: int = 10, protect: Iterable[str] = ()) -> int:
    """Deletes app backups older than BACKUP_RETENTION_DAYS but always keeps
    the newest `keep_min`, whatever their age, and those in `protect` or being
    restored by any process (their photo archive is still needed)."""
    protected = set(protect) | _names_being_restored()
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=retention_days())
    removed = 0
    for meta in list_backups()[keep_min:]:
        if meta.get("name") in protected:
            continue
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


# ------------------------------------------------- copies on the owner's PC --

MAX_IMPORT_BYTES = 100 * 1024 * 1024


def file_for_pc_copy(name: str) -> Path:
    """A backup the owner may copy to the shop PC: only an ENCRYPTED one (a
    stolen PC or USB key then gives nothing without the backup key)."""
    path = _resolve(name)
    if not name.endswith(".enc"):
        raise BackupError("Copie refusée : cette sauvegarde n'est pas chiffrée "
                          "(BACKUP_ENCRYPTION_KEY manquante sur le serveur).")
    return path


def import_pc_copy(blob: bytes, original_name: str, actor_id: Optional[int] = None) -> Dict[str, Any]:
    """Stores a copy sent back from the PC so it can be restored like any
    backup. It must decrypt with THIS server's key and be a store backup."""
    if len(blob) > MAX_IMPORT_BYTES:
        raise BackupError("Fichier trop volumineux pour une sauvegarde de la boutique.")
    if not blob.startswith(MAGIC):
        raise BackupError("Ce fichier n'est pas une sauvegarde chiffrée de la boutique.")
    raw = _decrypt(blob, _encryption_secret())
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as g:
            head = g.read(400).decode("utf-8", "replace")
    except Exception as exc:
        raise BackupError("La sauvegarde est illisible (archive endommagée).") from exc
    if f'"format":"{FORMAT}"' not in head and f'"format":"{FORMAT_V1}"' not in head:
        raise BackupError("Format de sauvegarde non pris en charge.")
    m = re.search(r'"created_at":"([^"]+)"', head)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(2)
    name = f"luxe_app_imported_{stamp}.json.gz.enc"
    path = backup_dir() / name
    _write_atomic(path, blob)
    sha = _sha256_file(path)
    meta = {
        "name": name, "kind": "imported", "created_at": m.group(1) if m else _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "engine": None, "encrypted": True, "size": path.stat().st_size, "sha256": sha,
        "total_rows": None, "counts": {}, "media": None, "imported_from": (original_name or "")[:120],
    }
    _write_atomic(backup_dir() / (name + ".meta.json"), json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
    _record_backup(name, "imported", meta["size"], sha, "verified", actor_id)
    return meta


def _read_backup(name: str) -> bytes:
    """The compressed backup (decrypted when needed) after its checksum is
    verified. Compressed data is about a tenth of the database."""
    path = _resolve(name)
    meta = _meta_for(path)
    if meta.get("sha256") and _sha256_file(path) != meta["sha256"]:
        raise BackupError("La sauvegarde est corrompue (empreinte SHA-256 différente).")
    blob = path.read_bytes()
    return _decrypt(blob, _encryption_secret()) if blob.startswith(MAGIC) else blob


def _lines(raw: bytes):
    """Decompressed lines, one at a time (never the whole text in memory)."""
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as g:
        for line in io.TextIOWrapper(g, encoding="utf-8"):
            if line.strip():
                yield line


def _is_v2(raw: bytes) -> bool:
    try:
        first = next(_lines(raw))
    except Exception as exc:
        raise BackupError("La sauvegarde est illisible (archive endommagée).") from exc
    return first.startswith("{") and f'"format":"{FORMAT}"' in first.replace(" ", "")


def _scan_v2(raw: bytes) -> Dict[str, Any]:
    """Reads the whole file once to prove it is complete and coherent BEFORE
    anything in the database is touched."""
    header: Optional[Dict[str, Any]] = None
    counts: Dict[str, int] = {}
    table: Optional[str] = None
    width = 0
    end: Optional[Dict[str, Any]] = None
    try:
        for line in _lines(raw):
            if end is not None:
                raise BackupError("La sauvegarde est illisible (données après la fin).")
            item = json.loads(line)
            if header is None:
                if not isinstance(item, dict) or item.get("format") != FORMAT:
                    raise BackupError("Format de sauvegarde non pris en charge.")
                header = item
            elif isinstance(item, list):
                if table is None or len(item) != width:
                    raise BackupError("La sauvegarde est illisible (ligne incohérente).")
                counts[table] += 1
            elif isinstance(item, dict) and "table" in item:
                table, width = str(item["table"]), len(item.get("columns") or [])
                counts[table] = 0
            elif isinstance(item, dict) and item.get("end"):
                end = item
            else:
                raise BackupError("La sauvegarde est illisible (ligne inconnue).")
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError("La sauvegarde est illisible (archive endommagée).") from exc
    if header is None or end is None:
        raise BackupError("La sauvegarde est incomplète (fin du fichier absente).")
    if end.get("counts") != counts:
        raise BackupError("La sauvegarde est incomplète (nombre de lignes différent).")
    if not counts.get("roles"):
        raise BackupError("La sauvegarde ne contient pas une base de boutique valide.")
    return {"engine": header.get("engine"), "counts": counts, "created_at": header.get("created_at")}


def _parse_v1(raw: bytes) -> Dict[str, Any]:
    try:
        snap = json.loads(gzip.decompress(raw).decode("utf-8"))
    except Exception as exc:
        raise BackupError("La sauvegarde est illisible (archive endommagée).") from exc
    if snap.get("format") != FORMAT_V1 or "tables" not in snap:
        raise BackupError("Format de sauvegarde non pris en charge.")
    return snap


def load_snapshot(name: str) -> Dict[str, Any]:
    """Whole snapshot as a dict (tests and old-format backups). Restores do
    not use this for new backups: they stream."""
    raw = _read_backup(name)
    if not _is_v2(raw):
        return _parse_v1(raw)
    _scan_v2(raw)
    snap: Dict[str, Any] = {"format": FORMAT, "tables": {}, "counts": {}}
    current = None
    for line in _lines(raw):
        item = json.loads(line)
        if isinstance(item, list):
            snap["tables"][current]["rows"].append(item)
        elif "table" in item:
            current = item["table"]
            snap["tables"][current] = {"columns": item["columns"], "rows": []}
        elif item.get("end"):
            snap["counts"] = item["counts"]
        else:
            snap.update({k: v for k, v in item.items() if k in ("created_at", "engine")})
    return snap


def verify_backup(name: str) -> Dict[str, Any]:
    raw = _read_backup(name)
    if _is_v2(raw):
        info = _scan_v2(raw)
        return {"name": name, "ok": True, "engine": info["engine"], "total_rows": sum(info["counts"].values())}
    snap = _parse_v1(raw)
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


_PG_FOREIGN_KEYS = """
SELECT c.conrelid::regclass::text AS child_table, c.confrelid::regclass::text AS parent_table,
       ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY AS k(num, pos)
             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.num ORDER BY k.pos) AS child_cols,
       ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY AS k(num, pos)
             JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.num ORDER BY k.pos) AS parent_cols
  FROM pg_constraint c
 WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace"""


def _orphan_rows(conn) -> int:
    """Rows whose foreign key points at nothing. SQLite has a pragma for it;
    on PostgreSQL the bulk replace runs with FK triggers off
    (session_replication_role = replica), so every FK is checked here."""
    if not _is_pg(conn):
        _, bad = _query(conn, "PRAGMA foreign_key_check")
        return len(bad)
    _, fks = _query(conn, _PG_FOREIGN_KEYS)
    total = 0
    for child, parent, child_cols, parent_cols in fks:
        child_cols, parent_cols = list(child_cols), list(parent_cols)
        if not child_cols or len(child_cols) != len(parent_cols):
            continue
        not_null = " AND ".join(f"c.{_q(col)} IS NOT NULL" for col in child_cols)
        match = " AND ".join(f"p.{_q(pc)} = c.{_q(cc)}" for cc, pc in zip(child_cols, parent_cols))
        _, rows = _query(conn, f"SELECT COUNT(*) FROM {_q(child)} c WHERE {not_null} "
                               f"AND NOT EXISTS (SELECT 1 FROM {_q(parent)} p WHERE {match})")
        total += int(rows[0][0])
    return total


def _check_integrity(conn) -> None:
    bad = _orphan_rows(conn)
    if bad:
        raise BackupError(f"Contrôle d'intégrité échoué ({bad} liens orphelins) : opération annulée.")


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
        rows = block["rows"]
        if "id" in block["columns"]:
            # Older backups were not sorted: sort here too (see snapshot).
            id_i = block["columns"].index("id")
            rows = sorted(rows, key=lambda r: (r[id_i] is None, r[id_i] if isinstance(r[id_i], int) else 0))
        sql = f"INSERT INTO {_q(t)} ({', '.join(_q(c) for c in cols)}) VALUES ({', '.join([ph] * len(cols))})"
        cur = _raw(conn).cursor()
        cur.executemany(sql, [tuple(_decode(row[i]) for i in idx) for row in rows])
        restored[t] = len(block["rows"])
    _reset_sequences(conn, order, restart=False)
    return restored


def _replace_all_stream(conn, raw: bytes, batch: int = 500) -> Dict[str, int]:
    """Same as _replace_all for a version-2 backup, streamed: rows go to the
    database in batches of 500, the file is read once."""
    current = list_tables(conn)
    order = _topological(current, _fk_parents(conn, current))
    for t in reversed(order):
        _exec(conn, f"DELETE FROM {_q(t)}")
    live_tables = set(current)
    restored: Dict[str, int] = {}
    ph = _ph(conn)
    cur = _raw(conn).cursor()
    table: Optional[str] = None
    idx: List[int] = []
    sql = ""
    pending: List[tuple] = []

    def flush() -> None:
        if pending:
            cur.executemany(sql, pending)
            pending.clear()

    for line in _lines(raw):
        item = json.loads(line)
        if isinstance(item, list):
            if table is None or table not in live_tables or not idx:
                continue
            pending.append(tuple(_decode(item[i]) for i in idx))
            restored[table] += 1
            if len(pending) >= batch:
                flush()
        elif isinstance(item, dict) and "table" in item:
            flush()
            table = item["table"]
            restored.setdefault(table, 0)
            if table in live_tables:
                live_cols = set(_table_columns(conn, table))
                cols_all = item.get("columns") or []
                idx = [i for i, c in enumerate(cols_all) if c in live_cols]
                cols = [cols_all[i] for i in idx]
                sql = f"INSERT INTO {_q(table)} ({', '.join(_q(c) for c in cols)}) VALUES ({', '.join([ph] * len(cols))})"
    flush()
    _reset_sequences(conn, order, restart=False)
    return {t: n for t, n in restored.items() if t in live_tables}


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


MEDIA_NAME_RE = re.compile(r"^luxe_media_[a-z\-]+_\d{8}_\d{6}(_[0-9a-f]{4})?\.tar\.gz$")


def _media_for_restore(name: str) -> Optional[Path]:
    """The photo archive saved with this backup ("+ photos"), checked BEFORE
    anything is changed. None when the backup has no photos (or the archive is
    no longer on disk: the database restore then keeps the current photos)."""
    media = (_meta_for(backup_dir() / name).get("media") or {})
    mname = media.get("name") or ""
    if not MEDIA_NAME_RE.match(mname):
        return None
    path = backup_dir() / mname
    if not path.is_file():
        return None
    if media.get("sha256") and _sha256_file(path) != media["sha256"]:
        raise BackupError("L'archive des photos de cette sauvegarde est endommagée : rien n'a été modifié.")
    return path


def _extract_media(archive: Path) -> int:
    """Puts the photos back in the upload folder (adds and overwrites, never
    deletes). Only plain files and folders inside it are accepted."""
    dest = upload_dir()
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = []
        for m in tar.getmembers():
            parts = Path(m.name).parts
            if not (m.isfile() or m.isdir()) or m.name.startswith(("/", "\\")) or ".." in parts:
                continue
            members.append(m)
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, members=members, filter="data")
        else:  # pragma: no cover - Python without the extraction filters
            tar.extractall(dest, members=members)
    return sum(1 for m in members if m.isfile())


def restore_backup(name: str, actor_id: Optional[int] = None) -> Dict[str, Any]:
    if not _OP_LOCK.acquire(blocking=False):
        raise BackupError("Une autre opération sur la base de données est déjà en cours.")
    try:
        _resolve(name)                 # valid name of an existing backup, before any marker
        with _protected_from_pruning(name):
            return _restore_backup_locked(name, actor_id)
    finally:
        _OP_LOCK.release()


def _restore_backup_locked(name: str, actor_id: Optional[int]) -> Dict[str, Any]:
    # Validate BEFORE touching anything.
    raw = _read_backup(name)
    streamed = _is_v2(raw)
    if streamed:
        _scan_v2(raw)
        snap = None
    else:
        snap = _parse_v1(raw)
    media_archive = _media_for_restore(name)
    # The safety backup prunes old ones: never the one being restored.
    safety = create_backup("pre-restore", actor_id, protect=(name,))
    with db_session() as conn:
        _begin_bulk(conn)
        try:
            restored = _replace_all_stream(conn, raw) if streamed else _replace_all(conn, snap)
            _check_integrity(conn)
            epoch = _new_epoch(conn)
            _audit(conn, actor_id, "database_restore", {"backup": name, "safety_backup": safety["name"]})
            _raw(conn).commit()
        except Exception:
            _raw(conn).rollback()
            raise
        finally:
            _end_bulk(conn)
    result = {"restored": True, "backup": name, "safety_backup": safety["name"], "rows": sum(restored.values()),
              "catalog_epoch": epoch, "media_files": None}
    if media_archive is not None:
        # After the database commit: photos are only added/overwritten, so a
        # failure here never leaves the database half-restored; it is reported.
        try:
            result["media_files"] = _extract_media(media_archive)
        except Exception as exc:
            result["media_error"] = f"Photos non restaurées : {type(exc).__name__}"
    return result


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
    if os.getenv("S3_BACKUP_ENABLED", "false").strip().lower() not in ("true", "1", "yes"):
        warnings.append(
            "Aucune copie hors serveur : les sauvegardes restent sur le même serveur que la boutique. "
            "Activez S3_BACKUP_ENABLED (stockage S3, 10 Go gratuits chez Backblaze B2 ou Cloudflare R2) pour survivre à la perte du VPS."
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
