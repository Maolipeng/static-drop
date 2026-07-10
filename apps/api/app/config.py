"""
StaticDrop configuration — loaded from environment variables.
All limits have sensible defaults but can be overridden via env.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(key: str, default: str) -> str:
    val = os.environ.get(key)
    return val if val else default


def _env_list(key: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(key, default).split(",") if item.strip()]


# --- Auth ---
DEPLOY_TOKEN: str = _env_str("DEPLOY_TOKEN", "change-me-to-a-random-string")
AUTH_MODE: str = _env_str("AUTH_MODE", "token").lower()
ADMIN_EMAIL: str = _env_str("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD: str = _env_str("ADMIN_PASSWORD", "change-me-to-a-random-password")
GITHUB_TOKEN: str = _env_str("GITHUB_TOKEN", "")
SESSION_TTL_DAYS: int = _env_int("SESSION_TTL_DAYS", 14)

# --- Public URL ---
PUBLIC_BASE_URL: str = _env_str("PUBLIC_BASE_URL", "http://localhost:8080")
PUBLIC_DOMAIN: str = _env_str("PUBLIC_DOMAIN", "")
CORS_ORIGINS: list[str] = _env_list("CORS_ORIGINS")

# --- Paths ---
DATA_DIR: Path = Path(_env_str("DATA_DIR", "/data"))
DEPLOYMENTS_DIR: Path = Path(_env_str("DEPLOYMENTS_DIR", str(DATA_DIR / "deployments")))
PROJECTS_DIR: Path = Path(_env_str("PROJECTS_DIR", str(DATA_DIR / "projects")))
DOMAINS_DIR: Path = Path(_env_str("DOMAINS_DIR", str(DATA_DIR / "domains")))
DB_PATH: Path = Path(_env_str("DB_PATH", str(DATA_DIR / "db" / "staticdrop.db")))
TMP_DIR: Path = DATA_DIR / "tmp"

# --- Limits (bytes / count) ---
MAX_ZIP_SIZE: int = _env_int("MAX_ZIP_SIZE", 104_857_600)       # 100 MB
MAX_TOTAL_SIZE: int = _env_int("MAX_TOTAL_SIZE", 524_288_000)    # 500 MB
MAX_FILE_SIZE: int = _env_int("MAX_FILE_SIZE", 52_428_800)       # 50 MB
MAX_FILE_COUNT: int = _env_int("MAX_FILE_COUNT", 5000)
MAX_STORAGE_SIZE: int = _env_int("MAX_STORAGE_SIZE", 5_368_709_120)  # 5 GB
MIN_FREE_SPACE: int = _env_int("MIN_FREE_SPACE", 67_108_864)        # 64 MB
MAX_VERSIONS_PER_PROJECT: int = _env_int("MAX_VERSIONS_PER_PROJECT", 10)
AUTO_CLEANUP_ENABLED: bool = _env_str("AUTO_CLEANUP_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

# --- Dangerous file extensions (never deploy these) ---
BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    # Server-side scripts
    ".php", ".phtml", ".php3", ".php4", ".php5", ".phps",
    ".py", ".rb", ".pl", ".cgi",
    # Executables
    ".exe", ".bat", ".cmd", ".com", ".scr", ".msi",
    ".sh", ".bash", ".zsh", ".fish",
    # Shared libraries
    ".so", ".dylib", ".dll", ".a",
    # Java
    ".jar", ".war", ".ear", ".class",
    # .NET
    ".aspx", ".asp", ".config",
    # Configs that may leak secrets
    ".env", ".ini",
    # Other
    ".htaccess", ".htpasswd",
})
