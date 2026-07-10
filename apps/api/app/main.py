"""
FastAPI application entrypoint.

Endpoints:
  GET    /api/health              — health check
  POST   /api/deploy              — upload & deploy a zip
  POST   /api/deploy-folder       — upload & deploy a folder (multiple files)
  GET    /api/deployments         — list deployments (paginated)
  GET    /api/deployments/{id}    — get single deployment
  DELETE /api/deployments/{id}    — delete deployment
  GET    /api/projects             — list projects
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import Cookie, Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import config
from . import db
from . import deploy as deploy_logic

@asynccontextmanager
async def lifespan(_: FastAPI):
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    config.DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    config.DOMAINS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    if config.AUTH_MODE == "users":
        db.ensure_admin(config.ADMIN_EMAIL, config.ADMIN_PASSWORD)
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

def require_auth(
    authorization: str | None = Header(default=None),
    session_token: str | None = Cookie(default=None, alias="staticdrop_session"),
) -> dict[str, Any]:
    """Accept an automation Bearer token or a browser session cookie."""
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == config.DEPLOY_TOKEN:
            return {"id": None, "email": "automation", "is_admin": True}
    if session_token:
        user = db.get_session_user(session_token)
        if user:
            return user
    raise HTTPException(
        status_code=401,
        detail={"error": "Authentication required", "code": "UNAUTHORIZED"},
    )


class AuthRequest(BaseModel):
    email: str
    password: str


class DomainRequest(BaseModel):
    domain: str


def _download_github_archive(repository: str, ref: str | None, destination: Path) -> None:
    parsed = urlparse(repository.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError("Only https://github.com repositories are supported")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise ValueError("Repository must look like https://github.com/owner/name")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    ref_value = ref.strip() if ref else "HEAD"
    if len(ref_value) > 200 or ".." in ref_value:
        raise ValueError("Invalid GitHub ref")
    archive_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{ref_value}"
    headers = {"User-Agent": "StaticDrop/0.1", "Accept": "application/vnd.github+json"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    request = Request(archive_url, headers=headers)
    with urlopen(request, timeout=30) as response, destination.open("wb") as output:
        written = 0
        while chunk := response.read(1024 * 1024):
            written += len(chunk)
            if written > config.MAX_ZIP_SIZE:
                raise ValueError("GitHub archive exceeds the maximum upload size")
            output.write(chunk)


def _finalize_external_archive(
    deploy_id: str,
    tmp_zip: Path,
    source_name: str,
    project_id: str | None,
    project_name: str | None,
    user: dict[str, Any],
) -> JSONResponse:
    tmp_extract = config.TMP_DIR / deploy_id
    try:
        deploy_logic.safe_unzip(tmp_zip, tmp_extract)
        deploy_root = deploy_logic.find_deploy_root(tmp_extract)
        if project_id and not db.get_project(project_id, user["id"], bool(user["is_admin"])):
            return _error("Project not found", "NOT_FOUND", 404)
        public_prefix = f"/s/{deploy_id}"
        deploy_logic.rewrite_html_paths(deploy_root, public_prefix)
        deploy_logic.rewrite_css_paths(deploy_root, public_prefix)
        deploy_logic.inject_env_config(deploy_root, None, f"{public_prefix}/__staticdrop_env__.js")
        incoming_size = deploy_logic.count_files_and_size(deploy_root)[1]
        if (storage_error := deploy_logic.storage_error(incoming_size)):
            return _error(storage_error, "QUOTA_EXCEEDED", 413)
        final_dir = deploy_logic.move_to_deployments(deploy_root, deploy_id)
        file_count, total_size = deploy_logic.count_files_and_size(final_dir)
        db.insert_deployment(
            deploy_id=deploy_id,
            project_id=project_id,
            project_name=project_name,
            owner_id=user["id"],
            url_path=f"/s/{deploy_id}/",
            source_zip=source_name,
            file_count=file_count,
            total_size=total_size,
        )
        record = _format_deployment(db.get_deployment(deploy_id) or {})
        if record.get("project_slug"):
            deploy_logic.sync_project_link(record["project_slug"], deploy_id)
        _sync_project_domains(record.get("project_id"), deploy_id)
        if config.AUTO_CLEANUP_ENABLED and record.get("project_id"):
            for old_id in db.cleanup_candidates(record["project_id"], config.MAX_VERSIONS_PER_PROJECT):
                deploy_logic.remove_deployment_files(old_id)
                db.delete_deployment(old_id)
        return JSONResponse(status_code=200, content=record)
    except deploy_logic.DeployError as exc:
        return _error(exc.message, exc.code, exc.status)
    except (OSError, ValueError) as exc:
        return _error(str(exc), "VALIDATION_ERROR", 422)
    finally:
        deploy_logic.cleanup_tmp(deploy_id)


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
        "name": row.get("project_name") or row.get("name"),
        "project_id": row.get("project_id"),
        "project_name": row.get("project_name") or row.get("name"),
        "project_slug": row.get("project_slug"),
        "version": row.get("version", 1),
        "is_current": bool(row.get("is_current", False)),
        "url": f"{config.PUBLIC_BASE_URL.rstrip('/')}{row['url_path']}",
        "project_url": (
            f"{config.PUBLIC_BASE_URL.rstrip('/')}/p/{row['project_slug']}/"
            if row.get("project_slug")
            else None
        ),
        "url_path": row["url_path"],
        "source_zip": row["source_zip"],
        "file_count": row["file_count"],
        "total_size": row["total_size"],
        "created_at": row["created_at"],
    }


def _sync_project_domains(project_id: str | None, deployment_id: str) -> None:
    if not project_id:
        return
    for domain in db.list_project_domains(project_id):
        if domain.get("verified_at"):
            deploy_logic.sync_domain_link(domain["domain"], deployment_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _session_response(payload: dict[str, Any], token: str) -> JSONResponse:
    response = JSONResponse(status_code=200, content=payload)
    response.set_cookie(
        "staticdrop_session",
        token,
        max_age=config.SESSION_TTL_DAYS * 86400,
        httponly=True,
        secure=config.PUBLIC_BASE_URL.startswith("https://"),
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/auth/register")
def register(payload: AuthRequest) -> JSONResponse:
    if config.AUTH_MODE != "users":
        return _error("User authentication is disabled", "AUTH_MODE_DISABLED", 409)
    try:
        user = db.create_user(payload.email, payload.password)
    except ValueError as exc:
        return _error(str(exc), "VALIDATION_ERROR", 422)
    token = db.create_session(user["id"], config.SESSION_TTL_DAYS)
    return _session_response({"user": user}, token)


@app.post("/api/auth/login")
def login(payload: AuthRequest) -> JSONResponse:
    if config.AUTH_MODE != "users":
        return _error("User authentication is disabled", "AUTH_MODE_DISABLED", 409)
    user = db.authenticate_user(payload.email, payload.password)
    if not user:
        return _error("Invalid email or password", "UNAUTHORIZED", 401)
    token = db.create_session(user["id"], config.SESSION_TTL_DAYS)
    return _session_response({"user": user}, token)


@app.post("/api/auth/logout")
def logout(
    session_token: str | None = Cookie(default=None, alias="staticdrop_session"),
) -> JSONResponse:
    if session_token:
        db.delete_session(session_token)
    response = JSONResponse(status_code=200, content={"logged_out": True})
    response.delete_cookie("staticdrop_session", path="/")
    return response


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return {"user": user, "auth_mode": config.AUTH_MODE}

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


@app.get("/api/projects")
def list_projects(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return {"projects": db.list_projects(user["id"], bool(user["is_admin"]))}


@app.get("/api/projects/{project_id}/deployments")
def project_deployments(
    project_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> Any:
    project = db.get_project(project_id, user["id"], bool(user["is_admin"]))
    if not project:
        return _error("Project not found", "NOT_FOUND", 404)
    return {
        "project": project,
        "deployments": [_format_deployment(row) for row in db.list_project_deployments(project_id)],
    }


@app.post("/api/projects/{project_id}/rollback/{version}")
def rollback_project(
    project_id: str,
    version: int,
    user: dict[str, Any] = Depends(require_auth),
) -> JSONResponse:
    if not db.get_project(project_id, user["id"], bool(user["is_admin"])):
        return _error("Project not found", "NOT_FOUND", 404)
    try:
        deployment = db.rollback_project(project_id, version)
    except ValueError as exc:
        return _error(str(exc), "VALIDATION_ERROR", 422)
    if not deployment:
        return _error("Project version not found", "NOT_FOUND", 404)
    deploy_logic.sync_project_link(deployment["project_slug"], deployment["id"])
    _sync_project_domains(deployment.get("project_id"), deployment["id"])
    return JSONResponse(status_code=200, content=_format_deployment(deployment))


@app.post("/api/projects/{project_id}/domains")
def add_domain(
    project_id: str,
    payload: DomainRequest,
    user: dict[str, Any] = Depends(require_auth),
) -> JSONResponse:
    project = db.get_project(project_id, user["id"], bool(user["is_admin"]))
    if not project:
        return _error("Project not found", "NOT_FOUND", 404)
    try:
        domain = db.create_domain(project_id, payload.domain)
    except ValueError as exc:
        return _error(str(exc), "VALIDATION_ERROR", 422)
    return JSONResponse(
        status_code=201,
        content={
            "id": domain["id"],
            "domain": domain["domain"],
            "verified": bool(domain["verified_at"]),
            "verification": {
                "type": "TXT",
                "name": f"_staticdrop-challenge.{domain['domain']}",
                "value": domain["verification_token"],
            },
        },
    )


@app.get("/api/projects/{project_id}/domains")
def project_domains(
    project_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> Any:
    if not db.get_project(project_id, user["id"], bool(user["is_admin"])):
        return _error("Project not found", "NOT_FOUND", 404)
    return {"domains": db.list_project_domains(project_id)}


@app.post("/api/domains/{domain_id}/verify")
def verify_domain(
    domain_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> JSONResponse:
    domain = db.get_domain(domain_id)
    if not domain:
        return _error("Domain not found", "NOT_FOUND", 404)
    if not db.get_project(domain["project_id"], user["id"], bool(user["is_admin"])):
        return _error("Domain not found", "NOT_FOUND", 404)
    try:
        import dns.resolver

        answers = dns.resolver.resolve(f"_staticdrop-challenge.{domain['domain']}", "TXT", lifetime=5)
        values = {b"".join(record.strings).decode() for record in answers}
    except Exception:
        return _error("Verification TXT record was not found", "VERIFICATION_PENDING", 422)
    if domain["verification_token"] not in values:
        return _error("Verification TXT record does not match", "VERIFICATION_PENDING", 422)
    verified = db.verify_domain(domain_id)
    project = db.get_project(domain["project_id"], include_all=True)
    if project and project.get("current_deployment_id"):
        deploy_logic.sync_domain_link(domain["domain"], project["current_deployment_id"])
    return JSONResponse(status_code=200, content={"domain": verified, "verified": True})


@app.delete("/api/domains/{domain_id}")
def remove_domain(
    domain_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> JSONResponse:
    domain = db.get_domain(domain_id)
    if not domain or not db.get_project(domain["project_id"], user["id"], bool(user["is_admin"])):
        return _error("Domain not found", "NOT_FOUND", 404)
    (config.DOMAINS_DIR / domain["domain"]).unlink(missing_ok=True)
    db.delete_domain(domain_id)
    return JSONResponse(status_code=200, content={"id": domain_id, "deleted": True})


@app.get("/api/domains/certificate-check")
def certificate_check(domain: str = Query(...)) -> JSONResponse:
    host = domain.lower().rstrip(".")
    allowed = bool(db.get_domain_by_host(host) and db.get_domain_by_host(host)["verified_at"])
    if config.PUBLIC_DOMAIN and host.endswith("." + config.PUBLIC_DOMAIN.lower()):
        slug = host[: -(len(config.PUBLIC_DOMAIN) + 1)]
        allowed = bool(db.get_project_by_slug(slug))
    if config.PUBLIC_DOMAIN and host == config.PUBLIC_DOMAIN.lower():
        allowed = True
    if not allowed:
        return _error("Domain is not verified", "DOMAIN_NOT_VERIFIED", 404)
    return JSONResponse(status_code=200, content={"allowed": True})


@app.post("/api/deploy")
async def deploy(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
    env: str | None = Form(default=None),
    user: dict[str, Any] = Depends(require_auth),
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

    if project_id and not db.get_project(project_id, user["id"], bool(user["is_admin"])):
        deploy_logic.cleanup_tmp(deploy_id)
        return _error("Project not found", "NOT_FOUND", 404)

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
    try:
        db.insert_deployment(
            deploy_id=deploy_id,
            project_id=project_id,
            project_name=name,
            owner_id=user["id"],
            url_path=url_path,
            source_zip=file.filename,
            file_count=file_count,
            total_size=total_size,
        )
        record = _format_deployment(db.get_deployment(deploy_id) or {})
    except ValueError as exc:
        deploy_logic.remove_deployment_files(deploy_id)
        return _error(str(exc), "VALIDATION_ERROR", 422)

    if record.get("project_slug"):
        deploy_logic.sync_project_link(record["project_slug"], deploy_id)
    _sync_project_domains(record.get("project_id"), deploy_id)
    if config.AUTO_CLEANUP_ENABLED and record.get("project_id"):
        for old_id in db.cleanup_candidates(record["project_id"], config.MAX_VERSIONS_PER_PROJECT):
            deploy_logic.remove_deployment_files(old_id)
            db.delete_deployment(old_id)

    return JSONResponse(status_code=200, content=record)


@app.post("/api/github/deploy")
async def deploy_github(
    repository: str = Form(...),
    ref: str | None = Form(default=None),
    name: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
    user: dict[str, Any] = Depends(require_auth),
) -> JSONResponse:
    """Download a GitHub repository archive and deploy its static output."""
    if project_id and not db.get_project(project_id, user["id"], bool(user["is_admin"])):
        return _error("Project not found", "NOT_FOUND", 404)

    deploy_id = _deploy_id()
    tmp_zip = config.TMP_DIR / f"{deploy_id}.zip"
    try:
        await asyncio.to_thread(_download_github_archive, repository, ref, tmp_zip)
        parsed = urlparse(repository.strip())
        repo_name = parsed.path.strip("/").split("/")[-1].removesuffix(".git")
        source_name = f"github:{parsed.netloc}/{parsed.path.strip('/')}"[:240]
        return _finalize_external_archive(
            deploy_id,
            tmp_zip,
            source_name,
            project_id,
            name or repo_name,
            user,
        )
    except (OSError, ValueError) as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(str(exc), "VALIDATION_ERROR", 422)
    except Exception as exc:
        deploy_logic.cleanup_tmp(deploy_id)
        return _error(f"Failed to download GitHub repository: {exc}", "GITHUB_ERROR", 502)


@app.post("/api/deploy-folder")
async def deploy_folder(
    files: list[UploadFile] = File(...),
    name: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
    env: str | None = Form(default=None),
    user: dict[str, Any] = Depends(require_auth),
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

    if project_id and not db.get_project(project_id, user["id"], bool(user["is_admin"])):
        deploy_logic.cleanup_tmp(deploy_id)
        return _error("Project not found", "NOT_FOUND", 404)

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
    try:
        db.insert_deployment(
            deploy_id=deploy_id,
            project_id=project_id,
            project_name=name,
            owner_id=user["id"],
            url_path=url_path,
            source_zip=source_name,
            file_count=file_count,
            total_size=total_size,
        )
        record = _format_deployment(db.get_deployment(deploy_id) or {})
    except ValueError as exc:
        deploy_logic.remove_deployment_files(deploy_id)
        return _error(str(exc), "VALIDATION_ERROR", 422)

    if record.get("project_slug"):
        deploy_logic.sync_project_link(record["project_slug"], deploy_id)
    _sync_project_domains(record.get("project_id"), deploy_id)
    if config.AUTO_CLEANUP_ENABLED and record.get("project_id"):
        for old_id in db.cleanup_candidates(record["project_id"], config.MAX_VERSIONS_PER_PROJECT):
            deploy_logic.remove_deployment_files(old_id)
            db.delete_deployment(old_id)

    return JSONResponse(status_code=200, content=record)


@app.get("/api/deployments")
def list_deployments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    rows = db.list_deployments(limit=limit, offset=offset, owner_id=user["id"], include_all=bool(user["is_admin"]))
    total = db.count_deployments(user["id"], bool(user["is_admin"]))
    return {
        "deployments": [_format_deployment(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/deployments/{deploy_id}")
def get_deployment(
    deploy_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> JSONResponse:
    row = db.get_deployment(deploy_id)
    if not row or (user["id"] and not user["is_admin"] and row.get("owner_id") != user["id"]):
        return _error("Deployment not found", "NOT_FOUND", 404)
    return JSONResponse(status_code=200, content=_format_deployment(row))


@app.delete("/api/deployments/{deploy_id}")
def delete_deployment(
    deploy_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> JSONResponse:
    row = db.get_deployment(deploy_id)
    if not row or (user["id"] and not user["is_admin"] and row.get("owner_id") != user["id"]):
        return _error("Deployment not found", "NOT_FOUND", 404)

    project_id = row.get("project_id")
    project_slug = row.get("project_slug")
    # Remove files first
    deploy_logic.remove_deployment_files(deploy_id)
    db.delete_deployment(deploy_id)
    if project_id and project_slug:
        project = db.get_project(project_id, include_all=True)
        if project and project.get("current_deployment_id"):
            deploy_logic.sync_project_link(project_slug, project["current_deployment_id"])
            _sync_project_domains(project_id, project["current_deployment_id"])
        else:
            (config.PROJECTS_DIR / project_slug).unlink(missing_ok=True)

    return JSONResponse(
        status_code=200,
        content={"id": deploy_id, "deleted": True},
    )
