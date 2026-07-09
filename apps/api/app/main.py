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

import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from . import db
from . import deploy as deploy_logic

app = FastAPI(
    title="StaticDrop API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# CORS — allow the Next.js dev server (prod goes through nginx so same origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def _startup() -> None:
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    config.DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()


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

    # --- rewrite absolute paths in HTML for subpath deployment ---
    deploy_logic.rewrite_html_paths(deploy_root)

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

    # --- read all files into memory with their relative paths ---
    # We read+validate in one pass, accumulating total size for the quota check.
    files_with_paths: list[tuple[bytes, str]] = []
    running_size = 0

    try:
        for upload_file in files:
            relative_path = upload_file.filename or upload_file.filename or ""
            if not relative_path:
                continue

            # Read content with size check
            content = await upload_file.read()
            running_size += len(content)

            # Enforce max zip size as the total upload size limit
            if running_size > config.MAX_ZIP_SIZE:
                deploy_logic.cleanup_tmp(deploy_id)
                return _error(
                    f"Total upload size exceeds maximum of {config.MAX_ZIP_SIZE} bytes",
                    "QUOTA_EXCEEDED",
                    413,
                )

            files_with_paths.append((content, relative_path))
            await upload_file.close()
    except Exception as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(f"Failed to read uploaded files: {exc}", "INTERNAL", 500)

    # --- safe write files ---
    try:
        file_count, total_size = await deploy_logic.safe_write_files(
            files_with_paths, tmp_extract
        )
    except deploy_logic.DeployError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(exc.message, exc.code, exc.status)

    # --- find deploy root (the dir with index.html) ---
    try:
        deploy_root = deploy_logic.find_deploy_root(tmp_extract)
    except deploy_logic.DeployError as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(exc.message, exc.code, exc.status)

    # --- rewrite absolute paths in HTML for subpath deployment ---
    deploy_logic.rewrite_html_paths(deploy_root)

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
    # Use the top-level folder name from the first file's path as source
    source_name = files_with_paths[0][1].split("/")[0] if files_with_paths else "folder"
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
