from __future__ import annotations

from typing import Any


OFFICIAL_URLS = {
    "transactions": "https://rt.molit.go.kr/pt/gis/gis.do",
    "building": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000098&tp_seq=03",
    "registry": "https://www.iros.go.kr/",
    "guarantee": "https://www.khug.or.kr/jeonse/index.jsp",
    "broker": "http://www.nsdi.go.kr/lxportal/?menuno=2679",
}


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _interp(value: float, points: list[tuple[float, float]]) -> float:
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 <= value <= x2:
            ratio = (value - x1) / (x2 - x1)
            return y1 + (y2 - y1) * ratio
    return points[-1][1]


def _bool_or_none(value: Any) -> bool | None:
    if value in (True, "true", "True", 1, "1", "yes"):
        return True
    if value in (False, "false", "False", 0, "0", "no"):
        return False
    return None


def _number(value: Any, default: float = 0) -> float:
    try:
        number = float(value)
        return number if number == number and number not in (float("inf"), float("-inf")) else default
    except (TypeError, ValueError):
        return default


def _action(priority: str, title: str, detail: str, category: str, when: str = "계약 전", where: str = "") -> dict:
    """when: 이 행동을 실제로 해야 하는 시점. 사용자가 순서를 바로 알아볼 수 있게 한다."""
    return {
        "priority": priority,
        "title": title,
        "detail": detail,
        "category": category,
        "when": when,
        "where": where,
    }


def _document(key: str, title: str, status: str, purpose: str, url: str) -> dict:
    return {"key": key, "title": title, "status": status, "purpose": purpose, "url": url}


def calculate_property_risk(payload: dict) -> dict:
    """계약의 치명적 조건과 미확인을 먼저 판정하고 점수는 보조로 제공한다."""
    deposit = max(0, _number(payload.get("deposit")))
    estimated_sale_price = max(0, _number(payload.get("estimated_sale_price")))
    district_score = _clamp(_number(payload.get("district_score"), 50))
    building_age = max(0, _number(payload.get("building_age")))
    mortgage = max(0, _number(payload.get("mortgage")))
    senior_deposit = max(0, _number(payload.get("senior_deposit")))

    guarantee_available = _bool_or_none(payload.get("guarantee_available"))
    violation_building = _bool_or_none(payload.get("violation_building"))
    trust_registration = _bool_or_none(payload.get("trust_registration"))
    owner_match = _bool_or_none(payload.get("owner_match"))
    tax_checked = _bool_or_none(payload.get("tax_checked"))
    broker_verified = _bool_or_none(payload.get("broker_verified"))
    registry_checked = _bool_or_none(payload.get("registry_checked"))
    mortgage_confirmed = _bool_or_none(payload.get("mortgage_confirmed"))
    senior_deposit_confirmed = _bool_or_none(payload.get("senior_deposit_confirmed"))

    jeonse_ratio = deposit / estimated_sale_price * 100 if estimated_sale_price > 0 else None
    rights_ratio = (
        (deposit + mortgage + senior_deposit) / estimated_sale_price * 100
        if estimated_sale_price > 0
        else None
    )

    price_risk = 55.0 if jeonse_ratio is None else _interp(
        jeonse_ratio,
        [(0, 0), (50, 8), (60, 22), (70, 45), (80, 72), (90, 92), (100, 100)],
    )
    rights_risk = 60.0 if rights_ratio is None else _interp(
        rights_ratio,
        [(0, 0), (40, 8), (60, 28), (70, 48), (80, 72), (90, 92), (100, 100)],
    )
    building_risk = _interp(
        building_age,
        [(0, 5), (10, 15), (20, 35), (30, 60), (40, 82), (50, 100)],
    )
    if violation_building is True:
        building_risk = 100
    elif violation_building is None:
        building_risk = _clamp(building_risk + 12)

    verification_values = [
        guarantee_available,
        violation_building,
        trust_registration,
        owner_match,
        tax_checked,
        broker_verified,
        registry_checked,
        mortgage_confirmed,
        senior_deposit_confirmed,
    ]
    unknown_count = sum(value is None for value in verification_values)
    verification_risk = _clamp(unknown_count * 8)
    if guarantee_available is False:
        verification_risk += 25
    if owner_match is False or trust_registration is True:
        verification_risk += 25
    verification_risk = _clamp(verification_risk)

    # 지역점수는 참고 맥락일 뿐 계약 판정을 압도하지 않도록 5%만 반영한다.
    weights = {"price": 0.32, "rights": 0.38, "building": 0.15, "verification": 0.10, "district": 0.05}
    component_scores = {
        "price": round(price_risk, 1),
        "rights": round(rights_risk, 1),
        "building": round(building_risk, 1),
        "verification": round(verification_risk, 1),
        "district": round(district_score, 1),
    }
    contributions = {key: round(component_scores[key] * weights[key], 1) for key in weights}
    score = round(_clamp(sum(contributions.values())), 1)

    hard_stops: list[dict] = []
    critical_unknowns: list[str] = []
    cautions: list[str] = []
    actions: list[dict] = []

    if deposit <= 0:
        critical_unknowns.append("전세보증금")
    if estimated_sale_price <= 0:
        critical_unknowns.append("최근 실거래에 근거한 추정 매매가")
    if registry_checked is not True:
        critical_unknowns.append("계약 직전 발급한 등기사항증명서")
    if mortgage_confirmed is not True:
        critical_unknowns.append("등기부 을구의 채권최고액")
    if senior_deposit_confirmed is not True:
        critical_unknowns.append("선순위 임차보증금 총액")
    if guarantee_available is None:
        critical_unknowns.append("HUG 등 반환보증 가입 가능 여부")
    if violation_building is None:
        critical_unknowns.append("건축물대장 위반건축물 표시")
    if trust_registration is None:
        critical_unknowns.append("등기부 신탁등기 여부")
    if owner_match is None:
        critical_unknowns.append("등기상 소유자와 계약 상대방 일치 여부")
    if tax_checked is not True:
        critical_unknowns.append("임대인 국세·지방세 체납 관련 확인")
    if broker_verified is not True:
        critical_unknowns.append("중개사무소 정상 영업·등록 여부")

    if trust_registration is True:
        hard_stops.append({
            "title": "신탁등기가 확인됨",
            "detail": "신탁원부와 수탁자의 임대 권한·동의가 확인되기 전에는 계약금이나 보증금을 지급하지 마세요.",
        })
    if owner_match is False:
        hard_stops.append({
            "title": "소유자와 계약 상대방이 다름",
            "detail": "적법한 대리권, 위임장·인감증명서와 소유자 본인 확인이 끝날 때까지 계약을 멈추세요.",
        })
    if violation_building is True:
        hard_stops.append({
            "title": "위반건축물 표시가 있음",
            "detail": "대출·보증 제한 가능성이 있으므로 위반 해소와 보증기관 사전심사 결과가 없으면 진행하지 마세요.",
        })
    if guarantee_available is False:
        hard_stops.append({
            "title": "반환보증 가입 불가로 확인됨",
            "detail": "불가 사유를 해소하거나 보증금·매물을 변경하기 전에는 계약을 중단하는 편이 안전합니다.",
        })
    if rights_ratio is not None and rights_ratio >= 90:
        hard_stops.append({
            "title": "보증금과 선순위 권리 합계가 추정가에 근접",
            "detail": f"보증금·채권최고액·선순위 보증금 합계가 추정가의 {rights_ratio:.1f}%입니다. 권리 축소와 가격 재검증이 필요합니다.",
        })

    if jeonse_ratio is not None and jeonse_ratio >= 80:
        cautions.append(f"전세가율이 {jeonse_ratio:.1f}%로 높아 가격 하락 시 회수 여력이 작습니다.")
    elif jeonse_ratio is not None and jeonse_ratio >= 70:
        cautions.append(f"전세가율이 {jeonse_ratio:.1f}%로 주의가 필요한 구간입니다.")
    if rights_ratio is not None and 75 <= rights_ratio < 90:
        cautions.append(f"권리부담 합계 비율이 {rights_ratio:.1f}%로 높습니다.")
    if building_age >= 25:
        cautions.append(f"사용승인 후 약 {building_age:.0f}년이 지난 건물입니다. 노후도보다 불법 증축과 실제 용도 일치를 확인하세요.")
    if district_score >= 70:
        cautions.append("지역 상대점수가 높습니다. 이는 해당 계약의 사기 확률이 아니므로 시세·등기·보증 결과로 최종 판단하세요.")

    if hard_stops:
        decision = "STOP"
        decision_label = "계약 중단·대안 검토"
        decision_summary = "평균점수로 상쇄할 수 없는 치명적 조건이 발견됐습니다. 해소 증빙 전에는 돈을 보내지 마세요."
    elif critical_unknowns:
        decision = "HOLD"
        decision_label = "서류 확인 전 계약 보류"
        decision_summary = "안전하다고 판단할 핵심 자료가 부족합니다. 아래 확인을 끝낸 뒤 다시 판정하세요."
    elif cautions:
        decision = "REVIEW"
        decision_label = "조건 조정 후 재검토"
        decision_summary = "즉시 중단 신호는 없지만 가격·권리 조건을 조정하고 특약과 보증 결과를 확인해야 합니다."
    else:
        decision = "CONDITIONAL"
        decision_label = "조건부 진행 가능"
        decision_summary = "현재 입력에서 치명적 신호는 적습니다. 잔금 직전 재확인과 보증 가입까지 완료해야 합니다."

    if hard_stops:
        actions.append(_action("계약 중단", "돈을 보내지 말고 치명적 조건부터 해소", "중개인의 구두 설명이 아니라 발급 서류와 기관 확인 결과로 해소 여부를 증명하세요.", "중단", "지금 당장", "임대인·중개사에게 서면 요구"))
    if critical_unknowns:
        actions.append(_action("필수", f"미확인 {len(set(critical_unknowns))}개 자료부터 채우기", "모르는 값을 0원이나 '없음'으로 입력하지 말고 실제 서류를 확인한 뒤 다시 진단하세요.", "검증", "지금 당장", "인터넷등기소·정부24"))
    if jeonse_ratio is None or (jeonse_ratio is not None and jeonse_ratio >= 70):
        actions.append(_action("필수", "같은 건물·유사면적 실거래 대조", "국토교통부 실거래가에서 최근 매매 2건 이상과 전세 거래를 확인하세요.", "가격", "계약 전", "국토부 실거래가"))
    if rights_ratio is None or (rights_ratio is not None and rights_ratio >= 75):
        actions.append(_action("필수", "선순위 권리 축소·재확인", "근저당 말소·감액은 특약과 잔금 지급 순서에 명확히 적고 당일 등기부를 다시 확인하세요.", "권리", "계약 전", "등기부 을구 + 특약"))
    actions.append(_action("필수", "반환보증 사전심사와 가입", "계약 전 가입 가능 여부를 확인하고 계약 후 기한 안에 실제 가입 완료까지 추적하세요.", "보증", "계약 전 → 입주 후", "HUG·HF·SGI"))
    actions.append(_action("잔금일", "잔금 송금 직전 등기부 재열람", "등기 변동, 소유자, 근저당 말소 처리와 입금 계좌 명의를 확인한 뒤 송금하세요.", "잔금", "잔금일 당일", "인터넷등기소"))
    actions.append(_action("필수", "입주 당일 인도·전입신고·확정일자", "이사와 전입신고를 미루지 마세요. 대항력·우선변제권이 늦어지면 그 사이 설정된 근저당이 앞섭니다.", "대항력", "입주 당일", "정부24·주민센터"))

    documents = [
        _document("price", "국토부 실거래가", "확인 필요" if estimated_sale_price <= 0 else "입력 완료", "최근 동일 건물·유사면적 매매가와 전세가 대조", OFFICIAL_URLS["transactions"]),
        _document("building", "건축물대장", "확인 완료" if violation_building is not None else "확인 필요", "위반건축물, 주용도, 동·호수와 실제 현황 확인", OFFICIAL_URLS["building"]),
        _document("registry", "등기사항증명서", "확인 완료" if registry_checked is True else "확인 필요", "소유자, 압류·가압류, 신탁, 채권최고액 확인", OFFICIAL_URLS["registry"]),
        _document("broker", "공인중개사 등록", "확인 완료" if broker_verified is True else "확인 필요", "국가공간정보포털에서 등록번호·상호·소재지 대조, 중개보조원 여부 확인", OFFICIAL_URLS["broker"]),
        _document("guarantee", "반환보증 사전심사", "가능" if guarantee_available is True else "불가" if guarantee_available is False else "확인 필요", "가입 가능 여부와 한도·제외 사유를 기관에서 확인", OFFICIAL_URLS["guarantee"]),
    ]

    clauses = [
        "임대인은 잔금 지급 다음 날까지 목적물에 근저당권·전세권 등 새로운 권리를 설정하거나 소유권을 이전하지 않는다.",
        "임대인은 임차인의 전세보증금반환보증 가입 및 국세·지방세 체납 관련 확인에 필요한 서류 제출과 절차에 협조한다.",
        "계약 체결 후 잔금 지급 전 등기사항 또는 건축물대장에서 계약 당시 고지하지 않은 중대한 권리·위반사항이 확인되면 임차인은 계약을 해제하고 지급금을 반환받을 수 있다.",
    ]
    if mortgage > 0:
        clauses.append(f"잔금 지급과 동시에 채권최고액 {mortgage:,.0f}원에 관한 근저당 말소(또는 합의한 금액으로 감액)를 이행하고 말소 접수증을 임차인에게 제공한다.")
    if guarantee_available is not True:
        clauses.append("임차인의 귀책사유 없이 반환보증 가입이 거절되는 경우 임차인은 계약을 해제할 수 있고 임대인은 지급받은 계약금·보증금을 반환한다.")
    if trust_registration is True:
        clauses.append("신탁원부상 수탁자의 임대차계약 체결 권한과 필요한 동의가 서면으로 확인되지 않으면 본 계약은 효력이 발생하지 않는다.")

    confidence = "높음" if unknown_count == 0 and estimated_sale_price > 0 else "보통" if unknown_count <= 3 and estimated_sale_price > 0 else "낮음"
    return {
        "decision": decision,
        "decision_label": decision_label,
        "decision_summary": decision_summary,
        "hard_stops": hard_stops,
        "critical_unknowns": sorted(set(critical_unknowns)),
        "cautions": cautions,
        "reference_score": score,
        "risk_score": score,
        "risk_level": "참고 지수",
        "analysis_confidence": confidence,
        "jeonse_ratio": round(jeonse_ratio, 1) if jeonse_ratio is not None else None,
        "rights_ratio": round(rights_ratio, 1) if rights_ratio is not None else None,
        "weights": weights,
        "component_scores": component_scores,
        "contributions": contributions,
        "major_reasons": [item["title"] for item in hard_stops] + cautions,
        "action_plan": actions,
        "missing_checks": sorted(set(critical_unknowns)),
        "documents": documents,
        "special_clauses": clauses,
        "calculation_note": "참고 위험부담 지수는 가격 32%·권리 38%·건물 15%·확인상태 10%·지역 5%입니다. 계약 판정은 치명적 조건과 미확인을 이 점수보다 먼저 적용합니다.",
        "disclaimer": "이 결과는 법률·감정평가·보증 심사를 대신하지 않으며 계약 안전을 보증하지 않습니다. 실제 발급 서류와 기관 심사 결과를 우선하세요.",
    }
