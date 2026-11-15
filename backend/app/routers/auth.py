"""Staff login, sessions, users, roles and protected actions."""
from fastapi import APIRouter
from .. import settings as app_settings
import re
from typing import Dict, List, Optional
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, validator
from ..database import db_session
from ..security import check_rate_limit, get_real_client_ip, create_access_token, hash_password as _hash_pw_init, revoke_token, verify_password
from ..security import hash_password, revoke_all_user_sessions
from ..security import verify_signed_request
from ..deps import (
    get_current_admin,
    log_audit,
    require_permission,
)
from ..common import (
    _EMAIL_RE,
)

router = APIRouter()



_DUMMY_PASSWORD_HASH = _hash_pw_init("luxe_constant_time_dummy_mitigation_2026!")


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str



# Login attempts allowed per minute and per IP address (brute-force guard).
# Default 5. The browser tests raise it (they log in many times from one
# machine); it can never exceed 30, and in production nginx limits logins to
# 5 per minute in front of the API anyway (zone auth_limit).
# LOGIN_ATTEMPTS_PER_MINUTE (older name MAX_LOGIN_ATTEMPTS_PER_MINUTE).
_LOGIN_ATTEMPTS_PER_MINUTE = app_settings.get_int("LOGIN_ATTEMPTS_PER_MINUTE", 1, 30)



@router.post("/api/v1/admin/auth/login")
def admin_login(payload: LoginRequest, request: Request):
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"login:{client_ip}", max_requests=_LOGIN_ATTEMPTS_PER_MINUTE, window_seconds=60)

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT u.*, r.name AS role_name
               FROM admin_users u
               JOIN roles r ON r.id = u.role_id
               WHERE u.email = ? AND u.is_active = 1""",
            (payload.email.strip().lower(),)
        )
        user = cur.fetchone()
        candidate_hash = user["password_hash"] if user else _DUMMY_PASSWORD_HASH
        pw_ok = verify_password(payload.password, candidate_hash)
        if not user or not pw_ok:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        cur.execute(
            """SELECT p.code FROM permissions p
               JOIN role_permissions rp ON rp.permission_id = p.id
               WHERE rp.role_id = ?""",
            (user["role_id"],)
        )
        perms = [r["code"] for r in cur.fetchall()]
        token = create_access_token(user["id"], user["email"], user["role_name"], perms)
        cur.execute("UPDATE admin_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
        log_audit(conn, user["id"], "admin_login", "admin_user", str(user["id"]), {"email": user["email"]})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role_name"],
                "permissions": perms,
            }
        }


@router.post("/api/v1/admin/auth/logout")
def admin_logout(admin: dict = Depends(get_current_admin)):
    revoke_token(admin["raw_token"])
    return {"status": "logged_out"}




# ============================================================================
# FIRST-TIME ONE-TIME OWNER INITIALIZATION & PERMANENT LOCKOUT
# ============================================================================

class OwnerInitializeInput(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=150)
    email: str = Field(..., min_length=5, max_length=150)
    password: str = Field(..., min_length=10, max_length=128)
    whatsapp_phone: Optional[str] = None
    emergency_phone: Optional[str] = None

    @validator("whatsapp_phone", "emergency_phone")
    def validate_phones(cls, v):
        if not v:
            return None
        cleaned = re.sub(r"[\s\-\.]", "", v)
        if not re.match(r"^(\+213|0)(5|6|7)[0-9]{8}$", cleaned):
            raise ValueError("Numéro de mobile algérien invalide (il doit commencer par 05, 06, 07 ou +213)")
        return cleaned


@router.get("/api/v1/admin/auth/setup-status")
def get_admin_setup_status():
    """
    Checks whether the primary Super Administrator (Owner) has already been provisioned.
    When true, all PCs opening the CMS directly display the Login and Forgot Password screen.
    """
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM store_settings WHERE setting_key = 'system_initialized'")
        init_row = cur.fetchone()
        is_init = init_row and init_row["setting_value"] == "true"
        if not is_init:
            cur.execute("SELECT COUNT(*) AS cnt FROM admin_users WHERE role_id = (SELECT id FROM roles WHERE name = 'super_admin')")
            is_init = cur.fetchone()["cnt"] > 0
        return {
            "is_initialized": is_init,
            "requires_owner_setup": not is_init,
            "store_name": "Mus Luxury (LUXE)"
        }


@router.post("/api/v1/admin/auth/initialize-owner", status_code=201)
def initialize_primary_owner(payload: OwnerInitializeInput, request: Request):
    """
    First-Time Provisioning Endpoint:
    Allows the store owner to configure their username, email, password, primary recovery WhatsApp number,
    and a second emergency phone number.
    SECURITY LOCKOUT: Once called and saved to PostgreSQL, this endpoint is PERMANENTLY LOCKED (HTTP 403).
    Even if the CMS application starts on another PC, it detects system_initialized = true
    and goes straight to the normal Login & Forgot Password screen.
    """
    client_ip = get_real_client_ip(request)
    check_rate_limit(f"init_owner:{client_ip}", max_requests=3, window_seconds=300)

    already_done = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Le compte propriétaire existe déjà : la première configuration n'est plus possible."
    )
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        # Claim the one-time marker FIRST, in this transaction. Two requests sent
        # at the same moment cannot both pass: the second waits on the marker's
        # row and then changes nothing (0 rows), on SQLite and PostgreSQL alike.
        # If anything below fails, the rollback releases the claim.
        cur.execute(
            """INSERT INTO store_settings (setting_key, setting_value, updated_at)
               VALUES ('system_initialized', 'true', CURRENT_TIMESTAMP)
               ON CONFLICT(setting_key) DO UPDATE SET setting_value = 'true', updated_at = CURRENT_TIMESTAMP
               WHERE store_settings.setting_value <> 'true'"""
        )
        is_init = cur.rowcount != 1
        if not is_init:
            cur.execute("SELECT COUNT(*) AS cnt FROM admin_users WHERE role_id = (SELECT id FROM roles WHERE name = 'super_admin')")
            is_init = cur.fetchone()["cnt"] > 0
        if is_init:
            raise already_done

        cur.execute("SELECT id FROM roles WHERE name = 'super_admin'")
        role_row = cur.fetchone()
        super_role_id = role_row["id"] if role_row else 1

        email_clean = payload.email.strip().lower()
        cur.execute("SELECT id FROM admin_users WHERE email = ?", (email_clean,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="An administrator with this email already exists")

        pw_hash = hash_password(payload.password)
        cur.execute(
            """INSERT INTO admin_users
               (email, full_name, phone, emergency_phone, whatsapp_verified, totp_enabled, password_hash, role_id, is_active)
               VALUES (?, ?, ?, ?, 1, 1, ?, ?, 1)""",
            (email_clean, payload.full_name.strip(), payload.whatsapp_phone, payload.emergency_phone, pw_hash, super_role_id)
        )
        owner_id = cur.lastrowid

        # No "emergency code": nothing could ever use one (the WhatsApp
        # recovery flow was removed). A forgotten password is reset on the
        # server: `python -m app.admin_cli reset-password --email ...`.

        cur.execute(
            """SELECT p.code FROM permissions p
               JOIN role_permissions rp ON rp.permission_id = p.id
               WHERE rp.role_id = ?""",
            (super_role_id,)
        )
        perms = [r["code"] for r in cur.fetchall()]
        token = create_access_token(owner_id, email_clean, "super_admin", perms)

        log_audit(conn, owner_id, "first_time_owner_initialized", "admin_user", str(owner_id), {
            "email": email_clean,
            "whatsapp_phone": payload.whatsapp_phone,
            "emergency_phone": payload.emergency_phone
        })

        return {
            "initialized": True,
            "message": "Super Administrator successfully provisioned. Setup is permanently locked.",
            "password_recovery": "server: python -m app.admin_cli reset-password --email <email>",
            "access_token": token,
            "user": {
                "id": owner_id,
                "email": email_clean,
                "full_name": payload.full_name.strip(),
                "role": "super_admin",
                "permissions": perms,
                "whatsapp_phone": payload.whatsapp_phone,
                "emergency_phone": payload.emergency_phone
            }
        }


@router.post("/api/v1/admin/secure-action")
async def execute_cryptographically_signed_action(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """
    Cryptographically signed administrative endpoint:
    Enforces HMAC-SHA256 signature verification over (method, path, timestamp, nonce, body_sha256).
    Rejects any replay attacks, expired timestamps, or tampered payloads.
    """
    body_bytes = await request.body()
    sig = request.headers.get("X-Luxe-Signature")
    ts = request.headers.get("X-Luxe-Timestamp")
    nonce = request.headers.get("X-Luxe-Nonce")
    verify_signed_request(request.method, request.url.path, body_bytes, sig, ts, nonce)
    return {"status": "verified_and_executed", "admin_id": admin["sub"], "nonce": nonce}



class AdminUserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=32)
    role_id: int
    password: str = Field(..., min_length=10, max_length=128)

    @validator("email")
    def _email(cls, v):
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Adresse e-mail invalide")
        return v



class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=32)
    role_id: Optional[int] = None
    is_active: Optional[bool] = None



class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=10, max_length=128)



def _role_name(conn, role_id: int) -> Optional[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM roles WHERE id = ?", (role_id,))
    r = cur.fetchone()
    return r["name"] if r else None



def _count_other_active_super_admins(conn, exclude_user_id: int) -> int:
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(*) AS c FROM admin_users u JOIN roles r ON r.id = u.role_id
           WHERE r.name = 'super_admin' AND u.is_active = 1 AND u.id != ?""",
        (exclude_user_id,),
    )
    return int(cur.fetchone()["c"])



@router.get("/api/v1/admin/roles")
def admin_list_roles(admin: dict = Depends(require_permission("settings:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description FROM roles ORDER BY id")
        roles = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """SELECT rp.role_id, p.code FROM role_permissions rp JOIN permissions p ON p.id = rp.permission_id
               ORDER BY rp.role_id, p.code"""
        )
        codes_by_role: Dict[int, List[str]] = {}
        for r in cur.fetchall():
            codes_by_role.setdefault(r["role_id"], []).append(r["code"])
        for role in roles:
            role["permissions"] = codes_by_role.get(role["id"], [])
        return {"items": roles}



@router.get("/api/v1/admin/users")
def admin_list_users(admin: dict = Depends(require_permission("settings:write"))):
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, u.last_login_at, u.created_at,
                      r.id AS role_id, r.name AS role_name
               FROM admin_users u JOIN roles r ON r.id = u.role_id
               ORDER BY u.id"""
        )
        return {"items": [dict(r) for r in cur.fetchall()]}



@router.post("/api/v1/admin/users", status_code=201)
def admin_create_user(payload: AdminUserCreate, admin: dict = Depends(require_permission("settings:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        if not _role_name(conn, payload.role_id):
            raise HTTPException(status_code=404, detail="Rôle introuvable")
        cur.execute("SELECT id FROM admin_users WHERE email = ?", (payload.email,))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un utilisateur avec cet e-mail existe déjà")
        cur.execute(
            """INSERT INTO admin_users (email, full_name, phone, password_hash, role_id, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (payload.email, payload.full_name, payload.phone, hash_password(payload.password), payload.role_id),
        )
        uid = cur.lastrowid
        log_audit(conn, int(admin["sub"]), "create_admin_user", "admin_user", str(uid), {
            "email": payload.email, "role_id": payload.role_id,
        })
        cur.execute(
            """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, u.created_at, r.id AS role_id, r.name AS role_name
               FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""",
            (uid,),
        )
        return dict(cur.fetchone())



@router.put("/api/v1/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: AdminUserUpdate, admin: dict = Depends(require_permission("settings:write"))):
    with db_session(commit=True) as conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        cur.execute(
            "SELECT u.*, r.name AS role_name FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?",
            (user_id,),
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

        is_self = int(admin["sub"]) == user_id
        was_super = user["role_name"] == "super_admin"

        # Resolve target role & active state after the update
        new_role_id = payload.role_id if payload.role_id is not None else user["role_id"]
        new_active = payload.is_active if payload.is_active is not None else bool(user["is_active"])
        new_role_name = _role_name(conn, new_role_id)
        if new_role_name is None:
            raise HTTPException(status_code=404, detail="Rôle introuvable")

        # Guard: never lock the business out of its last active super admin.
        if was_super and (new_role_name != "super_admin" or not new_active):
            if _count_other_active_super_admins(conn, user_id) == 0:
                raise HTTPException(status_code=400, detail="Impossible : c'est le dernier super administrateur actif")
        # Guard: an admin cannot deactivate their own account.
        if is_self and payload.is_active is False:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")

        sets, params = [], []
        if payload.full_name is not None:
            sets.append("full_name = ?"); params.append(payload.full_name)
        if payload.phone is not None:
            sets.append("phone = ?"); params.append(payload.phone)
        if payload.role_id is not None:
            sets.append("role_id = ?"); params.append(payload.role_id)
        if payload.is_active is not None:
            sets.append("is_active = ?"); params.append(1 if payload.is_active else 0)
        if not sets:
            cur.execute(
                """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, r.id AS role_id, r.name AS role_name
                   FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""", (user_id,))
            return dict(cur.fetchone())
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        cur.execute(f"UPDATE admin_users SET {', '.join(sets)} WHERE id = ?", tuple(params))

        # Role/status changes take effect immediately: revoke the target's sessions.
        if payload.role_id is not None or payload.is_active is not None:
            revoke_all_user_sessions(user_id, conn)
        log_audit(conn, int(admin["sub"]), "update_admin_user", "admin_user", str(user_id), {
            "role_id": new_role_id, "is_active": new_active,
        })
        cur.execute(
            """SELECT u.id, u.email, u.full_name, u.phone, u.is_active, r.id AS role_id, r.name AS role_name
               FROM admin_users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?""", (user_id,))
        return dict(cur.fetchone())



@router.post("/api/v1/admin/users/{user_id}/reset-password")
def admin_reset_user_password(user_id: int, payload: AdminPasswordReset, admin: dict = Depends(require_permission("settings:write"))):
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email FROM admin_users WHERE id = ?", (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        cur.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (hash_password(payload.new_password), user_id),
        )
        revoke_all_user_sessions(user_id, conn)
        log_audit(conn, int(admin["sub"]), "reset_admin_password", "admin_user", str(user_id), {"email": user["email"]})
        return {"id": user_id, "email": user["email"], "password_reset": True}
