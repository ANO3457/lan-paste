import os
import tempfile
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
