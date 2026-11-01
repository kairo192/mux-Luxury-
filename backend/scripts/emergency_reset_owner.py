#!/usr/bin/env python3
"""
Mus Luxury (LUXE) — Server-Side CLI Emergency Owner Password & Recovery Code Reset Utility.
Usage on VPS or Docker container:
  python3 backend/scripts/emergency_reset_owner.py --email admin@musluxury.dz --new-password "NewStrongPassword2026!"
"""
import argparse
import hashlib
import os
import secrets
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import db_session, init_db
from app.security import hash_password


def reset_owner_credentials(email: str, new_password: str) -> dict:
    if len(new_password) < 10:
        raise ValueError("New password must be at least 10 characters long.")
    init_db()
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin_users WHERE email = ?", (email.strip().lower(),))
        user = cur.fetchone()
        if not user:
            raise RuntimeError(f"Administrator account '{email}' not found.")

        pw_hash = hash_password(new_password)
        cur.execute(
            "UPDATE admin_users SET password_hash = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (pw_hash, user["id"]),
        )
        emergency_code = f"LUXE-EMERG-{secrets.token_hex(6).upper()}"
        code_hash = hashlib.sha256(emergency_code.encode("utf-8")).hexdigest()
        cur.execute(
            "UPDATE admin_recovery_codes SET is_used = 1 WHERE admin_user_id = ? AND channel = 'offline_emergency'",
            (user["id"],),
        )
        cur.execute(
            """INSERT INTO admin_recovery_codes (admin_user_id, phone, code_hash, channel, max_attempts, expires_at)
               VALUES (?, ?, ?, 'offline_emergency', 3, ?)""",
            (user["id"], user["emergency_phone"] or user["phone"], code_hash, int(time.time()) + 86400 * 365),
        )
        return {
            "admin_id": user["id"],
            "email": user["email"],
            "new_emergency_code": emergency_code,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Emergency Owner Password Reset")
    parser.add_argument("--email", default="admin@musluxury.dz", help="Administrator email")
    parser.add_argument("--new-password", required=True, help="New password (>= 10 chars)")
    args = parser.parse_args()
    info = reset_owner_credentials(args.email, args.new_password)
    print(f"[OK] Password updated for {info['email']} (ID #{info['admin_id']}).")
    print(f"[OK] New Offline Emergency Code: {info['new_emergency_code']}")
