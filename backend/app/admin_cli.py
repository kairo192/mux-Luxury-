"""
Server-side account recovery for the back office (CMS).

Used when the owner (or the last administrator) has forgotten the password.
It runs ON THE SERVER only, so it needs access to the VPS — nobody can use
it from the internet. Every use is written to the audit log and signs the
account out of every PC.

On the VPS, in the release folder:
    docker compose exec api python -m app.admin_cli list
    docker compose exec api python -m app.admin_cli reset-password --email owner@example.com

The new password is typed twice (hidden) and must have at least 10
characters. For automation, --password-stdin reads it from standard input.
The account is also re-activated if it had been disabled.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from .database import db_session, init_db
from .security import hash_password, revoke_all_user_sessions

MIN_PASSWORD_LENGTH = 10


def _list_admins() -> int:
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT u.id, u.email, u.full_name, u.is_active, r.name AS role
                 FROM admin_users u LEFT JOIN roles r ON r.id = u.role_id
                ORDER BY u.id"""
        )
        rows = cur.fetchall()
    if not rows:
        print("Aucun compte. Ouvrez le CMS : l'assistant de première configuration crée le compte propriétaire.")
        return 0
    for r in rows:
        state = "actif" if int(r["is_active"] or 0) else "DÉSACTIVÉ"
        print(f'{r["id"]:>4}  {r["email"]:<40} {r["role"] or "?":<18} {state:<10} {r["full_name"]}')
    return 0


def _read_new_password(from_stdin: bool) -> str:
    if from_stdin:
        pw = sys.stdin.readline().rstrip("\n")
    else:
        pw = getpass.getpass("Nouveau mot de passe : ")
        again = getpass.getpass("Confirmez le mot de passe : ")
        if pw != again:
            raise SystemExit("Les deux mots de passe sont différents. Rien n'a été modifié.")
    if len(pw) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Mot de passe trop court (au moins {MIN_PASSWORD_LENGTH} caractères). Rien n'a été modifié.")
    return pw


def _reset_password(email: str, from_stdin: bool) -> int:
    email = email.strip().lower()
    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email FROM admin_users WHERE LOWER(email) = ?", (email,))
        user = cur.fetchone()
    if not user:
        raise SystemExit(f"Aucun compte avec l'adresse {email}. Utilisez « list » pour voir les comptes.")

    new_pw = _read_new_password(from_stdin)
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE admin_users SET password_hash = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (hash_password(new_pw), user["id"]),
        )
        revoke_all_user_sessions(int(user["id"]), conn)
        cur.execute(
            "INSERT INTO audit_logs (admin_user_id, action, entity_type, entity_id, details_json) VALUES (?, ?, ?, ?, ?)",
            (None, "reset_admin_password_server", "admin_user", str(user["id"]),
             json.dumps({"via": "server command (admin_cli)", "email": user["email"]})),
        )
    print(f"Mot de passe de {user['email']} changé. Le compte est actif et déconnecté de tous les postes.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin_cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list back-office accounts")
    rp = sub.add_parser("reset-password", help="set a new password for an account")
    rp.add_argument("--email", required=True)
    rp.add_argument("--password-stdin", action="store_true", help="read the new password from standard input")
    args = parser.parse_args(argv)

    init_db()
    if args.cmd == "list":
        return _list_admins()
    return _reset_password(args.email, args.password_stdin)


if __name__ == "__main__":
    raise SystemExit(main())
