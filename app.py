import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, url_for
from collections import deque
from threading import Lock
import time

from werkzeug.exceptions import BadRequest, HTTPException

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "pastes.db"
MAX_PASTE_BYTES = 1024 * 1024  # 1 MiB
DEFAULT_TTL_HOURS = int(os.environ.get("DEFAULT_TTL_HOURS", "24"))
ADMIN_TOKEN = os.environ.get("PASTE_ADMIN_TOKEN", "")
RATE_LIMIT_PER_MINUTE = int(os.environ.get("PASTE_RATE_LIMIT", "0"))

_rate_limit_store: dict[str, deque[float]] = {}
_store_lock = Lock()


def check_rate_limit(ip: str, limit: int | None = None, window: int = 60) -> tuple[bool, int]:
    effective_limit = RATE_LIMIT_PER_MINUTE if limit is None else limit
    if effective_limit <= 0:
        return True, 0
    now = time.time()
    cutoff = now - window
    with _store_lock:
        dq = _rate_limit_store.setdefault(ip, deque())
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= effective_limit:
            retry_after = max(int(dq[0] + window - now) + 1, 1)
            return False, retry_after
        dq.append(now)
        return True, 0


def reset_rate_limits():
    with _store_lock:
        _rate_limit_store.clear()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_PASTE_BYTES + 8192


class PasteValidationError(ValueError):
    """A client input error, distinct from unexpected storage failures."""


def now_utc():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.isoformat(timespec="seconds")


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS pastes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_pastes_created ON pastes(created_at)")


def cleanup_expired(db):
    db.execute("DELETE FROM pastes WHERE expires_at IS NOT NULL AND expires_at <= ?", (stamp(now_utc()),))


def get_paste(paste_id):
    with connect() as db:
        cleanup_expired(db)
        row = db.execute("SELECT * FROM pastes WHERE id = ?", (paste_id,)).fetchone()
    return row


def parse_ttl(value):
    if value in (None, "", "default"):
        return DEFAULT_TTL_HOURS
    if value == "never":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise PasteValidationError("ttl_hours must be 1, 24, 168, or 'never'")
    try:
        hours = int(value)
    except (TypeError, ValueError):
        raise PasteValidationError("ttl_hours must be 1, 24, 168, or 'never'") from None
    if hours not in (1, 24, 168):
        raise PasteValidationError("ttl_hours must be 1, 24, 168, or 'never'")
    return hours


def create_paste(content, title="", ttl_hours=None):
    if not isinstance(content, str) or not isinstance(title, str):
        raise PasteValidationError("content and title must be strings")
    if not content or not content.strip():
        raise PasteValidationError("Paste content cannot be empty")
    try:
        encoded_content = content.encode("utf-8")
        title.encode("utf-8")
    except UnicodeEncodeError:
        raise PasteValidationError("content and title must be valid UTF-8") from None
    if len(encoded_content) > MAX_PASTE_BYTES:
        raise PasteValidationError("Paste is too large; maximum is 1 MiB")
    created = now_utc()
    expires = created + timedelta(hours=ttl_hours) if ttl_hours is not None else None
    paste_id = secrets.token_urlsafe(9)
    with connect() as db:
        cleanup_expired(db)
        db.execute(
            "INSERT INTO pastes (id, title, content, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (paste_id, title[:120].strip(), content, stamp(created), stamp(expires) if expires else None),
        )
    return paste_id


@app.get("/")
def index():
    with connect() as db:
        cleanup_expired(db)
        rows = db.execute("SELECT id, title, created_at, expires_at, substr(content, 1, 180) AS preview FROM pastes ORDER BY created_at DESC LIMIT 50").fetchall()
    return render_template("index.html", pastes=rows, default_ttl=DEFAULT_TTL_HOURS)


@app.get("/p/<paste_id>")
def view_paste(paste_id):
    paste = get_paste(paste_id)
    if paste is None:
        abort(404)
    return render_template("paste.html", paste=paste)


@app.post("/api/pastes")
def api_create():
    ip = request.remote_addr or "unknown"
    allowed, retry_after = check_rate_limit(ip)
    if not allowed:
        resp = jsonify(error="Rate limit exceeded; please wait before creating more pastes")
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp
    # JSON is convenient for scripts; raw request bodies work well with curl and stdin.
    if request.is_json:
        try:
            payload = request.get_json()
        except BadRequest:
            return jsonify(error="Request body must contain valid JSON"), 400
        if not isinstance(payload, dict):
            return jsonify(error="JSON body must be an object"), 400
        content = payload.get("content", "")
        title = payload.get("title", "")
        ttl_value = payload.get("ttl_hours", "default")
    else:
        content = request.get_data(as_text=True)
        title = request.headers.get("X-Paste-Title", "")
        ttl_value = request.headers.get("X-Paste-TTL", "default")
    if not isinstance(content, str) or not isinstance(title, str):
        return jsonify(error="content and title must be strings"), 400
    try:
        ttl = parse_ttl(ttl_value)
        paste_id = create_paste(content, title, ttl)
    except PasteValidationError as exc:
        return jsonify(error=str(exc)), 400
    paste_url = url_for("view_paste", paste_id=paste_id, _external=True)
    return jsonify(id=paste_id, url=paste_url, expires_in_hours=ttl), 201


@app.get("/api/pastes")
def api_list():
    with connect() as db:
        cleanup_expired(db)
        rows = db.execute("SELECT id, title, created_at, expires_at, substr(content, 1, 180) AS preview FROM pastes ORDER BY created_at DESC LIMIT 50").fetchall()
    return jsonify(pastes=[dict(row) for row in rows])


@app.get("/api/pastes/<paste_id>")
def api_get(paste_id):
    paste = get_paste(paste_id)
    if paste is None:
        abort(404)
    return jsonify(dict(paste))


@app.delete("/api/pastes/<paste_id>")
def api_delete(paste_id):
    if not ADMIN_TOKEN:
        return jsonify(error="Deletion is disabled until PASTE_ADMIN_TOKEN is configured"), 503
    supplied = request.headers.get("X-Admin-Token", "")
    if not secrets.compare_digest(supplied, ADMIN_TOKEN):
        return jsonify(error="Invalid admin token"), 403
    with connect() as db:
        result = db.execute("DELETE FROM pastes WHERE id = ?", (paste_id,))
    if result.rowcount == 0:
        abort(404)
    return "", 204


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify(error="Paste not found"), 404
    return "Paste not found", 404


@app.errorhandler(413)
def too_large(_error):
    if not request.path.startswith("/api/"):
        return _error
    return jsonify(error="Request too large; maximum paste size is 1 MiB"), 413


@app.errorhandler(HTTPException)
def http_error(error):
    if not request.path.startswith("/api/"):
        return error
    # Keep HTTP metadata such as Allow on 405 responses.
    response = error.get_response()
    response.set_data(app.json.dumps({"error": error.description}))
    response.content_type = "application/json"
    return response


@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith("/api/"):
        return jsonify(error="Internal server error"), 500
    return error


init_db()

if __name__ == "__main__":
    # For local development only. Docker runs Gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=8000, debug=False)
