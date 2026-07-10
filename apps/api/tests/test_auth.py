from pathlib import Path
import io
import zipfile

from fastapi.testclient import TestClient

from app import config
from app.main import app


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("index.html", "<html>alice</html>")
    return buffer.getvalue()


def test_users_mode_isolates_projects_between_accounts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "AUTH_MODE", "users")
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "admin-password")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "staticdrop.db")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(config, "DEPLOYMENTS_DIR", tmp_path / "deployments")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "DOMAINS_DIR", tmp_path / "domains")

    with TestClient(app) as alice:
        assert alice.post("/api/auth/register", json={"email": "alice@example.com", "password": "alice-password"}).status_code == 200
        upload = alice.post(
            "/api/deploy",
            files={"file": ("site.zip", _zip_bytes(), "application/zip")},
            data={"name": "Alice Site"},
        )
        assert upload.status_code == 200
        project_id = upload.json()["project_id"]

    with TestClient(app) as bob:
        assert bob.post("/api/auth/register", json={"email": "bob@example.com", "password": "bob-password"}).status_code == 200
        assert bob.get("/api/projects").json() == {"projects": []}
        assert bob.get(f"/api/projects/{project_id}/deployments").status_code == 404
        assert bob.get(f"/api/deployments/{upload.json()['id']}").status_code == 404
