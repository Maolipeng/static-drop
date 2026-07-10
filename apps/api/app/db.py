"""SQLite persistence for projects and immutable deployment versions."""

from __future__ import annotations

import re
import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from . import config


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_connection() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "project"


def _unique_slug(conn: sqlite3.Connection, name: str, project_id: str) -> str:
    base = _slugify(name)
    slug = base
    suffix = 2
    while conn.execute(
        "SELECT 1 FROM projects WHERE slug = ? AND id != ?", (slug, project_id)
    ).fetchone():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def _migrate_existing_deployments(conn: sqlite3.Connection) -> None:
    """Give pre-project deployments a one-project/one-version identity."""
    rows = conn.execute(
        "SELECT id, name, source_zip FROM deployments WHERE project_id IS NULL"
    ).fetchall()
    for row in rows:
        project_id = "prj_" + uuid.uuid4().hex
        name = row["name"] or row["source_zip"] or project_id
        slug = _unique_slug(conn, name, project_id)
        now = _utc_now_iso()
        conn.execute(
            """
            INSERT INTO projects (id, name, slug, current_deployment_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, name, slug, row["id"], now, now),
        )
        conn.execute(
            "UPDATE deployments SET project_id = ?, version = 1 WHERE id = ?",
            (project_id, row["id"]),
        )


def init_db() -> None:
    """Create the project schema and migrate the original deployment-only schema."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id                    TEXT PRIMARY KEY,
                name                  TEXT NOT NULL,
                slug                  TEXT NOT NULL UNIQUE,
                owner_id              TEXT,
                current_deployment_id TEXT,
                created_at            TEXT NOT NULL,
                updated_at            TEXT NOT NULL,
                deleted_at            TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL,
                disabled_at   TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS domains (
                id                 TEXT PRIMARY KEY,
                project_id         TEXT NOT NULL,
                domain             TEXT NOT NULL UNIQUE,
                verification_token TEXT NOT NULL,
                verified_at        TEXT,
                created_at         TEXT NOT NULL,
                active             INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        if not _has_column(conn, "projects", "owner_id"):
            conn.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT")
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
                deleted_at    TEXT,
                project_id    TEXT,
                version       INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        if not _has_column(conn, "deployments", "project_id"):
            conn.execute("ALTER TABLE deployments ADD COLUMN project_id TEXT")
        if not _has_column(conn, "deployments", "version"):
            conn.execute("ALTER TABLE deployments ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deployments_created ON deployments(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deployments_project ON deployments(project_id, version DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC)")
        _migrate_existing_deployments(conn)
        conn.commit()


def ensure_admin(email: str, password: str) -> dict[str, Any]:
    email = email.strip().lower()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            user = dict(row)
        else:
            user_id = "usr_" + uuid.uuid4().hex
            now = _utc_now_iso()
            conn.execute(
                "INSERT INTO users (id, email, password_hash, is_admin, created_at) VALUES (?, ?, ?, 1, ?)",
                (user_id, email, _hash_password(password), now),
            )
            user = {"id": user_id, "email": email, "is_admin": 1}
        conn.execute("UPDATE projects SET owner_id = ? WHERE owner_id IS NULL", (user["id"],))
        conn.commit()
    return user


def create_user(email: str, password: str) -> dict[str, Any]:
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Invalid email address")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    user_id = "usr_" + uuid.uuid4().hex
    now = _utc_now_iso()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, is_admin, created_at) VALUES (?, ?, ?, 0, ?)",
                (user_id, email, _hash_password(password), now),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Email is already registered")
    return {"id": user_id, "email": email, "is_admin": False}


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND disabled_at IS NULL",
            (email.strip().lower(),),
        ).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"], "is_admin": bool(row["is_admin"])}


def create_session(user_id: str, ttl_days: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    expires = now.timestamp() + max(1, ttl_days) * 86400
    expires_at = datetime.fromtimestamp(expires, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, expires_at, _utc_now_iso()),
        )
        conn.commit()
    return token


def get_session_user(token: str) -> dict[str, Any] | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.is_admin, s.expires_at
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND u.disabled_at IS NULL
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            return None
        if row["expires_at"] <= _utc_now_iso():
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            conn.commit()
            return None
    return {"id": row["id"], "email": row["email"], "is_admin": bool(row["is_admin"])}


def delete_session(token: str) -> None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()


def create_domain(project_id: str, domain: str) -> dict[str, Any]:
    domain = domain.strip().lower().rstrip(".")
    if not re.fullmatch(r"(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain):
        raise ValueError("Invalid domain name")
    domain_id = "dom_" + uuid.uuid4().hex
    now = _utc_now_iso()
    token = secrets.token_urlsafe(24)
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO domains (id, project_id, domain, verification_token, created_at) VALUES (?, ?, ?, ?, ?)",
                (domain_id, project_id, domain, token, now),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Domain is already registered")
    return get_domain(domain_id)  # type: ignore[return-value]


def get_domain(domain_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM domains WHERE id = ? AND active = 1", (domain_id,)
        ).fetchone()
    return dict(row) if row else None


def get_domain_by_host(domain: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM domains WHERE domain = ? AND active = 1", (domain.lower().rstrip("."),)
        ).fetchone()
    return dict(row) if row else None


def list_domains(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM domains WHERE project_id = ? AND active = 1 ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def verify_domain(domain_id: str) -> dict[str, Any] | None:
    domain = get_domain(domain_id)
    if not domain:
        return None
    now = _utc_now_iso()
    with get_connection() as conn:
        conn.execute("UPDATE domains SET verified_at = ? WHERE id = ?", (now, domain_id))
        conn.commit()
    domain["verified_at"] = now
    return domain


def delete_domain(domain_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("UPDATE domains SET active = 0 WHERE id = ?", (domain_id,))
        conn.commit()
        return cur.rowcount > 0


def _project_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "current_deployment_id": row["current_deployment_id"],
        "current_version": row["current_version"] if "current_version" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_projects(owner_id: str | None = None, include_all: bool = False) -> list[dict[str, Any]]:
    with get_connection() as conn:
        query = """
            SELECT p.*, d.version AS current_version
            FROM projects p
            LEFT JOIN deployments d ON d.id = p.current_deployment_id
            WHERE p.deleted_at IS NULL
        """
        params: list[Any] = []
        if owner_id and not include_all:
            query += " AND p.owner_id = ?"
            params.append(owner_id)
        query += " ORDER BY p.updated_at DESC"
        rows = conn.execute(query, params).fetchall()
    return [_project_dict(row) for row in rows]


def get_project(project_id: str, owner_id: str | None = None, include_all: bool = False) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.*, d.version AS current_version
            FROM projects p
            LEFT JOIN deployments d ON d.id = p.current_deployment_id
            WHERE p.id = ? AND p.deleted_at IS NULL
              AND (? IS NULL OR ? = 1 OR p.owner_id = ?)
            """,
            (project_id, owner_id, 1 if include_all else 0, owner_id),
        ).fetchone()
    return _project_dict(row) if row else None


def get_project_by_slug(slug: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.*, d.version AS current_version
            FROM projects p LEFT JOIN deployments d ON d.id = p.current_deployment_id
            WHERE p.slug = ? AND p.deleted_at IS NULL
            """,
            (slug,),
        ).fetchone()
    return _project_dict(row) if row else None


def list_project_domains(project_id: str) -> list[dict[str, Any]]:
    return list_domains(project_id)


def create_project(name: str, owner_id: str | None = None) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise ValueError("Project name is required")
    project_id = "prj_" + uuid.uuid4().hex
    now = _utc_now_iso()
    with get_connection() as conn:
        slug = _unique_slug(conn, name, project_id)
        conn.execute(
            "INSERT INTO projects (id, name, slug, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, name[:120], slug, owner_id, now, now),
        )
        conn.commit()
    return get_project(project_id, include_all=True)  # type: ignore[return-value]


def insert_deployment(
    deploy_id: str,
    project_id: str | None,
    project_name: str | None,
    owner_id: str | None,
    url_path: str,
    source_zip: str,
    file_count: int,
    total_size: int,
) -> dict[str, Any]:
    """Insert a new immutable version and atomically advance the project pointer."""
    created_at = _utc_now_iso()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if project_id:
            project = conn.execute(
                "SELECT * FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,)
            ).fetchone()
            if not project:
                raise ValueError("Project not found")
        else:
            project_id = "prj_" + uuid.uuid4().hex
            name = (project_name or source_zip or "Untitled project").strip()[:120]
            slug = _unique_slug(conn, name, project_id)
            conn.execute(
                "INSERT INTO projects (id, name, slug, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, name, slug, owner_id, created_at, created_at),
            )

        version_row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM deployments WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        version = int(version_row["next_version"])
        conn.execute(
            """
            INSERT INTO deployments
                (id, name, url_path, source_zip, file_count, total_size, created_at, project_id, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (deploy_id, project_name, url_path, source_zip, file_count, total_size, created_at, project_id, version),
        )
        conn.execute(
            "UPDATE projects SET current_deployment_id = ?, updated_at = ? WHERE id = ?",
            (deploy_id, created_at, project_id),
        )
        conn.commit()

    return get_deployment(deploy_id)  # type: ignore[return-value]


def get_deployment(deploy_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT d.*, p.name AS project_name, p.slug AS project_slug,
                   p.current_deployment_id = d.id AS is_current
            FROM deployments d
            LEFT JOIN projects p ON p.id = d.project_id
            WHERE d.id = ? AND d.deleted_at IS NULL
            """,
            (deploy_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["is_current"] = bool(result.get("is_current"))
    return result


def list_deployments(limit: int = 50, offset: int = 0, owner_id: str | None = None, include_all: bool = False) -> list[dict[str, Any]]:
    with get_connection() as conn:
        query = """
            SELECT d.*, p.name AS project_name, p.slug AS project_slug,
                   p.current_deployment_id = d.id AS is_current
            FROM deployments d
            LEFT JOIN projects p ON p.id = d.project_id
            WHERE d.deleted_at IS NULL
        """
        params: list[Any] = []
        if owner_id and not include_all:
            query += " AND p.owner_id = ?"
            params.append(owner_id)
        query += " ORDER BY d.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
    return [
        {**dict(row), "is_current": bool(row["is_current"])}
        for row in rows
    ]


def count_deployments(owner_id: str | None = None, include_all: bool = False) -> int:
    with get_connection() as conn:
        if owner_id and not include_all:
            return int(conn.execute(
                "SELECT COUNT(*) AS cnt FROM deployments d JOIN projects p ON p.id = d.project_id WHERE d.deleted_at IS NULL AND p.owner_id = ?",
                (owner_id,),
            ).fetchone()["cnt"])
        return int(conn.execute("SELECT COUNT(*) AS cnt FROM deployments WHERE deleted_at IS NULL").fetchone()["cnt"])


def list_project_deployments(project_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT d.*, p.name AS project_name, p.slug AS project_slug,
                   p.current_deployment_id = d.id AS is_current
            FROM deployments d JOIN projects p ON p.id = d.project_id
            WHERE d.project_id = ? AND d.deleted_at IS NULL
            ORDER BY d.version DESC LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    return [
        {**dict(row), "is_current": bool(row["is_current"])}
        for row in rows
    ]


def cleanup_candidates(project_id: str, keep_versions: int) -> list[str]:
    """Return old non-current deployment IDs beyond the retention window."""
    keep_versions = max(1, keep_versions)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT d.id
            FROM deployments d
            JOIN projects p ON p.id = d.project_id
            WHERE d.project_id = ? AND d.deleted_at IS NULL
              AND d.id != p.current_deployment_id
            ORDER BY d.version DESC
            LIMIT -1 OFFSET ?
            """,
            (project_id, keep_versions - 1),
        ).fetchall()
    return [row["id"] for row in rows]


def rollback_project(project_id: str, version: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT d.*, p.name AS project_name, p.slug AS project_slug,
                   p.current_deployment_id = d.id AS is_current
            FROM deployments d JOIN projects p ON p.id = d.project_id
            WHERE d.project_id = ? AND d.version = ? AND d.deleted_at IS NULL
            """,
            (project_id, version),
        ).fetchone()
        if not row:
            conn.rollback()
            return None
        now = _utc_now_iso()
        conn.execute(
            "UPDATE projects SET current_deployment_id = ?, updated_at = ? WHERE id = ?",
            (row["id"], now, project_id),
        )
        conn.commit()
    result = dict(row)
    result["is_current"] = True
    return result


def delete_deployment(deploy_id: str) -> bool:
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT project_id FROM deployments WHERE id = ?", (deploy_id,)).fetchone()
        if not row:
            return False
        project_id = row["project_id"]
        conn.execute("DELETE FROM deployments WHERE id = ?", (deploy_id,))
        if project_id:
            replacement = conn.execute(
                "SELECT id FROM deployments WHERE project_id = ? AND deleted_at IS NULL ORDER BY version DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            conn.execute(
                "UPDATE projects SET current_deployment_id = ?, updated_at = ? WHERE id = ?",
                (replacement["id"] if replacement else None, _utc_now_iso(), project_id),
            )
        conn.commit()
        return True
