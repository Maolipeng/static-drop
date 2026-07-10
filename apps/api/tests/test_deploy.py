from pathlib import Path
import asyncio
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.deploy import (
    DeployError,
    inject_env_config,
    rewrite_css_paths,
    rewrite_html_paths,
    safe_write_uploaded_files,
)
from app.main import _parse_env, app
from app import config, db


def test_runtime_env_uses_deployment_url_and_escapes_script_content(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        "<html><head></head><body></body></html>", encoding="utf-8"
    )
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "index.html").write_text(
        "<html><head></head><body></body></html>", encoding="utf-8"
    )

    inject_env_config(
        tmp_path,
        {"API_URL": "https://api.example.test", "VALUE": "</script><script>alert(1)</script>"},
        "/s/dep_test/__staticdrop_env__.js",
    )

    root_html = (tmp_path / "index.html").read_text(encoding="utf-8")
    nested_html = (tmp_path / "nested" / "index.html").read_text(encoding="utf-8")
    env_js = (tmp_path / "__staticdrop_env__.js").read_text(encoding="utf-8")

    assert '/s/dep_test/__staticdrop_env__.js' in root_html
    assert '/s/dep_test/__staticdrop_env__.js' in nested_html
    assert "</script>" not in env_js
    assert "\\u003c/script\\u003e" in env_js


def test_asset_rewriters_cover_html_and_css(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        '<script src="/assets/app.js"></script><base href="/">',
        encoding="utf-8",
    )
    (tmp_path / "styles.css").write_text(
        "body { background: url('/assets/bg.png'); }", encoding="utf-8"
    )

    rewrite_html_paths(tmp_path, "/s/dep_test")
    rewrite_css_paths(tmp_path, "/s/dep_test")

    assert '/s/dep_test/assets/app.js' in (tmp_path / "index.html").read_text()
    assert '/s/dep_test/assets/bg.png' in (tmp_path / "styles.css").read_text()


class FakeUpload:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self.content = content
        self.offset = 0
        self.closed = False

    async def read(self, size: int) -> bytes:
        chunk = self.content[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    async def close(self) -> None:
        self.closed = True


def test_folder_upload_is_streamed_and_normalizes_paths(tmp_path: Path) -> None:
    uploads = [
        FakeUpload("dist/index.html", b"<html></html>"),
        FakeUpload("dist\\assets\\app.js", b"console.log(1)"),
    ]

    count, size, first_path = asyncio.run(safe_write_uploaded_files(uploads, tmp_path))

    assert (count, size, first_path) == (2, 27, "dist/index.html")
    assert (tmp_path / "dist" / "assets" / "app.js").read_bytes() == b"console.log(1)"
    assert all(upload.closed for upload in uploads)


def test_env_parser_rejects_invalid_public_api_url() -> None:
    with pytest.raises(ValueError, match=r"absolute http\(s\) URL"):
        _parse_env('{"API_URL":"javascript:alert(1)"}')


def test_folder_upload_rejects_windows_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(DeployError, match="Path traversal"):
        asyncio.run(
            safe_write_uploaded_files([FakeUpload("..\\secret.txt", b"x")], tmp_path)
        )


def test_github_deploy_downloads_and_creates_a_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "staticdrop.db")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(config, "DEPLOYMENTS_DIR", tmp_path / "deployments")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "DOMAINS_DIR", tmp_path / "domains")
    monkeypatch.setattr(config, "DEPLOY_TOKEN", "test-token")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "http://testserver")
    db.init_db()

    def fake_download(_repository, _ref, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w") as archive:
            archive.writestr("repo/index.html", "<html><body>github</body></html>")

    monkeypatch.setattr("app.main._download_github_archive", fake_download)
    with TestClient(app) as client:
        response = client.post(
            "/api/github/deploy",
            headers={"Authorization": "Bearer test-token"},
            data={"repository": "https://github.com/example/site", "ref": "main"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_zip"] == "github:github.com/example/site"
    assert (config.DEPLOYMENTS_DIR / payload["id"] / "index.html").exists()


def test_cloudflare_provision_creates_dns_records_for_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "staticdrop.db")
    monkeypatch.setattr(config, "DEPLOY_TOKEN", "test-token")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(config, "DEPLOYMENTS_DIR", tmp_path / "deployments")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "DOMAINS_DIR", tmp_path / "domains")
    monkeypatch.setattr(config, "PUBLIC_DOMAIN", "drop.example.com")
    monkeypatch.setattr(config, "CLOUDFLARE_API_TOKEN", "cf-test", raising=False)
    monkeypatch.setattr(config, "CLOUDFLARE_ZONE_ID", "zone-test", raising=False)
    monkeypatch.setattr(config, "CLOUDFLARE_ZONE_NAME", "example.com", raising=False)
    db.init_db()
    project = db.create_project("Cloudflare Site")

    calls = []

    def fake_cloudflare_request(method, path, payload=None):
        calls.append((method, path, payload))
        if method == "GET":
            return {"success": True, "result": []}
        return {"success": True, "result": {"id": "record-id"}}

    monkeypatch.setattr("app.main._cloudflare_request", fake_cloudflare_request, raising=False)
    with TestClient(app) as client:
        response = client.post(
            f"/api/projects/{project['id']}/domains/provision",
            headers={"Authorization": "Bearer test-token"},
            json={"domain": "www.example.com"},
        )

    assert response.status_code == 201
    assert response.json()["domain"]["domain"] == "www.example.com"
    assert any(call[2]["type"] == "CNAME" for call in calls if call[2])
    assert any(call[2]["type"] == "TXT" for call in calls if call[2])
