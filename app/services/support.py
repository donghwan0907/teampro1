from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"


@lru_cache(maxsize=8)
def _load_json(filename: str) -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def regions() -> list[dict[str, Any]]:
    return deepcopy(_load_json("regions.json"))


def guarantees() -> list[dict[str, Any]]:
    return deepcopy(_load_json("guarantee_products.json"))


def _region_prefix(region_code: str | None) -> str | None:
    if region_code is None:
        return None
    text = str(region_code).strip()
    return text[:2] if len(text) >= 2 else text.zfill(2)


def _region_record(region_code: str | None) -> dict[str, Any] | None:
    prefix = _region_prefix(region_code)
    return next((item for item in regions() if item["code"] == prefix), None)


def _regional_fee_fallback(region: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"{region['code']}_FEE_FALLBACK",
        "scope": "regional",
        "region_code": region["code"],
        "title": f"{region['name']} 전세보증금 반환보증 보증료 지원 확인",
        "category": "보증료",
        "summary": "국토교통부 보증료 지원사업은 지자체가 접수·지급하므로 해당 지역의 예산 소진 여부와 접수방법을 확인해야 합니다.",
        "target_summary": "반환보증 가입·보증금·소득·무주택 요건 충족 임차인",
        "benefit_summary": "기납부 보증료 최대 40만원 범위",
        "status": "check",
        "status_label": "지역 예산·접수처 확인",
        "official_url": region["support_url"],
        "apply_url": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/161300000103",
        "source_name": region["name"],
        "phone": "관할 시군구 주택부서",
        "verified_at": region.get("verified_at", "2026-08-03"),
        "conditions": {
            "guarantee_joined": True,
            "deposit_max": 300000000,
            "renter": True,
            "income_rules": {"youth": 50000000, "general": 60000000, "newlywed": 75000000},
        },
    }


def programs(region_code: str | None = None, include_national: bool = True) -> list[dict[str, Any]]:
    prefix = _region_prefix(region_code)
    all_programs = deepcopy(_load_json("support_programs.json"))
    selected = [
        item for item in all_programs
        if (include_national and item.get("scope") == "national")
        or (prefix and item.get("region_code") == prefix)
    ]
    region = _region_record(prefix)
    if region and not any(item.get("category") == "보증료" and item.get("scope") == "regional" for item in selected):
        selected.append(_regional_fee_fallback(region))
    return selected


def _bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    return None


def _match_program(program: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(program)
    conditions = program.get("conditions") or {}
    passed: list[str] = []
    pending: list[str] = []
    failed: list[str] = []

    region = _region_prefix(profile.get("region_code"))
    if program.get("scope") == "regional" and program.get("region_code") != region:
        failed.append("선택한 지역의 사업이 아닙니다.")

    deposit = float(profile.get("deposit") or 0)
    if conditions.get("deposit_max"):
        if deposit <= 0:
            pending.append("보증금 확인 필요")
        elif deposit <= float(conditions["deposit_max"]):
            passed.append("보증금 기준 충족 가능")
        else:
            failed.append("보증금 기준 초과")

    for key, label in [
        ("guarantee_joined", "반환보증 가입"),
        ("victim_confirmed", "피해자등 결정"),
        ("moved", "피해주택에서 이주"),
        ("renter", "임차인·무주택 여부"),
    ]:
        if key not in conditions:
            continue
        expected = bool(conditions[key])
        actual = _bool(profile, key)
        if actual is None:
            pending.append(f"{label} 확인 필요")
        elif actual == expected:
            passed.append(f"{label} 조건 충족")
        else:
            failed.append(f"{label} 조건 불충족")

    income_rules = conditions.get("income_rules")
    if income_rules:
        income = float(profile.get("annual_income") or 0)
        age = int(profile.get("age") or 0)
        marital = str(profile.get("marital_status") or "general")
        group = "newlywed" if marital == "newlywed" else ("youth" if age and age <= 39 else "general")
        limit = float(income_rules[group])
        if income <= 0:
            pending.append("연소득 확인 필요")
        elif income <= limit:
            passed.append(f"소득 기준 충족 가능({int(limit):,}원 이하)")
        else:
            failed.append(f"소득 기준 초과 가능({int(limit):,}원 기준)")

    if failed:
        status = "대상 아님 가능성"
        rank = 3
    elif pending:
        status = "조건 확인"
        rank = 2
    else:
        status = "신청 가능성 있음"
        rank = 1

    result["match_status"] = status
    result["match_rank"] = rank
    result["match_reasons"] = passed
    result["pending_checks"] = pending
    result["failed_reasons"] = failed
    result["final_note"] = "예상 선별 결과이며 최종 지원 여부는 담당기관의 접수·심사로 결정됩니다."
    return result


def match_programs(profile: dict[str, Any]) -> dict[str, Any]:
    region = _region_record(profile.get("region_code"))
    matched = [_match_program(item, profile) for item in programs(profile.get("region_code"), include_national=True)]
    matched.sort(key=lambda item: (item["match_rank"], 0 if item.get("scope") == "regional" else 1, item["title"]))
    return {
        "region": region,
        "items": matched,
        "guarantees": guarantees(),
        "disclaimer": "조건 기반 예상 결과이며 사업 예산, 접수기간, 제출서류와 최종 자격은 공식 페이지와 담당기관에서 다시 확인해야 합니다.",
    }
