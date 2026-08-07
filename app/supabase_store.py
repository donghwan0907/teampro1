from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class SupabaseStoreError(RuntimeError):
    """Supabase 요청이 실패했지만 비밀 키는 노출하지 않는 예외입니다."""


class DuplicateUserError(ValueError):
    pass


class SupabaseStore:
    USERS_TABLE = "safelease_users"
    SESSIONS_TABLE = "safelease_sessions"
    CHECKLISTS_TABLE = "safelease_checklists"
    MEMOS_TABLE = "memos"

    def __init__(self, project_url: str, secret_key: str, timeout_seconds: float = 10.0):
        self.project_url = project_url.strip().rstrip("/")
        self.secret_key = secret_key.strip()
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        if not self.project_url.startswith("https://") or not self.secret_key:
            raise SupabaseStoreError("Supabase URL 또는 서버 비밀 키가 설정되지 않았습니다.")

    def _request(
        self,
        method: str,
        table: str,
        *,
        query: dict[str, str] | None = None,
        payload: Any | None = None,
        prefer: str | None = None,
    ) -> Any:
        table_path = quote(table, safe="")
        url = f"{self.project_url}/rest/v1/{table_path}"
        if query:
            url += "?" + urlencode(query)

        data = None
        headers = {
            "apikey": self.secret_key,
            "Accept": "application/json",
            "User-Agent": "SafeLease-FastAPI/4.0",
        }
        # 새 sb_secret 키는 apikey 헤더만 사용합니다. 기존 service_role JWT는
        # Supabase의 레거시 인증 방식에 맞춰 Bearer 헤더도 함께 보냅니다.
        if self.secret_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.secret_key}"
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if prefer:
            headers["Prefer"] = prefer

        request = Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as error:
            detail = ""
            try:
                body = json.loads(error.read().decode("utf-8", errors="replace"))
                detail = str(body.get("message") or body.get("details") or body.get("hint") or "")
            except (json.JSONDecodeError, AttributeError):
                detail = ""
            message = f"Supabase 요청 실패(HTTP {error.code})"
            if detail:
                message += f": {detail[:240]}"
            raise SupabaseStoreError(message) from error
        except (URLError, TimeoutError, OSError) as error:
            raise SupabaseStoreError("Supabase에 연결할 수 없습니다. 네트워크와 .env 설정을 확인하세요.") from error

        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise SupabaseStoreError("Supabase가 올바르지 않은 JSON 응답을 반환했습니다.") from error

    def create_user(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self._request(
                "POST",
                self.USERS_TABLE,
                payload=row,
                prefer="return=representation",
            )
        except SupabaseStoreError as error:
            if "HTTP 409" in str(error) or "duplicate key" in str(error).lower():
                raise DuplicateUserError("이미 사용 중인 아이디입니다.") from error
            raise
        if not isinstance(result, list) or not result:
            raise SupabaseStoreError("Supabase 회원 저장 결과를 확인할 수 없습니다.")
        return result[0]

    def find_user_by_key(self, username_key: str) -> dict[str, Any] | None:
        result = self._request(
            "GET",
            self.USERS_TABLE,
            query={
                "select": "id,username,password_hash,password_salt,password_iterations",
                "username_key": f"eq.{username_key}",
                "limit": "1",
            },
        )
        return result[0] if isinstance(result, list) and result else None

    def find_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        result = self._request(
            "GET",
            self.USERS_TABLE,
            query={"select": "id,username", "id": f"eq.{int(user_id)}", "limit": "1"},
        )
        return result[0] if isinstance(result, list) and result else None

    def create_session(self, row: dict[str, Any]) -> None:
        self._request("POST", self.SESSIONS_TABLE, payload=row, prefer="return=minimal")

    def find_session(self, token_hash: str) -> dict[str, Any] | None:
        result = self._request(
            "GET",
            self.SESSIONS_TABLE,
            query={
                "select": "user_id,expires_at",
                "token_hash": f"eq.{token_hash}",
                "limit": "1",
            },
        )
        return result[0] if isinstance(result, list) and result else None

    def delete_session(self, token_hash: str) -> None:
        self._request(
            "DELETE",
            self.SESSIONS_TABLE,
            query={"token_hash": f"eq.{token_hash}"},
            prefer="return=minimal",
        )

    def delete_expired_sessions(self, now_iso: str) -> None:
        self._request(
            "DELETE",
            self.SESSIONS_TABLE,
            query={"expires_at": f"lte.{now_iso}"},
            prefer="return=minimal",
        )

    def read_checklist(self, user_id: int) -> dict[str, Any] | None:
        result = self._request(
            "GET",
            self.CHECKLISTS_TABLE,
            query={
                "select": "state_json,updated_at",
                "user_id": f"eq.{int(user_id)}",
                "limit": "1",
            },
        )
        return result[0] if isinstance(result, list) and result else None

    def save_checklist(self, row: dict[str, Any]) -> None:
        self._request(
            "POST",
            self.CHECKLISTS_TABLE,
            query={"on_conflict": "user_id"},
            payload=row,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def read_memos(self, limit: int = 20) -> list[dict[str, Any]]:
        result = self._request(
            "GET",
            self.MEMOS_TABLE,
            query={"select": "id,title,content", "order": "id.asc", "limit": str(max(1, min(limit, 100)))},
        )
        return result if isinstance(result, list) else []

    def status(self) -> dict[str, Any]:
        tables: list[str] = []
        errors: dict[str, str] = {}
        for table in (self.USERS_TABLE, self.SESSIONS_TABLE, self.CHECKLISTS_TABLE):
            try:
                self._request("GET", table, query={"select": "*", "limit": "1"})
                tables.append(table)
            except SupabaseStoreError as error:
                errors[table] = str(error)
        return {
            "backend": "supabase",
            "configured": True,
            "connected": bool(tables),
            "ready": len(tables) == 3,
            "project_url": self.project_url,
            "tables": tables,
            "errors": errors,
        }


def is_future_iso(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed > datetime.now(UTC)
    except ValueError:
        return False
