"""Operational CLI. Run via: ``docker compose exec plantpal python -m plantpal.cli <cmd>``.

All operational DB writes go through here, never raw SQL in a shell. Each command
prints a usable magic link to stdout so the admin is never locked out even if the
email provider is down.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import auth_service
from .config import get_settings
from .db import init_db
from .errors import AppError


async def _maybe_send(
    settings, email: str, url: str, kind: str, send: bool, code: str | None = None
) -> None:
    """Best-effort email send; never fatal (the printed link always works)."""
    if not send:
        return
    try:
        from . import email_service  # lazy: available from Phase 4 onward

        if kind == "invite":
            await email_service.send_invite(settings, email, url)
        else:
            await email_service.send_magic_link(settings, email, url, code)
        print("  (email sent)")
    except Exception as exc:  # noqa: BLE001 — operational tool, surface + continue
        print(f"  (email send failed: {exc} — use the link above)")


async def _bootstrap_admin(email: str, force: bool, send: bool) -> int:
    settings = get_settings()
    db = await init_db(settings)
    try:
        user_id, raw = await auth_service.bootstrap_admin(db, settings, email, force=force)
        url = auth_service.login_url(settings, raw)
        print(f"Admin user #{user_id} ready: {email}")
        print(f"Login link: {url}")
        await _maybe_send(settings, email, url, "login", send)
        return 0
    finally:
        await db.close()


async def _issue_login_link(email: str, send: bool) -> int:
    settings = get_settings()
    db = await init_db(settings)
    try:
        issued = await auth_service.request_login_link(db, settings, email)
        if issued is None:
            print(f"No active user for {email!r}.", file=sys.stderr)
            return 1
        raw, code = issued
        url = auth_service.login_url(settings, raw)
        print(f"Login link for {email}: {url}")
        print(f"Login code: {code}")
        await _maybe_send(settings, email, url, "login", send, code)
        return 0
    finally:
        await db.close()


async def _create_invite(created_by: str | None, email_hint: str | None, send: bool) -> int:
    settings = get_settings()
    db = await init_db(settings)
    try:
        creator_id = None
        if created_by:
            user = await auth_service.get_user_by_email(db, created_by)
            if user is None or not user["is_admin"]:
                print(f"{created_by!r} is not an admin.", file=sys.stderr)
                return 1
            creator_id = user["id"]
        raw = await auth_service.create_invite(db, settings, creator_id, email_hint)
        url = auth_service.register_url(settings, raw)
        print(f"Invite link: {url}")
        if email_hint:
            await _maybe_send(settings, email_hint, url, "invite", send)
        return 0
    finally:
        await db.close()


async def _revoke_sessions(email: str) -> int:
    settings = get_settings()
    db = await init_db(settings)
    try:
        user = await auth_service.get_user_by_email(db, email)
        if user is None:
            print(f"No user for {email!r}.", file=sys.stderr)
            return 1
        n = await auth_service.revoke_user_sessions(db, user["id"])
        print(f"Revoked {n} session(s) for {email}.")
        return 0
    finally:
        await db.close()


def _backup(out: str, db_path: str | None = None) -> int:
    """Online, WAL-consistent SQLite backup via sqlite3.Connection.backup (K5: no sqlite3 CLI)."""
    import sqlite3

    src = sqlite3.connect(db_path or get_settings().DB_PATH)
    try:
        dest = sqlite3.connect(out)
        try:
            src.backup(dest)
        finally:
            dest.close()
        print(f"Backup written to {out}")
        return 0
    finally:
        src.close()


async def _set_invite_quota(email: str, quota: int) -> int:
    settings = get_settings()
    db = await init_db(settings)
    try:
        if await auth_service.set_invite_quota(db, email, quota):
            print(f"Set invite quota for {email} to {quota}.")
            return 0
        print(f"No user for {email!r}.", file=sys.stderr)
        return 1
    finally:
        await db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plantpal", description="PlantPal admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bootstrap-admin", help="Create or promote the first admin")
    p.add_argument("--email", required=True)
    p.add_argument("--force", action="store_true", help="Allow even if an admin exists")
    p.add_argument("--send", action="store_true", help="Also email the magic link")

    p = sub.add_parser("issue-login-link", help="Issue a magic link (Resend-outage fallback)")
    p.add_argument("--email", required=True)
    p.add_argument("--send", action="store_true")

    p = sub.add_parser("create-invite", help="Generate an invite token")
    p.add_argument("--created-by", help="Admin email that owns this invite")
    p.add_argument("--email-hint")
    p.add_argument("--send", action="store_true")

    p = sub.add_parser("revoke-sessions", help="Force-logout all sessions of a user")
    p.add_argument("--email", required=True)

    p = sub.add_parser("set-invite-quota", help="Set a user's invite quota")
    p.add_argument("--email", required=True)
    p.add_argument("--quota", type=int, required=True)

    p = sub.add_parser("backup", help="Write a consistent SQLite backup to --out")
    p.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "bootstrap-admin":
            return asyncio.run(_bootstrap_admin(args.email, args.force, args.send))
        if args.command == "issue-login-link":
            return asyncio.run(_issue_login_link(args.email, args.send))
        if args.command == "create-invite":
            return asyncio.run(_create_invite(args.created_by, args.email_hint, args.send))
        if args.command == "revoke-sessions":
            return asyncio.run(_revoke_sessions(args.email))
        if args.command == "set-invite-quota":
            return asyncio.run(_set_invite_quota(args.email, args.quota))
        if args.command == "backup":
            return _backup(args.out)
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
