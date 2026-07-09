"""
SQLite database layer for deployment metadata.
No ORM — straightforward SQL with parameterized queries.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if not exist. Called on startup."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deployments (
                id            TEXT PRIMARY KEY,
                name          TEXT,
                url_path      TEXT NOT NULL,
                source_zip    TEXT NOT NULL,
                file_count    INTEGER NOT NULL,
                total_size    INTEGER NOT NULL,
                created_at    TEXT NOT NULL,
                deleted_at    TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deployments_created "
            "ON deployments(created_at DESC)"
        )
        conn.commit()


def insert_deployment(
    deploy_id: str,
    name: str | None,
    url_path: str,
    source_zip: str,
    file_count: int,
    total_size: int,
) -> dict[str, Any]:
    """Insert a deployment record and return it as a dict."""
    created_at = _utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO deployments (id, name, url_path, source_zip, file_count, total_size, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (deploy_id, name, url_path, source_zip, file_count, total_size, created_at),
        )
        conn.commit()
    return {
        "id": deploy_id,
        "name": name,
        "url_path": url_path,
        "url": f"{config.PUBLIC_BASE_URL.rstrip('/')}{url_path}",
        "source_zip": source_zip,
        "file_count": file_count,
        "total_size": total_size,
        "created_at": created_at,
    }


def get_deployment(deploy_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM deployments WHERE id = ? AND deleted_at IS NULL",
            (deploy_id,),
        ).fetchone()
    return dict(row) if row else None


def list_deployments(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM deployments WHERE deleted_at IS NULL "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_deployments() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM deployments WHERE deleted_at IS NULL"
        ).fetchone()
    return row["cnt"]


def delete_deployment(deploy_id: str) -> bool:
    """Hard-delete the DB record. Returns True if a row was deleted."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM deployments WHERE id = ?", (deploy_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    # Augment with full URL
    d["url"] = f"{config.PUBLIC_BASE_URL.rstrip('/')}{d['url_path']}"
    return d
