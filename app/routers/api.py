from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.db import database_status
from app.services.risk import calculate_property_risk

router = APIRouter()

SEOUL_WEIGHTS = {
    "market_risk_score": {
        "label": "법정동 시장 위험",
        "weight": 0.60,
        "description": "주택유형·면적대별 매매와 순수전세 거래를 매칭한 전세가율, 고전세가율 비중, 가격·거래량 변화",
    },
    "building_risk_score": {
        "label": "건물구조 위험",
        "weight": 0.25,
        "description": "비아파트·노후 주거건물·혼합용도·세대 대비 주차 구조의 서울 내 상대위치",
    },
    "district_context_score": {
        "label": "자치구 공식 배경",
        "weight": 0.15,
        "description": "2023~2025년 자치구 공식 가결건수의 세대수 보정값과 업로드된 보증사고 보조지표",
    },
}


@router.get("/integration-status")
def integration_status():
    """키 값은 제외하고 현재 영속 저장소 연결 상태만 반환합니다."""
    return database_status()


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", force_ascii=False, date_format="iso"))


@lru_cache(maxsize=12)
def _read_json(path_text: str) -> dict:
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


@lru_cache(maxsize=6)
def _read_csv(path_text: str) -> pd.DataFrame:
    return pd.read_csv(
        path_text,
        dtype={"legal_dong_code": str, "sigungu_code": str},
        low_memory=False,
    )


def _geojson(filename: str) -> dict:
    path = settings.geojson_dir / filename
    if not path.exists():
        raise HTTPException(404, f"{filename}이 아직 생성되지 않았습니다.")
    return _read_json(str(path.resolve()))


def _risk_data() -> pd.DataFrame:
    path = settings.processed_dir / "seoul_dong_risk_latest.csv"
    if not path.exists():
        raise HTTPException(404, "서울 법정동 위험도 데이터가 아직 생성되지 않았습니다.")
    frame = _read_csv(str(path.resolve())).copy()
    frame["legal_dong_code"] = frame["legal_dong_code"].astype(str).str.zfill(10)
    frame["sigungu_code"] = frame["sigungu_code"].astype(str).str.zfill(5)
    return frame


def _official_districts() -> pd.DataFrame:
    path = settings.processed_dir / "seoul_district_official_latest.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = _read_csv(str(path.resolve())).copy()
    if "sigungu_code" in frame:
        frame["sigungu_code"] = frame["sigungu_code"].astype(str).str.zfill(5)
    return frame


def _official_evidence() -> pd.DataFrame:
    path = settings.processed_dir / "seoul_official_dong_evidence.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = _read_csv(str(path.resolve())).copy()
    if "legal_dong_code" in frame:
        frame["legal_dong_code"] = frame["legal_dong_code"].where(
            frame["legal_dong_code"].notna(), None
        )
        mask = frame["legal_dong_code"].notna()
        frame.loc[mask, "legal_dong_code"] = frame.loc[mask, "legal_dong_code"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    return frame


def _safety_comparison_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """위험점수를 같은 비교집단에서 읽기 쉬운 안전 참고점수로 뒤집습니다."""
    result = frame.copy()
    result["risk_score"] = pd.to_numeric(result["risk_score"], errors="coerce")
    result = result[result["risk_score"].notna()].copy()
    result["safety_score"] = (100 - result["risk_score"]).clip(0, 100).round(1)
    result["is_comparable"] = result["data_confidence"].isin(["높음", "보통"])
    return result


def _comparison_records(frame: pd.DataFrame) -> list[dict]:
    columns = [
        "legal_dong_code",
        "sigungu_code",
        "district",
        "legal_dong",
        "safety_score",
        "risk_score",
        "risk_level",
        "data_confidence",
        "is_comparable",
        "jeonse_ratio_pct",
        "sale_count",
        "jeonse_count",
        "official_dong_evidence_count",
        "major_reasons",
        "distance_km",
        "is_selected",
        "rank",
    ]
    return _records(frame[[column for column in columns if column in frame.columns]])


def _coordinate_points(value):
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        yield float(value[0]), float(value[1])
        return
    if isinstance(value, list):
        for child in value:
            yield from _coordinate_points(child)


@lru_cache(maxsize=1)
def _legal_dong_centers() -> dict[str, tuple[float, float]]:
    centers: dict[str, tuple[float, float]] = {}
    for feature in _geojson("seoul_legal_dong_risk_web.geojson").get("features", []):
        code = str(feature.get("properties", {}).get("legal_dong_code") or "").zfill(10)
        points = list(_coordinate_points(feature.get("geometry", {}).get("coordinates", [])))
        if code and points:
            centers[code] = (
                sum(point[0] for point in points) / len(points),
                sum(point[1] for point in points) / len(points),
            )
    return centers


def _distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, first)
    lon2, lat2 = map(math.radians, second)
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(value))


def _component_explanation(row: pd.Series) -> dict:
    valid: list[tuple[str, float, float]] = []
    for column, meta in SEOUL_WEIGHTS.items():
        value = row.get(column)
        if pd.notna(value):
            valid.append((column, float(value), float(meta["weight"])))

    used_weight = sum(item[2] for item in valid)
    components = []
    for column, score, base_weight in valid:
        effective_weight = base_weight / used_weight if used_weight else 0
        components.append(
            {
                "key": column,
                "label": SEOUL_WEIGHTS[column]["label"],
                "description": SEOUL_WEIGHTS[column]["description"],
                "score": round(score, 1),
                "base_weight_pct": round(base_weight * 100, 1),
                "effective_weight_pct": round(effective_weight * 100, 1),
                "contribution": round(score * effective_weight, 1),
                "available": True,
            }
        )

    missing = [
        {
            "key": column,
            "label": meta["label"],
            "reason": "해당 법정동의 공개자료 또는 유효 표본 부족",
        }
        for column, meta in SEOUL_WEIGHTS.items()
        if pd.isna(row.get(column))
    ]

    actions: list[dict] = []
    market = row.get("market_risk_score")
    building = row.get("building_risk_score")
    context = row.get("district_context_score")
    ratio = row.get("jeonse_ratio_pct")
    confidence = str(row.get("data_confidence") or "자료 부족")

    if pd.notna(ratio) and float(ratio) >= 80:
        actions.append(
            {
                "priority": "필수",
                "title": "동일 건물·유사 면적의 최근 매매가 재확인",
                "detail": "동 단위 평균이 아니라 계약하려는 건물과 비슷한 면적·층·연식의 최근 실거래를 직접 대조하세요.",
            }
        )
    elif pd.notna(market) and float(market) >= 70:
        actions.append(
            {
                "priority": "필수",
                "title": "보증금과 추정 매매가격의 차이 확인",
                "detail": "고전세가율, 매매가격 하락, 거래량 감소 중 어떤 지표가 높았는지 원자료를 확인하세요.",
            }
        )
    if pd.notna(building) and float(building) >= 70:
        actions.append(
            {
                "priority": "주의",
                "title": "건축물대장과 실제 임대공간 일치 여부 확인",
                "detail": "다가구·다세대 구분, 주용도, 위반건축물 여부, 층·호수와 근린생활시설 혼합 여부를 확인하세요.",
            }
        )
    if pd.notna(context) and float(context) >= 70:
        actions.append(
            {
                "priority": "권장",
                "title": f"{row.get('district', '')} 공식 피해·보증사고 배경 확인",
                "detail": "자치구 공식 수치는 법정동 피해 건수가 아니며, 지역 배경정보로만 해석해야 합니다.",
            }
        )
    if int(row.get("official_dong_evidence_count") or 0) > 0:
        actions.append(
            {
                "priority": "주의",
                "title": "동 단위 공식 확인자료의 정의와 기준일 확인",
                "detail": "신청 접수, 특정 사건, 피해자 가결은 서로 다른 통계이므로 상세 카드의 집계범위와 비교주의를 확인하세요.",
            }
        )
    if confidence in {"낮음", "자료 부족"}:
        actions.append(
            {
                "priority": "주의",
                "title": "지역점수를 확정판정으로 사용하지 않기",
                "detail": "거래·건물 표본이 부족합니다. 등기부, 선순위 보증금, 보증기관 사전심사를 우선하세요.",
            }
        )
    if not actions:
        actions.append(
            {
                "priority": "권장",
                "title": "개별 매물 진단으로 이동",
                "detail": "지역점수가 낮아도 근저당·신탁·압류·선순위 임차보증금은 개별 계약에서 따로 확인해야 합니다.",
            }
        )

    return {
        "score": round(float(row["risk_score"]), 1) if pd.notna(row.get("risk_score")) else None,
        "level": row.get("risk_level", "자료 부족"),
        "confidence": confidence,
        "components": components,
        "missing_components": missing,
        "renormalized": 0 < used_weight < 0.999,
        "used_base_weight_pct": round(used_weight * 100, 1),
        "formula": "가용 지표의 (점수 × 기본가중치) 합 ÷ 가용 기본가중치 합",
        "actions": actions,
        "note": "서울 법정동 간 시장·건물구조 상대위험이며 전세사기 발생확률이 아닙니다.",
    }


@router.get("/map/legal-dong")
def legal_dong_map():
    return _geojson("seoul_legal_dong_risk_web.geojson")


@router.get("/map/sigungu")
def legacy_map_alias():
    """기존 전국 프로젝트 프론트와의 호환용 별칭."""
    return legal_dong_map()


@router.get("/dong-risk")
def dong_risk(
    code: str | None = Query(default=None),
    query: str | None = Query(default=None),
    district: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    frame = _risk_data()
    if code:
        key = str(code).strip()
        frame = frame[frame["legal_dong_code"].str.startswith(key)]
    if district:
        frame = frame[frame["district"].fillna("").astype(str).str.contains(district.strip(), case=False, regex=False)]
    if query:
        key = query.strip()
        mask = frame["district"].fillna("").astype(str).str.contains(key, case=False, regex=False)
        mask |= frame["legal_dong"].fillna("").astype(str).str.contains(key, case=False, regex=False)
        mask |= frame["legal_dong_code"].astype(str).str.contains(key, case=False, regex=False)
        frame = frame[mask]
    frame = frame.sort_values(["data_confidence", "risk_score"], ascending=[True, False])
    return {"items": _records(frame.head(limit))}


@router.get("/district-risk")
def legacy_district_search(
    code: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    return dong_risk(code=code, query=query, district=None, limit=limit)


@router.get("/dong-risk/{legal_dong_code}")
def dong_risk_detail(legal_dong_code: str):
    code = str(legal_dong_code).zfill(10)
    frame = _risk_data()
    matched = frame[frame["legal_dong_code"] == code]
    if matched.empty:
        raise HTTPException(404, "해당 서울 법정동 위험도 자료가 없습니다.")
    row = matched.iloc[0]
    item = _records(matched.head(1))[0]
    item["explanation"] = _component_explanation(row)

    evidence = _official_evidence()
    if not evidence.empty and "legal_dong_code" in evidence:
        evidence_rows = evidence[evidence["legal_dong_code"] == code]
        item["official_dong_evidence"] = _records(evidence_rows)
    else:
        item["official_dong_evidence"] = []
    return item


@router.get("/district-risk/{region_code}")
def legacy_detail_alias(region_code: str):
    if len(str(region_code)) >= 10:
        return dong_risk_detail(region_code)
    frame = _risk_data()
    candidates = frame[frame["sigungu_code"] == str(region_code).zfill(5)]
    if candidates.empty:
        raise HTTPException(404, "해당 지역 자료가 없습니다.")
    # 기존 주소로 들어온 경우 해당 자치구에서 표본 신뢰도가 가장 높은 대표 동으로 연결한다.
    order = {"높음": 0, "보통": 1, "낮음": 2, "자료 부족": 3}
    candidates = candidates.assign(_order=candidates["data_confidence"].map(order).fillna(9))
    representative = candidates.sort_values(["_order", "risk_score"], ascending=[True, False]).iloc[0]
    return dong_risk_detail(str(representative["legal_dong_code"]))


@router.get("/methodology")
def methodology():
    return {
        "model": {
            "name": "서울 법정동 시장·건물구조 상대위험 v1.0",
            "scope": "서울특별시 467개 법정동",
            "components": [
                {"key": key, **meta, "weight_pct": int(meta["weight"] * 100)}
                for key, meta in SEOUL_WEIGHTS.items()
            ],
            "market_detail": {
                "jeonse_ratio": 40,
                "high80_share": 25,
                "sale_decline": 15,
                "sale_activity_decline": 10,
                "non_apartment_lease_share": 10,
            },
            "building_detail": {
                "non_apartment_building_share": 40,
                "old20_share": 25,
                "mixed_use_share": 20,
                "households_per_parking": 15,
            },
            "missing_rule": "결측은 0점 처리하지 않고 가용 지표끼리 기본가중치를 재정규화합니다.",
            "official_rule": "자치구 공식 가결건수를 법정동에 나누지 않으며, 동 단위 공식자료는 집계범위가 확인된 경우에만 별도 카드로 표시합니다.",
            "limits": [
                "전세사기 발생확률 또는 피해율이 아닙니다.",
                "등기부의 근저당·압류·신탁과 선순위 보증금은 자동 반영되지 않습니다.",
                "서울_~1·~2·~4 업로드 자료는 원본 기준일 확인 전까지 보조·참고자료로 취급합니다.",
            ],
        },
        "property_model": {
            "name": "계약 안전 행동판정 v2.0",
            "components": [
                {"label": "가격", "weight_pct": 32},
                {"label": "권리", "weight_pct": 38},
                {"label": "건물", "weight_pct": 15},
                {"label": "확인상태", "weight_pct": 10},
                {"label": "지역 참고", "weight_pct": 5},
            ],
            "decision_order": ["치명적 중단 조건", "핵심자료 미확인", "주의 조건", "참고 위험부담 지수"],
            "purpose": "낮은 평균점수로 치명적 위험이 상쇄되지 않도록 계약 중단·보류 행동을 우선 판정",
        },
    }


@router.get("/compare/neighbors/{legal_dong_code}")
def compare_neighboring_legal_dongs(
    legal_dong_code: str,
    limit: int = Query(default=8, ge=4, le=12),
):
    code = str(legal_dong_code).zfill(10)
    centers = _legal_dong_centers()
    if code not in centers:
        raise HTTPException(404, "선택한 법정동의 지도 중심점을 찾을 수 없습니다.")

    source = _safety_comparison_frame(_risk_data())
    selected = source[source["legal_dong_code"] == code]
    if selected.empty:
        raise HTTPException(404, "선택한 법정동의 비교자료가 없습니다.")

    selected_center = centers[code]
    distances = []
    for candidate_code in source["legal_dong_code"].astype(str):
        if candidate_code == code or candidate_code not in centers:
            continue
        distances.append((candidate_code, _distance_km(selected_center, centers[candidate_code])))
    nearest = sorted(distances, key=lambda item: item[1])[:limit]
    nearest_codes = [item[0] for item in nearest]
    distance_by_code = {item[0]: item[1] for item in nearest}
    distance_by_code[code] = 0.0

    comparison = source[source["legal_dong_code"].isin([code, *nearest_codes])].copy()
    comparison["distance_km"] = comparison["legal_dong_code"].map(distance_by_code).round(2)
    comparison["is_selected"] = comparison["legal_dong_code"].eq(code)
    comparison = comparison.sort_values(["safety_score", "legal_dong"], ascending=[False, True]).reset_index(drop=True)
    comparison["rank"] = comparison.index + 1
    selected_rank = int(comparison.loc[comparison["is_selected"], "rank"].iloc[0])
    selected_row = selected.iloc[0]
    return {
        "selected": {
            "legal_dong_code": code,
            "district": str(selected_row["district"]),
            "legal_dong": str(selected_row["legal_dong"]),
            "safety_score": round(float(selected_row["safety_score"]), 1),
            "risk_level": str(selected_row["risk_level"]),
            "data_confidence": str(selected_row["data_confidence"]),
            "rank_in_comparison": selected_rank,
            "comparison_count": int(len(comparison)),
        },
        "items": _comparison_records(comparison),
        "distance_basis": "법정동 경계 좌표의 중심점 간 직선거리 기준",
        "note": "주변 비교는 가까운 법정동과의 상대 비교이며 전세사기 발생확률이나 개별 매물의 안전을 뜻하지 않습니다.",
    }


@router.get("/summary")
def summary():
    frame = _risk_data()
    summary_path = settings.processed_dir / "seoul_project_summary.json"
    project_summary = _read_json(str(summary_path.resolve())) if summary_path.exists() else {}
    official_total = int(_official_districts()["official_total"].sum()) if not _official_districts().empty else None
    return {
        "legal_dongs": int(len(frame)),
        "scored_dongs": int(frame["risk_score"].notna().sum()),
        "high_or_higher": int(frame["risk_level"].isin(["높음", "매우 높음"]).sum()),
        "high_confidence": int(frame["data_confidence"].eq("높음").sum()),
        "medium_or_higher_confidence": int(frame["data_confidence"].isin(["높음", "보통"]).sum()),
        "median_jeonse_ratio": round(float(frame["jeonse_ratio_pct"].median()), 1),
        "official_district_total_2023_2025": official_total,
        "official_dong_evidence_dongs": int((frame["official_dong_evidence_count"] > 0).sum()),
        "transaction_summary": project_summary.get("transactions", {}),
        "building_summary": project_summary.get("buildings", {}),
        "score_version": frame["score_version"].dropna().iloc[0] if frame["score_version"].notna().any() else "unknown",
        "disclaimer": "공공데이터 기반 서울 법정동 상대 위험지표이며 특정 매물의 안전을 보증하지 않습니다.",
    }


@router.get("/official/districts")
def official_district_list():
    frame = _official_districts()
    return {"items": _records(frame.sort_values("official_total", ascending=False)) if not frame.empty else []}


@router.get("/official/dong-evidence")
def official_dong_evidence(
    legal_dong_code: str | None = Query(default=None),
    district: str | None = Query(default=None),
):
    frame = _official_evidence()
    if frame.empty:
        return {"items": []}
    if legal_dong_code:
        frame = frame[frame["legal_dong_code"] == str(legal_dong_code).zfill(10)]
    if district:
        frame = frame[frame["자치구"].astype(str).eq(district)]
    return {"items": _records(frame)}


@router.post("/property-risk")
def property_risk(payload: dict):
    return calculate_property_risk(payload)


@router.get("/guarantees")
def guarantee_products():
    from app.services.support import guarantees

    return {"items": guarantees()}


@router.get("/support-regions")
def support_regions():
    from app.services.support import regions

    return {"items": regions()}


@router.get("/support-programs")
def support_program_list(region_code: str | None = Query(default=None), include_national: bool = True):
    from app.services.support import programs

    return {"items": programs(region_code, include_national=include_national)}


@router.post("/support-programs/match")
def support_program_match(payload: dict):
    from app.services.support import match_programs

    return match_programs(payload)
