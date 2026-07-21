from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import psycopg


APP_DIR = Path(__file__).resolve().parent
SQLITE_PATH = APP_DIR / "accounting_timeline.sqlite3"


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate local SQLite timeline data to Postgres.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing Postgres timeline/change-log rows before migrating.",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL before running this migration.")
    if not SQLITE_PATH.exists():
        raise SystemExit(f"Local SQLite database not found: {SQLITE_PATH}")

    with sqlite3.connect(SQLITE_PATH) as sqlite_conn, psycopg.connect(database_url) as pg_conn:
        _ensure_postgres_schema(pg_conn)
        if args.replace:
            pg_conn.execute("DELETE FROM change_log")
            pg_conn.execute("DELETE FROM timeline_overrides")

        timeline_rows = sqlite_conn.execute(
            """
            SELECT year, month, activity, start_date, end_date, status
            FROM timeline_overrides
            """
        ).fetchall()
        pg_conn.executemany(
            """
            INSERT INTO timeline_overrides (
                year, month, activity, start_date, end_date, status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(year, month, activity) DO UPDATE SET
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                status = excluded.status
            """,
            timeline_rows,
        )

        change_rows = sqlite_conn.execute(
            """
            SELECT changed_at, year, month, activity, field, old_value, new_value, action
            FROM change_log
            ORDER BY id
            """
        ).fetchall()
        pg_conn.executemany(
            """
            INSERT INTO change_log (
                changed_at, year, month, activity, field, old_value, new_value, action
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            change_rows,
        )
        pg_conn.commit()

    print(f"Migrated {len(timeline_rows)} timeline rows and {len(change_rows)} change-log rows.")


def _ensure_postgres_schema(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS timeline_overrides (
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            activity TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (year, month, activity)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS change_log (
            id BIGSERIAL PRIMARY KEY,
            changed_at TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            activity TEXT NOT NULL,
            field TEXT NOT NULL,
            old_value TEXT NOT NULL,
            new_value TEXT NOT NULL,
            action TEXT NOT NULL
        )
        """
    )


if __name__ == "__main__":
    main()
