"""Grant or revoke the admin flag for an existing Sthalo user.

Usage:
    backend/.venv/bin/python backend/scripts/make_admin.py --email owner@example.com
    backend/.venv/bin/python backend/scripts/make_admin.py --email owner@example.com --revoke
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of an existing Sthalo user")
    parser.add_argument("--revoke", action="store_true", help="Remove admin access")
    return parser.parse_args()


async def update_admin(email: str, *, grant: bool) -> int:
    settings = Settings(_env_file=ENV_FILE)
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(dsn)
    try:
        row = await connection.fetchrow(
            "SELECT id, email, is_admin FROM sthalo.users WHERE lower(email) = lower($1)",
            email,
        )
        if row is None:
            print(f"No Sthalo user exists for {email}", file=sys.stderr)
            return 2
        if bool(row["is_admin"]) == grant:
            state = "admin" if grant else "non-admin"
            print(f"{row['email']} is already {state}; no changes made.")
            return 0

        transaction = connection.transaction()
        await transaction.start()
        try:
            await connection.execute(
                "UPDATE sthalo.users SET is_admin = $2 WHERE id = $1",
                row["id"],
                grant,
            )
            await connection.execute(
                """
                INSERT INTO sthalo.audit_events
                    (actor_type, action, entity_type, entity_id, before, after, request_id)
                VALUES
                    ('system', $1, 'user', $2, $3::jsonb, $4::jsonb, 'make_admin')
                """,
                "admin.granted" if grant else "admin.revoked",
                row["id"],
                json.dumps({"is_admin": bool(row["is_admin"])}),
                json.dumps({"is_admin": grant}),
            )
            await transaction.commit()
        except BaseException:
            await transaction.rollback()
            raise
        print(f"{'Granted' if grant else 'Revoked'} admin access for {row['email']}.")
        return 0
    finally:
        await connection.close()


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(update_admin(args.email, grant=not args.revoke)))


if __name__ == "__main__":
    main()
