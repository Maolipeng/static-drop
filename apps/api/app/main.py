"""
FastAPI application entrypoint.

Endpoints:
  GET    /api/health              — health check
  POST   /api/deploy              — upload & deploy a zip
  POST   /api/deploy-folder       — upload & deploy a folder (multiple files)
  GET    /api/deployments         — list deployments (paginated)
  GET    /api/deployments/{id}    — get single deployment
  DELETE /api/deployments/{id}    — delete deployment
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from . import db
from . import deploy as deploy_logic

@asynccontextmanager
async def lifespan(_: FastAPI):
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    config.DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    yield


app = FastAPI(
    title="StaticDrop API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS is opt-in. Production uses same-origin requests through nginx, while
# direct browser clients must explicitly configure CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def require_token(authorization: str | None = Header(default=None)) -> None:
    """Validate Bearer token against DEPLOY_TOKEN."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={"error": "Missing Authorization header", "code": "UNAUTHORIZED"},
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid Authorization header format", "code": "UNAUTHORIZED"},
        )
    token = parts[1]
    if token != config.DEPLOY_TOKEN:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid token", "code": "UNAUTHORIZED"},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str, code: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": message, "code": code},
    )


def _deploy_id() -> str:
    """Generate a deploy ID: dep_ + uuid (no dashes, 25 chars)."""
    return "dep_" + uuid.uuid4().hex


def _parse_env(env_str: str | None) -> dict[str, str] | None:
    """
    Parse the env parameter from the deploy request.

    Accepts a JSON string like '{"API_URL":"https://api.example.com"}'
    or a simple key=value format like 'API_URL=https://api.example.com'.

    Returns a dict, or None if env_str is empty/None.
    """
    if not env_str:
        return None

    import json

    env_str = env_str.strip()
    if len(env_str) > 16_384:
        raise ValueError("Runtime environment configuration is too large")

    # Try JSON first
    try:
        parsed = json.loads(env_str)
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        if not isinstance(parsed, dict):
            raise ValueError("env must be a JSON object")
        result = {str(k): str(v) for k, v in parsed.items()}
    else:
        # Fallback: parse key=value pairs (newline or comma separated)
        result = {}
        for line in env_str.replace(",", "\n").split("\n"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k:
                    result[k] = v

    if not result:
        raise ValueError("env must contain at least one key-value pair")
    if len(result) > 32:
        raise ValueError("env contains too many variables")
    for key, value in result.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Invalid environment variable name: {key}")
        if len(value) > 2048:
            raise ValueError(f"Environment variable is too long: {key}")
    if "API_URL" in result:
        parsed_url = urlparse(result["API_URL"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("API_URL must be an absolute http(s) URL")

    return result


def _format_deployment(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row.get("name"),
        "url": f"{config.PUBLIC_BASE_URL.rstrip('/')}{row['url_path']}",
        "url_path": row["url_path"],
        "source_zip": row["source_zip"],
        "file_count": row["file_count"],
        "total_size": row["total_size"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, Any]:
    db_ok = True
    try:
        db.get_connection().execute("SELECT 1").fetchone()
    except Exception:
        db_ok = False

    data_dir_ok = config.DEPLOYMENTS_DIR.exists()

    return {
        "status": "ok" if (db_ok and data_dir_ok) else "degraded",
        "db": "ok" if db_ok else "error",
        "data_dir": "ok" if data_dir_ok else "missing",
        "deployments_dir": str(config.DEPLOYMENTS_DIR),
    }


@app.post("/api/deploy")
async def deploy(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    env: str | None = Form(default=None),
    _auth: None = Depends(require_token),
) -> JSONResponse:
    # --- validate filename / extension ---
    if not file.filename or not file.filename.lower().endswith(".zip"):
        return _error("File must be a .zip archive", "VALIDATION_ERROR", 422)

    # --- stream upload to tmp file, enforcing max zip size ---
    deploy_id = _deploy_id()
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_zip = config.TMP_DIR / f"{deploy_id}.zip"

    try:
        written = 0
        with open(tmp_zip, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                written += len(chunk)
                if written > config.MAX_ZIP_SIZE:
                    f.close()
                    tmp_zip.unlink(missing_ok=True)
                    return _error(
                        f"Zip file exceeds maximum size of {config.MAX_ZIP_SIZE} bytes",
                        "QUOTA_EXCEEDED",
                        413,
                    )
                f.write(chunk)
    finally:
        await file.close()

    # --- safe unzip ---
    tmp_extract = config.TMP_DIR / deploy_id
    try:
        file_count, total_size = deploy_logic.safe_unzip(tmp_zip, tmp_extract)
    except deploy_logic.DeployError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(exc.message, exc.code, exc.status)

    # --- find deploy root (the dir with index.html) ---
    try:
        deploy_root = deploy_logic.find_deploy_root(tmp_extract)
    except deploy_logic.DeployError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(exc.message, exc.code, exc.status)

    try:
        parsed_env = _parse_env(env)
    except ValueError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(str(exc), "VALIDATION_ERROR", 422)

    # --- rewrite assets and inject runtime config ---
    public_prefix = f"/s/{deploy_id}"
    try:
        deploy_logic.rewrite_html_paths(deploy_root, public_prefix)
        deploy_logic.rewrite_css_paths(deploy_root, public_prefix)
        deploy_logic.inject_env_config(
            deploy_root,
            parsed_env,
            f"{public_prefix}/__staticdrop_env__.js",
        )
    except OSError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(f"Failed to prepare deployment: {exc}", "INTERNAL", 500)

    incoming_size = deploy_logic.count_files_and_size(deploy_root)[1]
    storage_error = deploy_logic.storage_error(incoming_size)
    if storage_error:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(storage_error, "QUOTA_EXCEEDED", 413)

    # --- move to final location ---
    try:
        final_dir = deploy_logic.move_to_deployments(deploy_root, deploy_id)
    except Exception as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(f"Failed to move deployment: {exc}", "INTERNAL", 500)

    # Recount after move for accuracy (the move may have dropped empty dirs etc.)
    file_count, total_size = deploy_logic.count_files_and_size(final_dir)

    # --- cleanup tmp ---
    deploy_logic.cleanup_tmp(deploy_id)

    # --- write to DB ---
    url_path = f"/s/{deploy_id}/"
    record = db.insert_deployment(
        deploy_id=deploy_id,
        name=name,
        url_path=url_path,
        source_zip=file.filename,
        file_count=file_count,
        total_size=total_size,
    )

    return JSONResponse(status_code=200, content=record)


@app.post("/api/deploy-folder")
async def deploy_folder(
    files: list[UploadFile] = File(...),
    name: str | None = Form(default=None),
    env: str | None = Form(default=None),
    _auth: None = Depends(require_token),
) -> JSONResponse:
    """
    Deploy a folder uploaded as multiple files.
    Each file's filename should be its relative path within the folder
    (e.g. "dist/index.html", "dist/assets/app.js").
    """
    if not files:
        return _error("No files provided", "VALIDATION_ERROR", 422)

    deploy_id = _deploy_id()
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_extract = config.TMP_DIR / deploy_id

    try:
        file_count, total_size, source_name = await deploy_logic.safe_write_uploaded_files(
            files, tmp_extract
        )
    except Exception as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        if isinstance(exc, deploy_logic.DeployError):
            return _error(exc.message, exc.code, exc.status)
        return _error(f"Failed to write uploaded files: {exc}", "INTERNAL", 500)

    # --- find deploy root (the dir with index.html) ---
    try:
        deploy_root = deploy_logic.find_deploy_root(tmp_extract)
    except deploy_logic.DeployError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(exc.message, exc.code, exc.status)

    try:
        parsed_env = _parse_env(env)
    except ValueError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(str(exc), "VALIDATION_ERROR", 422)

    public_prefix = f"/s/{deploy_id}"
    try:
        deploy_logic.rewrite_html_paths(deploy_root, public_prefix)
        deploy_logic.rewrite_css_paths(deploy_root, public_prefix)
        deploy_logic.inject_env_config(
            deploy_root,
            parsed_env,
            f"{public_prefix}/__staticdrop_env__.js",
        )
    except OSError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(f"Failed to prepare deployment: {exc}", "INTERNAL", 500)

    incoming_size = deploy_logic.count_files_and_size(deploy_root)[1]
    storage_error = deploy_logic.storage_error(incoming_size)
    if storage_error:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(storage_error, "QUOTA_EXCEEDED", 413)

    # --- move to final location ---
    try:
        final_dir = deploy_logic.move_to_deployments(deploy_root, deploy_id)
    except Exception as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(f"Failed to move deployment: {exc}", "INTERNAL", 500)

    # Recount after move for accuracy
    file_count, total_size = deploy_logic.count_files_and_size(final_dir)

    # --- cleanup tmp ---
    deploy_logic.cleanup_tmp(deploy_id)

    # --- write to DB ---
    url_path = f"/s/{deploy_id}/"
    # Use the first uploaded path as the source label.
    source_name = (source_name or "folder").replace("\\", "/").split("/")[0]
    record = db.insert_deployment(
        deploy_id=deploy_id,
        name=name,
        url_path=url_path,
        source_zip=source_name,
        file_count=file_count,
        total_size=total_size,
    )

    return JSONResponse(status_code=200, content=record)


@app.get("/api/deployments")
def list_deployments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: None = Depends(require_token),
) -> dict[str, Any]:
    rows = db.list_deployments(limit=limit, offset=offset)
    total = db.count_deployments()
    return {
        "deployments": [_format_deployment(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/deployments/{deploy_id}")
def get_deployment(
    deploy_id: str,
    _auth: None = Depends(require_token),
) -> JSONResponse:
    row = db.get_deployment(deploy_id)
    if not row:
        return _error("Deployment not found", "NOT_FOUND", 404)
    return JSONResponse(status_code=200, content=_format_deployment(row))


@app.delete("/api/deployments/{deploy_id}")
def delete_deployment(
    deploy_id: str,
    _auth: None = Depends(require_token),
) -> JSONResponse:
    row = db.get_deployment(deploy_id)
    if not row:
        return _error("Deployment not found", "NOT_FOUND", 404)

    # Remove files first
    deploy_logic.remove_deployment_files(deploy_id)
    db.delete_deployment(deploy_id)

    return JSONResponse(
        status_code=200,
        content={"id": deploy_id, "deleted": True},
    )
