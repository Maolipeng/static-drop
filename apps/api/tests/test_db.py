import sqlite3

from app import config, db


def test_project_versions_increment_and_current_pointer_moves(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "staticdrop.db")
    db.init_db()

    project = db.create_project("Demo Site")
    first = db.insert_deployment(
        "dep_one", project["id"], project["name"], None, "/s/dep_one/", "one.zip", 1, 10
    )
    second = db.insert_deployment(
        "dep_two", project["id"], project["name"], None, "/s/dep_two/", "two.zip", 1, 20
    )

    assert first["version"] == 1
    assert second["version"] == 2
    assert second["is_current"] is True
    assert db.get_project(project["id"])["current_deployment_id"] == "dep_two"

    assert db.delete_deployment("dep_two") is True
    assert db.get_project(project["id"])["current_deployment_id"] == "dep_one"


def test_legacy_deployment_is_migrated_to_a_project(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    monkeypatch.setattr(config, "DB_PATH", database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            CREATE TABLE deployments (
                id TEXT PRIMARY KEY, name TEXT, url_path TEXT NOT NULL,
                source_zip TEXT NOT NULL, file_count INTEGER NOT NULL,
                total_size INTEGER NOT NULL, created_at TEXT NOT NULL, deleted_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO deployments VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
            ("dep_legacy", "Legacy site", "/s/dep_legacy/", "legacy.zip", 1, 10, "2026-01-01T00:00:00Z"),
        )

    db.init_db()
    migrated = db.get_deployment("dep_legacy")
    projects = db.list_projects()

    assert migrated["project_id"] == projects[0]["id"]
    assert migrated["version"] == 1
    assert projects[0]["current_deployment_id"] == "dep_legacy"


def test_domain_verification_is_bound_to_project(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "domain.db")
    db.init_db()
    project = db.create_project("Domain Site")

    domain = db.create_domain(project["id"], "www.example.com")
    assert domain["verified_at"] is None
    assert db.get_domain_by_host("WWW.EXAMPLE.COM")["id"] == domain["id"]

    verified = db.verify_domain(domain["id"])
    assert verified["verified_at"] is not None
    assert db.list_domains(project["id"])[0]["domain"] == "www.example.com"
    assert db.delete_domain(domain["id"]) is True
    assert db.get_domain(domain["id"]) is None
