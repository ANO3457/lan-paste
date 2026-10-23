import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Give the imported app an isolated SQLite database for this test run.
_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix="lan-paste-tests-")
os.environ["DATA_DIR"] = _TEST_DATA_DIR.name
os.environ["PASTE_ADMIN_TOKEN"] = "test-admin-token"
os.environ["DEFAULT_TTL_HOURS"] = "24"

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


def assert_api_error(response, status):
    assert response.status_code == status
    assert response.is_json
    payload = response.get_json()
    assert set(payload) == {"error"}
    assert isinstance(payload["error"], str) and payload["error"].strip()
    return payload["error"]


@pytest.mark.parametrize("body", [
    b'{"content":', b'', b'{"content":"\xff"}',
    b'null', b'[]', b'["note"]', b'"note"', b'123', b'true', b'false',
])
def test_invalid_json_has_a_useful_client_error(body):
    response = paste_app.app.test_client().post(
        "/api/pastes", data=body, content_type="application/json"
    )
    assert "JSON" in assert_api_error(response, 400)


@pytest.mark.parametrize("payload", [
    {}, {"content": ""}, {"content": " \n\t"},
    {"content": None}, {"content": []}, {"content": 42},
    {"content": "note", "title": None},
    {"content": "note", "title": []},
    {"content": "note", "title": 42},
])
def test_invalid_json_fields_are_client_errors(payload):
    response = paste_app.app.test_client().post("/api/pastes", json=payload)
    assert_api_error(response, 400)


@pytest.mark.parametrize("content,title", [
    (42, ""), ("note", None), ("note", []),
])
def test_create_paste_rejects_non_string_fields_before_string_operations(content, title):
    with pytest.raises(paste_app.PasteValidationError, match="content and title must be strings"):
        paste_app.create_paste(content, title)
    with paste_app.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM pastes").fetchone()[0] == 0


@pytest.mark.parametrize("ttl", [True, False, 24.0, 24.5, [], {}, 5, "invalid"])
def test_invalid_ttl_is_not_coerced_to_an_allowed_hour(ttl):
    response = paste_app.app.test_client().post(
        "/api/pastes", json={"content": "note", "ttl_hours": ttl}
    )
    assert "ttl_hours" in assert_api_error(response, 400)


@pytest.mark.parametrize("raw,ttl,expected", [
    (False, None, 24), (False, "", 24), (False, "default", 24),
    (False, 1, 1), (False, "24", 24), (False, 168, 168),
    (False, "never", None), (True, None, 24),
    (True, "default", 24), (True, "1", 1), (True, "never", None),
])
def test_valid_requests_keep_their_content_title_and_expiry(raw, ttl, expected):
    client = paste_app.app.test_client()
    content = "ordinary note\nwith a second line"
    if raw:
        headers = {"X-Paste-Title": "raw note"}
        if ttl is not None:
            headers["X-Paste-TTL"] = ttl
        response = client.post(
            "/api/pastes", data=content, content_type="text/plain", headers=headers
        )
        title = "raw note"
    else:
        response = client.post(
            "/api/pastes", json={"title": "JSON note", "content": content, "ttl_hours": ttl}
        )
        title = "JSON note"
    assert response.status_code == 201
    created = response.get_json()
    assert created["id"] and created["url"].endswith("/p/" + created["id"])
    assert created["expires_in_hours"] == expected
    fetched = client.get("/api/pastes/" + created["id"])
    assert fetched.status_code == 200
    stored = fetched.get_json()
    assert stored["content"] == content and stored["title"] == title
    assert (stored["expires_at"] is None) == (expected is None)


@pytest.mark.parametrize("size,status", [
    (paste_app.MAX_PASTE_BYTES, 201),
    (paste_app.MAX_PASTE_BYTES + 1, 400),
    (paste_app.app.config["MAX_CONTENT_LENGTH"] + 1, 413),
])
def test_paste_and_request_size_boundaries(size, status):
    response = paste_app.app.test_client().post(
        "/api/pastes", data="x" * size, content_type="text/plain"
    )
    if status == 201:
        assert response.status_code == 201
    else:
        assert_api_error(response, status)


def test_missing_pastes_and_methods_keep_status_and_http_headers():
    client = paste_app.app.test_client()
    assert_api_error(client.get("/api/pastes/missing-id"), 404)
    response = client.post("/api/pastes/missing-id")
    assert_api_error(response, 405)
    assert {"GET", "DELETE"} <= set(response.headers["Allow"].replace(" ", "").split(","))
    for method, status in (("get", 404), ("post", 405)):
        response = getattr(client, method)("/p/missing-id")
        assert response.status_code == status and not response.is_json


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_unexpected_storage_errors_are_not_exposed(monkeypatch, error_type):
    detail = "synthetic-internal-detail-that-must-not-reach-the-client"

    def fail_connection():
        raise error_type(detail)

    monkeypatch.setattr(paste_app, "connect", fail_connection)
    # Exercise Flask's real production error response rather than propagate exceptions.
    monkeypatch.setitem(paste_app.app.config, "PROPAGATE_EXCEPTIONS", False)
    client = paste_app.app.test_client()
    response = client.post("/api/pastes", json={"content": "safe note"})
    assert_api_error(response, 500)
    assert detail not in response.get_data(as_text=True)
    response = client.get("/")
    assert response.status_code == 500 and not response.is_json
    assert detail not in response.get_data(as_text=True)


@pytest.mark.parametrize("field", ["content", "title"])
@pytest.mark.parametrize("value", ["\ud800", "\udfff"])
def test_invalid_unicode_fields_are_client_errors(field, value):
    payload = {"content": "safe note", "title": "safe title"}
    payload[field] = value
    response = paste_app.app.test_client().post("/api/pastes", json=payload)
    assert "UTF-8" in assert_api_error(response, 400)


def test_valid_unicode_pair_is_preserved_in_both_fields():
    client = paste_app.app.test_client()
    response = client.post(
        "/api/pastes", data=br'{"content":"\ud83d\ude00","title":"\ud83d\ude00"}',
        content_type="application/json",
    )
    assert response.status_code == 201
    stored = client.get("/api/pastes/" + response.get_json()["id"]).get_json()
    assert stored["content"] == stored["title"] == "\U0001f600"


@pytest.mark.parametrize("extra,status", [("", 201), ("x", 400)])
def test_size_limit_counts_utf8_bytes(extra, status):
    content = "\U0001f600" * (paste_app.MAX_PASTE_BYTES // 4) + extra
    body = b'{"content":"' + content.encode("utf-8") + b'"}'
    response = paste_app.app.test_client().post(
        "/api/pastes", data=body, content_type="application/json"
    )
    if status == 201:
        assert response.status_code == 201
    else:
        assert_api_error(response, status)


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


@pytest.mark.parametrize("env_val,expected", [
    ("24", 24),
    ("1", 1),
    ("168", 168),
    (None, 24),
])
def test_load_default_ttl_valid(env_val, expected, monkeypatch):
    if env_val is None:
        monkeypatch.delenv("DEFAULT_TTL_HOURS", raising=False)
        assert paste_app.load_default_ttl() == expected
    else:
        monkeypatch.setenv("DEFAULT_TTL_HOURS", env_val)
        assert paste_app.load_default_ttl() == expected


@pytest.mark.parametrize("invalid_val", ["0", "-1", "48", "999", "never", "invalid", "24.5"])
def test_load_default_ttl_invalid_raises_value_error(invalid_val, monkeypatch):
    monkeypatch.setenv("DEFAULT_TTL_HOURS", invalid_val)
    with pytest.raises(ValueError, match="Invalid DEFAULT_TTL_HOURS"):
        paste_app.load_default_ttl()
