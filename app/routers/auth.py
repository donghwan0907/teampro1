from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import settings
from app.db import (
    authenticate_user,
    create_session,
    create_user,
    delete_session,
    read_checklist,
    save_checklist,
    user_from_session,
)

router = APIRouter(prefix="/auth", tags=["로그인·체크리스트"])
COOKIE_NAME = "safelease_session"
ALLOWED_KEYS = {
    "price", "building", "registry", "senior", "owner", "broker", "guarantee",
    "explain", "clause", "payment", "day_registry", "day_cancel", "day_identity",
    "move", "guarantee_done",
}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _current_user(request: Request) -> dict:
    user = user_from_session(request.cookies.get(COOKIE_NAME))
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def _clean_checklist(raw_state: object) -> dict:
    if not isinstance(raw_state, dict):
        raise HTTPException(status_code=400, detail="체크리스트 형식이 올바르지 않습니다.")
    cleaned: dict[str, dict] = {}
    for key, value in raw_state.items():
        if key not in ALLOWED_KEYS or not isinstance(value, dict):
            continue
        date_text = str(value.get("date") or "")
        cleaned[key] = {
            "checked": value.get("checked") is True,
            "date": date_text if not date_text or DATE_PATTERN.fullmatch(date_text) else "",
        }
    return cleaned


@router.post("/register", status_code=201)
def register(payload: dict, response: Response):
    try:
        user = create_user(payload.get("username", ""), payload.get("password", ""))
    except ValueError as error:
        message = str(error)
        raise HTTPException(status_code=409 if "사용 중" in message else 400, detail=message) from error
    token = create_session(user["id"])
    _set_session_cookie(response, token)
    return {"authenticated": True, "user": {"username": user["username"]}}


@router.post("/login")
def login(payload: dict, response: Response):
    user = authenticate_user(payload.get("username", ""), payload.get("password", ""))
    if not user:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_session(user["id"])
    _set_session_cookie(response, token)
    return {"authenticated": True, "user": {"username": user["username"]}}


@router.post("/logout")
def logout(request: Request, response: Response):
    delete_session(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/", samesite="lax")
    return {"authenticated": False}


@router.get("/me")
def me(request: Request):
    user = user_from_session(request.cookies.get(COOKIE_NAME))
    return {
        "authenticated": bool(user),
        "user": {"username": user["username"]} if user else None,
    }


@router.get("/checklist")
def get_checklist(request: Request):
    user = _current_user(request)
    return read_checklist(user["id"])


@router.put("/checklist")
def put_checklist(payload: dict, request: Request):
    user = _current_user(request)
    state = _clean_checklist(payload.get("state"))
    try:
        updated_at = save_checklist(user["id"], state)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"saved": True, "updated_at": updated_at, "items": len(state)}
