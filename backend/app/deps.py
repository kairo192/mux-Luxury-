"""Login and permission checks used by every admin route (FastAPI dependencies)."""
import json
from typing import List, Optional
from fastapi import Depends, Header, HTTPException, status
from .database import db_session
from .security import decode_access_token



# ============================================================================
# AUTHENTICATION & RBAC DEPENDENCIES
# ============================================================================

def get_current_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connexion requise.")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    uid = int(payload.get("sub") or 0)
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = ?", (f"session_revoked_ns:{uid}",))
        rev_row = cur.fetchone()
        if rev_row and int(payload.get("iat_ns") or 0) < int(rev_row["setting_value"] or 0):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée. Reconnectez-vous.")
        # Permissions are read from the database on every request, not trusted
        # from the token: a role change, a deactivation or a permission added
        # by an update applies at once, without logging out.
        cur.execute(
            """SELECT u.is_active, r.name AS role_name
               FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""",
            (uid,),
        )
        user_row = cur.fetchone()
        if not user_row or not int(user_row["is_active"] or 0):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée. Reconnectez-vous.")
        cur.execute(
            """SELECT p.code FROM permissions p
               JOIN role_permissions rp ON rp.permission_id = p.id
               JOIN admin_users u ON u.role_id = rp.role_id
               WHERE u.id = ?""",
            (uid,),
        )
        payload["perms"] = [r["code"] for r in cur.fetchall()]
        payload["role"] = user_row["role_name"]
    payload["raw_token"] = token
    return payload


def require_permission(perm: str):
    def dep(admin: dict = Depends(get_current_admin)) -> dict:
        if perm not in admin.get("perms", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre rôle ne permet pas cette action."
            )
        return admin
    return dep


def require_any_permission(perms: List[str]):
    def dep(admin: dict = Depends(get_current_admin)) -> dict:
        granted = admin.get("perms", [])
        if not any(p in granted for p in perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre rôle ne permet pas cette action."
            )
        return admin
    return dep


def log_audit(conn, admin_user_id: Optional[int], action: str, entity_type: str, entity_id: str, details: dict):
    conn.execute(
        "INSERT INTO audit_logs (admin_user_id, action, entity_type, entity_id, details_json) VALUES (?, ?, ?, ?, ?)",
        (admin_user_id, action, entity_type, str(entity_id), json.dumps(details, ensure_ascii=False))
    )
