from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from collections.abc import Iterator

from app.config import settings
from app.supabase_store import (
    DuplicateUserError,
    SupabaseStore,
    SupabaseStoreError,
    is_future_iso,
)

PersistenceUnavailable = SupabaseStoreError
PASSWORD_ITERATIONS = 260_000
SESSION_DAYS = 7
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9가-힣._-]{3,24}$")


def _database_path() -> Path:
    raw_path = str(settings.database_url).removeprefix("sqlite:///")
    path = Path(raw_path)
    return path if path.is_absolute() else settings.project_dir / path


DB_PATH = _database_path()


def _backend_name() -> str:
    requested = str(settings.persistence_backend or "auto").strip().lower()
    if requested not in {"auto", "sqlite", "supabase"}:
        requested = "auto"
    if requested == "auto":
        return "supabase" if settings.supabase_configured else "sqlite"
    return requested


@lru_cache(maxsize=1)
def _supabase() -> SupabaseStore:
    if not settings.supabase_configured:
        raise PersistenceUnavailable(
            "Supabase 서버 설정이 비어 있습니다. .env의 SUPABASE_URL과 SUPABASE_SECRET_KEY를 확인하세요."
        )
    return SupabaseStore(
        settings.supabase_url,
        settings.supabase_secret_key,
        settings.supabase_timeout_seconds,
    )


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database() -> None:
    """오프라인 대체 저장소인 SQLite를 준비합니다. 원격 DDL은 실행하지 않습니다."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_iterations INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS sessions_expires_idx ON sessions(expires_at)")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS checklists (
                user_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


def validate_credentials(username: str, password: str) -> tuple[str, str]:
    normalized = str(username or "").strip()
    secret = str(password or "")
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("아이디는 한글·영문·숫자·._- 조합 3~24자로 입력하세요.")
    if len(secret) < 8 or len(secret) > 72:
        raise ValueError("비밀번호는 8~72자로 입력하세요.")
    return normalized, secret


def _password_digest(password: str, salt: bytes, iterations: int = PASSWORD_ITERATIONS) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def create_user(username: str, password: str) -> dict:
    normalized, secret = validate_credentials(username, password)
    salt = secrets.token_bytes(16)
    digest = _password_digest(secret, salt)
    created_at = datetime.now(UTC).isoformat()

    if _backend_name() == "supabase":
        try:
            row = _supabase().create_user(
                {
                    "username": normalized,
                    "username_key": normalized.casefold(),
                    "password_hash": digest,
                    "password_salt": salt.hex(),
                    "password_iterations": PASSWORD_ITERATIONS,
                    "created_at": created_at,
                }
            )
        except DuplicateUserError:
            raise
        return {"id": int(row["id"]), "username": str(row["username"])}

    try:
        with _connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users(username,password_hash,password_salt,password_iterations,created_at) VALUES(?,?,?,?,?)",
                (normalized, digest, salt.hex(), PASSWORD_ITERATIONS, created_at),
            )
            return {"id": int(cursor.lastrowid), "username": normalized}
    except sqlite3.IntegrityError as error:
        raise ValueError("이미 사용 중인 아이디입니다.") from error


def authenticate_user(username: str, password: str) -> dict | None:
    normalized = str(username or "").strip()
    secret = str(password or "")
    if _backend_name() == "supabase":
        row = _supabase().find_user_by_key(normalized.casefold())
    else:
        with _connect() as connection:
            row = connection.execute(
                "SELECT id,username,password_hash,password_salt,password_iterations FROM users WHERE username = ? COLLATE NOCASE",
                (normalized,),
            ).fetchone()

    if row is None:
        # 계정 존재 여부에 따른 응답 시간 차이를 줄이기 위한 더미 계산입니다.
        _password_digest(secret, b"safelease-dummy!", PASSWORD_ITERATIONS)
        return None
    candidate = _password_digest(secret, bytes.fromhex(row["password_salt"]), int(row["password_iterations"]))
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return None
    return {"id": int(row["id"]), "username": str(row["username"])}


def create_session(user_id: int) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=SESSION_DAYS)

    if _backend_name() == "supabase":
        store = _supabase()
        store.delete_expired_sessions(now.isoformat())
        store.create_session(
            {
                "user_id": int(user_id),
                "token_hash": token_hash,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        )
        return raw_token

    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now.isoformat(),))
        connection.execute(
            "INSERT INTO sessions(user_id,token_hash,created_at,expires_at) VALUES(?,?,?,?)",
            (user_id, token_hash, now.isoformat(), expires_at.isoformat()),
        )
    return raw_token


def user_from_session(raw_token: str | None) -> dict | None:
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    if _backend_name() == "supabase":
        store = _supabase()
        session = store.find_session(token_hash)
        if not session or not is_future_iso(str(session.get("expires_at") or "")):
            if session:
                store.delete_session(token_hash)
            return None
        user = store.find_user_by_id(int(session["user_id"]))
        return {"id": int(user["id"]), "username": str(user["username"])} if user else None

    now = datetime.now(UTC).isoformat()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT users.id, users.username
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
    return {"id": int(row["id"]), "username": row["username"]} if row else None


def delete_session(raw_token: str | None) -> None:
    if not raw_token:
        return
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    if _backend_name() == "supabase":
        _supabase().delete_session(token_hash)
        return
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def read_checklist(user_id: int) -> dict:
    if _backend_name() == "supabase":
        row = _supabase().read_checklist(user_id)
        if not row:
            return {"state": {}, "updated_at": None}
        state = row.get("state_json")
        return {"state": state if isinstance(state, dict) else {}, "updated_at": row.get("updated_at")}

    with _connect() as connection:
        row = connection.execute(
            "SELECT state_json,updated_at FROM checklists WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return {"state": {}, "updated_at": None}
    try:
        state = json.loads(row["state_json"])
    except json.JSONDecodeError:
        state = {}
    return {"state": state if isinstance(state, dict) else {}, "updated_at": row["updated_at"]}


def save_checklist(user_id: int, state: dict) -> str:
    updated_at = datetime.now(UTC).isoformat()
    state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    if len(state_json.encode("utf-8")) > 50_000:
        raise ValueError("체크리스트 데이터가 허용 크기를 초과했습니다.")

    if _backend_name() == "supabase":
        _supabase().save_checklist(
            {"user_id": int(user_id), "state_json": state, "updated_at": updated_at}
        )
        return updated_at

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO checklists(user_id,state_json,updated_at) VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at
            """,
            (user_id, state_json, updated_at),
        )
    return updated_at


def read_supabase_memos(limit: int = 20) -> list[dict]:
    if _backend_name() != "supabase":
        return []
    return _supabase().read_memos(limit)


def database_status() -> dict:
    backend = _backend_name()
    if backend == "supabase":
        if not settings.supabase_configured:
            return {
                "backend": "supabase",
                "configured": False,
                "connected": False,
                "ready": False,
                "tables": [],
                "error": "SUPABASE_URL과 SUPABASE_SECRET_KEY가 필요합니다.",
            }
        try:
            return _supabase().status()
        except PersistenceUnavailable as error:
            return {
                "backend": "supabase",
                "configured": True,
                "connected": False,
                "ready": False,
                "project_url": settings.supabase_url.rstrip("/"),
                "tables": [],
                "error": str(error),
            }

    init_database()
    with _connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    required = {"users", "sessions", "checklists"}
    return {
        "backend": "sqlite",
        "configured": True,
        "connected": True,
        "path": str(DB_PATH),
        "ready": required.issubset(tables),
        "tables": sorted(required & tables),
    }
