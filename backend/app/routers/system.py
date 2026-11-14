"""Database administration and desktop CMS updates (owner only / staff login)."""
from fastapi import APIRouter
from .. import settings as app_settings
import os
import re
from pathlib import Path
from fastapi import Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from ..database import db_session
from ..security import verify_password
from .. import backup_engine as _bk
from ..deps import (
    get_current_admin,
    log_audit,
    require_permission,
)

router = APIRouter()


# ----------------------------------------------------------------------------
# Desktop CMS updates — for logged-in staff only.
# The repository is private, so installed apps cannot download from GitHub.
# The release workflow copies the signed installer, its .sig and latest.json
# to LUXE_DOWNLOADS_DIR/cms on the server; docker-compose mounts that folder
# read-only at LUXE_UPDATES_DIR in this container. Nothing is on the public
# website: every file here needs a valid CMS login (same check as every
# admin route), travels over HTTPS only, and the app installs it only if its
# signature matches the public key built into the app.
# ----------------------------------------------------------------------------
_CMS_UPDATE_FILE = re.compile(r"MusLuxuryCMS_[0-9A-Za-z][0-9A-Za-z._-]*-setup\.exe(?:\.sig)?")

_NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}



def _cms_updates_dir() -> Path:
    return Path(os.getenv("LUXE_UPDATES_DIR", "/var/lib/luxe/updates")) / "cms"



@router.get("/api/v1/admin/updates/cms/latest.json")
def cms_update_manifest(admin: dict = Depends(get_current_admin)):
    """What the installed CMS asks every few hours. 204 = nothing published yet
    (the updater reads it as "no update")."""
    path = _cms_updates_dir() / "latest.json"
    if not path.is_file():
        return Response(status_code=204, headers=_NO_STORE)
    return FileResponse(path, media_type="application/json", headers=_NO_STORE)



@router.get("/api/v1/admin/updates/cms/{filename}")
def cms_update_file(filename: str, admin: dict = Depends(get_current_admin)):
    """A versioned installer or its signature. Only those two kinds of name are
    served, so nothing else in the folder (or outside it) can be reached."""
    if not _CMS_UPDATE_FILE.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    path = _cms_updates_dir() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return FileResponse(path, media_type="application/octet-stream", filename=filename, headers=_NO_STORE)

# ============================================================================
# DATABASE ADMINISTRATION (owner only) — status, backup now, restore,
# "nouvelle base de données". Backup files never leave the server over HTTP.
# Engine: app/backup_engine.py (same code as the nightly job).
# ============================================================================



class OwnerConfirmPayload(BaseModel):
    password: str = Field(..., min_length=1, max_length=256)
    confirm: str = Field(..., min_length=1, max_length=40)



class DatabaseResetPayload(OwnerConfirmPayload):
    keep_settings: bool = True



class BackupCreatePayload(BaseModel):
    include_media: bool = False



def _require_owner(admin: dict) -> int:
    if admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Réservé au propriétaire (super administrateur).")
    return int(admin["sub"])



def _check_owner_password(user_id: int, password: str) -> None:
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM admin_users WHERE id = ? AND is_active = 1", (user_id,))
        row = cur.fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=403, detail="Mot de passe incorrect : opération annulée.")



def _bk_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except _bk.BackupError as exc:
        raise HTTPException(status_code=409, detail=str(exc))



@router.get("/api/v1/admin/system/configuration")
def admin_configuration_status(admin: dict = Depends(require_permission("backups:write"))):
    """Owner only: which .env settings are set, missing or for features not
    built — secret values are never returned (app/settings.py)."""
    _require_owner(admin)
    return app_settings.public_report()



@router.get("/api/v1/admin/system/database")
def admin_database_status(admin: dict = Depends(require_permission("backups:write"))):
    _require_owner(admin)
    return _bk_call(_bk.database_info)



@router.post("/api/v1/admin/system/backups", status_code=201)
def admin_create_backup(payload: BackupCreatePayload, admin: dict = Depends(require_permission("backups:write"))):
    uid = _require_owner(admin)
    meta = _bk_call(_bk.create_backup, "manual", uid, payload.include_media)
    with db_session(commit=True) as conn:
        log_audit(conn, uid, "database_backup", "database", "store", {"backup": meta["name"], "media": bool(meta.get("media"))})
    return meta



@router.get("/api/v1/admin/system/backups/{name}/download")
def admin_download_backup_for_pc(name: str, admin: dict = Depends(require_permission("backups:write"))):
    """The owner's desktop CMS keeps a copy of each backup on the shop PC (the
    VPS disk is small). Owner only, encrypted files only, written to the
    audit log."""
    uid = _require_owner(admin)
    path = _bk_call(_bk.file_for_pc_copy, name)
    with db_session(commit=True) as conn:
        log_audit(conn, uid, "download_backup", "database", "store", {"backup": name})
    return FileResponse(str(path), media_type="application/octet-stream", filename=name,
                        headers={"Cache-Control": "no-store"})



@router.post("/api/v1/admin/system/backups/import", status_code=201)
async def admin_import_backup_from_pc(file: UploadFile = File(...), admin: dict = Depends(require_permission("backups:write"))):
    """A copy kept on the PC is sent back (new server, lost disk); it can then
    be restored like any backup (password + RESTAURER)."""
    uid = _require_owner(admin)
    blob = await file.read(_bk.MAX_IMPORT_BYTES + 1)
    meta = _bk_call(_bk.import_pc_copy, blob, file.filename or "", uid)
    with db_session(commit=True) as conn:
        log_audit(conn, uid, "import_backup", "database", "store", {"backup": meta["name"], "from": meta["imported_from"]})
    return meta



@router.post("/api/v1/admin/system/backups/{name}/restore")
def admin_restore_backup(name: str, payload: OwnerConfirmPayload, admin: dict = Depends(require_permission("backups:write"))):
    uid = _require_owner(admin)
    if payload.confirm.strip().upper() != "RESTAURER":
        raise HTTPException(status_code=400, detail="Tapez RESTAURER pour confirmer.")
    _check_owner_password(uid, payload.password)
    return _bk_call(_bk.restore_backup, name, uid)



@router.post("/api/v1/admin/system/reset")
def admin_reset_database(payload: DatabaseResetPayload, admin: dict = Depends(require_permission("backups:write"))):
    uid = _require_owner(admin)
    if payload.confirm.strip().upper() != "EFFACER":
        raise HTTPException(status_code=400, detail="Tapez EFFACER pour confirmer.")
    _check_owner_password(uid, payload.password)
    return _bk_call(_bk.reset_database, uid, payload.keep_settings)
