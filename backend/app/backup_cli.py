"""
Command line for the backup engine (used by the nightly job and by operators).

On the VPS, run it inside the API container so it uses the same database
connection, key and backup folder as the CMS:

    docker exec luxe_api python -m app.backup_cli create --kind nightly --media
    docker exec luxe_api python -m app.backup_cli list
    docker exec luxe_api python -m app.backup_cli verify  luxe_app_nightly_20261111_023000_ab12.json.gz.enc
    docker exec luxe_api python -m app.backup_cli restore luxe_app_nightly_20261111_023000_ab12.json.gz.enc --yes

On a PC running the backend locally:   cd backend && python -m app.backup_cli list

Every command prints one JSON document; exit code 0 = success, 1 = failure.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import backup_engine as engine


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.backup_cli", description="Mus Luxury backups")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="take a backup now")
    p_create.add_argument("--kind", default="manual", help="nightly | manual | pre-update ...")
    p_create.add_argument("--media", action="store_true", help="also archive product photos")

    sub.add_parser("list", help="list backups")
    sub.add_parser("info", help="database + backup status")

    p_verify = sub.add_parser("verify", help="decrypt and read a backup without restoring it")
    p_verify.add_argument("name")

    p_restore = sub.add_parser("restore", help="replace the database with a backup (takes a safety backup first)")
    p_restore.add_argument("name")
    p_restore.add_argument("--yes", action="store_true", help="confirm")

    p_reset = sub.add_parser("reset", help="empty the store (takes a safety backup first)")
    p_reset.add_argument("--yes", action="store_true", help="confirm")
    p_reset.add_argument("--wipe-settings", action="store_true", help="also clear store settings and homepage layout")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "create":
            out = engine.create_backup(kind=args.kind, include_media=args.media)
        elif args.cmd == "list":
            out = engine.list_backups()
        elif args.cmd == "info":
            out = engine.database_info()
        elif args.cmd == "verify":
            out = engine.verify_backup(args.name)
        elif args.cmd == "restore":
            if not args.yes:
                raise engine.BackupError("Add --yes to confirm the restore.")
            out = engine.restore_backup(args.name)
        elif args.cmd == "reset":
            if not args.yes:
                raise engine.BackupError("Add --yes to confirm the reset.")
            out = engine.reset_database(keep_settings=not args.wipe_settings)
        else:  # pragma: no cover
            parser.error("unknown command")
            return 2
    except Exception as exc:  # report, never print a traceback with data in it
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
