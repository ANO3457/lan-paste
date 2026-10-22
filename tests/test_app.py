import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from pathlib import Path

# Give the imported app an isolated SQLite database for this test run.
_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix="lan-paste-tests-")
os.environ["DATA_DIR"] = _TEST_DATA_DIR.name
os.environ["PASTE_ADMIN_TOKEN"] = "test-admin-token"

import app as paste_app  # noqa: E402


def setup_function():
    with paste_app.connect() as db:
        db.execute("DELETE FROM pastes")


def test_create_and_read_paste():
    client = paste_app.app.test_client()
    response = client.post(
        "/api/pastes",
        json={"title": "test note", "content": "hello LAN", "ttl_hours": 24},
    )
    assert response.status_code == 201
    paste_id = response.get_json()["id"]

    fetched = client.get(f"/api/pastes/{paste_id}")
    assert fetched.status_code == 200
    assert fetched.get_json()["title"] == "test note"
    assert fetched.get_json()["content"] == "hello LAN"


def test_reject_empty_content():
    response = paste_app.app.test_client().post(
        "/api/pastes", json={"content": "   "}
    )
    assert response.status_code == 400
    assert "empty" in response.get_json()["error"]


def test_reject_invalid_expiry():
    response = paste_app.app.test_client().post(
        "/api/pastes", json={"content": "hello", "ttl_hours": 5}
    )
    assert response.status_code == 400


def test_delete_requires_valid_admin_token():
    client = paste_app.app.test_client()
    created = client.post("/api/pastes", json={"content": "delete me"})
    paste_id = created.get_json()["id"]

    denied = client.delete(f"/api/pastes/{paste_id}", headers={"X-Admin-Token": "wrong"})
    assert denied.status_code == 403

    deleted = client.delete(
        f"/api/pastes/{paste_id}",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/pastes/{paste_id}").status_code == 404


@pytest.mark.parametrize("route", ["/api/pastes/", "/p/"])
def test_missing_paste_is_not_found(route):
    response = paste_app.app.test_client().get(f"{route}nonexistent-paste")
    assert response.status_code == 404
    if route.startswith("/api/"):
        assert response.is_json
        assert response.get_json() == {"error": "Paste not found"}
    else:
        assert response.get_data(as_text=True) == "Paste not found"


@pytest.mark.parametrize("route", ["/api/pastes/", "/p/"])
def test_expired_paste_is_removed_and_not_returned(route, monkeypatch):
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(paste_app, "now_utc", lambda: now)
    with paste_app.connect() as db:
        db.execute(
            "INSERT INTO pastes (id, title, content, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            ("expired", "expired-title-marker", "expired-content-marker",
             paste_app.stamp(now - timedelta(hours=2)),
             paste_app.stamp(now - timedelta(hours=1))),
        )
        assert db.execute("SELECT id FROM pastes WHERE id = 'expired'").fetchone() is not None

    response = paste_app.app.test_client().get(f"{route}expired")
    assert response.status_code == 404
    assert "expired-title-marker" not in response.get_data(as_text=True)
    assert "expired-content-marker" not in response.get_data(as_text=True)
    if route.startswith("/api/"):
        assert response.is_json
        assert response.get_json() == {"error": "Paste not found"}
    else:
        assert response.get_data(as_text=True) == "Paste not found"
    with paste_app.connect() as db:
        assert db.execute("SELECT id FROM pastes WHERE id = 'expired'").fetchone() is None


@pytest.mark.parametrize("route", ["/api/pastes/", "/p/"])
@pytest.mark.parametrize("ttl_hours", [1, None], ids=["future-expiry", "no-expiry"])
def test_unexpired_paste_remains_readable(route, ttl_hours, monkeypatch):
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(paste_app, "now_utc", lambda: now)
    paste_id = paste_app.create_paste("still-readable-marker", "live note", ttl_hours)
    response = paste_app.app.test_client().get(f"{route}{paste_id}")
    assert response.status_code == 200
    if route.startswith("/api/"):
        assert response.get_json()["content"] == "still-readable-marker"
    else:
        assert "still-readable-marker" in response.get_data(as_text=True)
    with paste_app.connect() as db:
        assert db.execute("SELECT id FROM pastes WHERE id = ?", (paste_id,)).fetchone() is not None
