#!/usr/bin/env python3
"""
migrate.py — apply pending SQL schema migrations, in order, with tracking.

The project had no migration runner: the SQL files in migrations/ were applied
by hand. This applies them deterministically (needed for a repeatable deploy)
and records which have run in a `schema_migrations` table, so re-running is safe
and idempotent.

Usage (run from the pythonBackend directory):

    python migrate.py                 # apply all pending migrations
    python migrate.py up              # same
    python migrate.py up --dry-run    # list what would apply; change nothing
    python migrate.py status          # show applied vs pending
    python migrate.py baseline        # record all current .sql as applied,
                                      #   WITHOUT running them

Adopting the runner on a DB that already has migrations applied by hand
--------------------------------------------------------------------
Your existing local/prod DB already has 001–004 applied. Running `up` there
would try to re-run them (and some, e.g. 001's ADD CONSTRAINT, are not
idempotent and would error). Run `baseline` ONCE on such a DB first: it stamps
every current .sql as already-applied. After that, `up` only applies migrations
added later. On a brand-new empty DB, skip baseline and just run `up`.

Conventions
-----------
* Ordering is lexical by filename — keep the zero-padded numeric prefix
  (001_, 002_, …).
* Each file is executed as a single script, so a file that changes more than
  one thing MUST wrap itself in `BEGIN; … COMMIT;` for atomicity (as 001/002
  do). The runner records success immediately after the file applies.
* `.py` data migrations (e.g. 004_purge_legacy_gear.py) are NOT run by this
  tool — they need the Python resolver and are run separately. They are listed
  under `status` as a reminder.
"""

import argparse
import glob
import os
import sys

import psycopg

from DBConnection import _conn_kwargs

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")

_TRACKING_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text        PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def _connect():
    # A dedicated autocommit connection (not the app pool): migrations are a
    # one-shot admin task, and autocommit lets each file's own BEGIN/COMMIT be
    # authoritative for its transaction.
    return psycopg.connect(**_conn_kwargs(), autocommit=True)


def _discover_sql() -> list[str]:
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    return [os.path.basename(f) for f in files]


def _discover_py() -> list[str]:
    out = []
    for f in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.py"))):
        name = os.path.basename(f)
        if name != "__init__.py":
            out.append(name)
    return out


def _ensure_tracking(cur) -> None:
    cur.execute(_TRACKING_DDL)


def _applied(cur) -> dict:
    cur.execute("SELECT version, applied_at FROM schema_migrations ORDER BY version")
    return {r["version"]: r["applied_at"] for r in cur.fetchall()}


def cmd_status() -> None:
    with _connect() as conn, conn.cursor() as cur:
        _ensure_tracking(cur)
        applied = _applied(cur)
    on_disk = _discover_sql()
    pending = [n for n in on_disk if n not in applied]
    orphans = [v for v in applied if v not in on_disk]

    print("Applied:")
    for name in on_disk:
        if name in applied:
            print(f"  [x] {name}   ({applied[name]:%Y-%m-%d %H:%M})")
    if not any(n in applied for n in on_disk):
        print("  (none)")

    print("\nPending:")
    print("\n".join(f"  [ ] {n}" for n in pending) if pending else "  (none — up to date)")

    if orphans:
        print("\nRecorded but not on disk (renamed/removed?):")
        for v in orphans:
            print(f"  [?] {v}")

    py = _discover_py()
    if py:
        print("\nManual data migrations (run separately - NOT handled here):")
        for name in py:
            print(f"  -  {name}")


def cmd_up(dry_run: bool = False) -> None:
    with _connect() as conn, conn.cursor() as cur:
        _ensure_tracking(cur)
        applied = _applied(cur)
        pending = [n for n in _discover_sql() if n not in applied]

        if not pending:
            print("Up to date — no pending migrations.")
            return

        print(f"{len(pending)} pending migration(s):")
        for name in pending:
            print(f"  {'[dry-run] ' if dry_run else ''}{name}")
        if dry_run:
            print("\nDry run — nothing applied.")
            return

        for name in pending:
            with open(os.path.join(MIGRATIONS_DIR, name), "r", encoding="utf-8") as fh:
                sql = fh.read()
            print(f"\nApplying {name} …")
            try:
                cur.execute(sql)
            except Exception as e:
                print(f"  ! FAILED: {e}")
                print("Stopping. Earlier migrations are recorded; fix this one and re-run.")
                sys.exit(1)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                (name,),
            )
            print("  [ok] applied")
    print("\nDone.")


def cmd_baseline() -> None:
    on_disk = _discover_sql()
    with _connect() as conn, conn.cursor() as cur:
        _ensure_tracking(cur)
        for name in on_disk:
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                (name,),
            )
    print(f"Baselined {len(on_disk)} migration(s) as already applied:")
    for name in on_disk:
        print(f"  [x] {name}")
    print("\n`migrate.py up` will now only apply migrations added after this point.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply pending SQL schema migrations.")
    ap.add_argument(
        "command",
        nargs="?",
        default="up",
        choices=["up", "status", "baseline"],
        help="up (default): apply pending · status: report · baseline: record all current .sql as applied",
    )
    ap.add_argument("--dry-run", action="store_true", help="(up only) list what would apply; change nothing.")
    args = ap.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "baseline":
        cmd_baseline()
    else:
        cmd_up(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
