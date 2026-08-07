const SL = window.SafeLease;
const code = window.SAFELEASE_REGION_CODE;

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

// 안전 참고점수 구간별 색. 최종점수 구성과 같은 저채도 초록·노랑·빨강을 쓰고,
// 안전(초록) → 주의(황토) → 위험(벽돌) 순서를 유지한다.
function neighborBarColor(score, selected) {
  if (selected) return '#123337';
  if (score >= 70) return '#2E7D68';
  if (score >= 55) return '#6FA894';
  if (score >= 40) return '#C99A46';
  return '#B85F57';
}

function renderNeighborComparison(data) {
  const selected = data.selected;
  document.getElementById('region-neighbor-summary').innerHTML = `
    <strong>안전 ${SL.fmt(selected.safety_score)}점</strong>
    <span>주변 ${selected.comparison_count - 1}개 동과 비교해 ${selected.rank_in_comparison}번째</span>
  `;
  document.getElementById('region-neighbor-chart').innerHTML = data.items.map((item) => {
    const safety = Math.max(0, Math.min(100, Number(item.safety_score) || 0));
    const selectedItem = Boolean(item.is_selected);
    const selectedBadge = selectedItem ? '<em>선택</em>' : '';
    const distance = selectedItem ? '선택 지역' : `${SL.fmt(item.distance_km, 2)}km`;
    return `
      <a class="neighbor-vertical-item${selectedItem ? ' selected' : ''}${item.is_comparable ? '' : ' low-confidence'}"
         href="/region/${String(item.legal_dong_code).padStart(10, '0')}"
         aria-label="${escapeHtml(item.district)} ${escapeHtml(item.legal_dong)}, 안전 참고점수 ${SL.fmt(safety)}점, ${escapeHtml(SL.riskLevelLabel(item.risk_level))}, 자료 신뢰도 ${escapeHtml(SL.value(item.data_confidence))}">
        <span class="neighbor-bar-value">${SL.fmt(safety)}</span>
        <span class="neighbor-bar-track" aria-hidden="true"><i style="height:${safety}%;background:${neighborBarColor(safety, selectedItem)}"></i></span>
        <span class="neighbor-bar-label"><strong>${escapeHtml(item.legal_dong)} ${selectedBadge}</strong><small>${escapeHtml(item.district)} · ${escapeHtml(distance)}</small><small>${escapeHtml(SL.riskLevelLabel(item.risk_level))} · 신뢰도 ${escapeHtml(SL.value(item.data_confidence))}</small></span>
      </a>
    `;
  }).join('');
  document.getElementById('region-neighbor-note').textContent = `${data.distance_basis}. ${data.note}`;
}

fetch(`/api/compare/neighbors/${encodeURIComponent(code)}?limit=8`, { cache: 'no-store' })
  .then((response) => {
    if (!response.ok) throw new Error('주변 법정동 비교자료를 불러오지 못했습니다.');
    return response.json();
  })
  .then(renderNeighborComparison)
  .catch((error) => {
    document.getElementById('region-neighbor-chart').innerHTML = `<p class="chart-error">${escapeHtml(error.message)}</p>`;
    document.getElementById('region-neighbor-summary').textContent = '비교자료 없음';
  });

function rawItem(label, value, suffix = '') {
  return `<div><dt>${label}</dt><dd>${value}${value === '-' ? '' : suffix}</dd></div>`;
}

function money(value) {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return '-';
  return `${Number(value).toLocaleString('ko-KR')}원`;
}

function evidenceCard(item) {
  const value = Number.isFinite(Number(item['수치'])) ? SL.fmt(item['수치'], 0) : SL.value(item['수치']);
  const link = item['원문_URL'] ? `<a class="text-link" href="${item['원문_URL']}" target="_blank" rel="noopener noreferrer">공식 원문 보기 ↗</a>` : '';
  return `
    <article class="evidence-item">
      <div class="evidence-head"><span class="source-chip">${SL.value(item['자료등급'])}</span><strong>${SL.value(item['지표명'])}</strong></div>
      <div class="evidence-value">${value}<small>${SL.value(item['단위'], '')}</small></div>
      <dl class="evidence-meta">
        <div><dt>기준일</dt><dd>${SL.value(item['기준일'])}</dd></div>
        <div><dt>집계범위</dt><dd>${SL.value(item['집계범위'])}</dd></div>
        <div><dt>공식기관</dt><dd>${SL.value(item['공식기관'])}</dd></div>
      </dl>
      <p class="warning-text">${SL.value(item['비교주의'])}</p>
      ${link}
    </article>
  `;
}

fetch(`/api/dong-risk/${encodeURIComponent(code)}`)
  .then((response) => {
    if (!response.ok) throw new Error('서울 법정동 상세자료를 찾지 못했습니다.');
    return response.json();
  })
  .then((data) => {
    const explanation = data.explanation;
    document.getElementById('region-name').textContent = `서울특별시 ${SL.value(data.district)} ${SL.value(data.legal_dong)}`;
    document.getElementById('region-subtitle').textContent = `${SL.value(data.score_scope)} · ${explanation.note}`;
    document.getElementById('region-score').textContent = SL.fmt(data.risk_score);
    document.getElementById('region-level').textContent = SL.riskLevelLabel(data.risk_level);
    document.getElementById('region-confidence').textContent = SL.value(data.data_confidence);
    document.getElementById('region-ratio').textContent = data.jeonse_ratio_pct == null ? '-' : `${SL.fmt(data.jeonse_ratio_pct)}%`;
    document.getElementById('region-groups').textContent = SL.fmt(data.matched_group_count, 0);

    document.getElementById('official-district-title').textContent = `${SL.value(data.district)} 공식 피해·보증사고 배경`;
    document.getElementById('official-district-data').innerHTML = `
      <div><span>2023년 가결</span><strong>${SL.fmt(data.official_2023, 0)}건</strong></div>
      <div><span>2024년 가결</span><strong>${SL.fmt(data.official_2024, 0)}건</strong></div>
      <div><span>2025년 가결</span><strong>${SL.fmt(data.official_2025, 0)}건</strong></div>
      <div><span>3개년 합계</span><strong>${SL.fmt(data.official_total, 0)}건</strong></div>
      <div><span>1,000세대당</span><strong>${SL.fmt(data.official_per_1000_households, 3)}건</strong></div>
      <div><span>보증사고율*</span><strong>${SL.fmt(data.guarantee_accident_rate_pct)}%</strong></div>
    `;

    const evidence = data.official_dong_evidence || [];
    document.getElementById('official-dong-evidence').innerHTML = evidence.length
      ? evidence.map(evidenceCard).join('')
      : '<div class="evidence-empty"><strong>공개된 동 단위 공식 집계 없음</strong><p>피해 0건이라는 뜻이 아닙니다. 이 법정동은 거래·건물구조 신호만 계산하고 자치구 공식자료는 배경으로 분리합니다.</p></div>';

    // 기여도가 큰 순으로 정렬하고, 순위에 따라 짙은 톤 → 옅은 톤으로 색을 준다.
    // 초록·노랑·빨강. 채도를 낮춰 사이트의 차분한 톤에 맞춘다.
    // fill=면, on=면 위 글자색, ink=흰 배경 위 글자색.
    const ramp = [
      { fill: '#2E7D68', on: '#ffffff', ink: '#24634F' },
      { fill: '#C99A46', on: '#3A2A08', ink: '#856320' },
      { fill: '#B85F57', on: '#ffffff', ink: '#94473F' },
      { fill: '#7C9B92', on: '#ffffff', ink: '#4E6D63' },
    ];
    const parts = explanation.components
      .map((item) => ({
        label: item.label,
        score: Math.max(0, Number(item.score) || 0),
        contribution: Math.max(0, Number(item.contribution) || 0),
        baseWeight: Number(item.base_weight_pct) || 0,
        effWeight: Number(item.effective_weight_pct) || 0,
        description: item.description,
      }))
      .sort((a, b) => b.contribution - a.contribution)
      .map((item, index) => ({ ...item, ...ramp[index % ramp.length] }));

    const total = parts.reduce((sum, item) => sum + item.contribution, 0);
    const share = (value) => (total > 0 ? value / total * 100 : 0);
    const top = parts[0];

    const RADIUS = 52;
    const CIRC = 2 * Math.PI * RADIUS;
    let walked = 0;
    const arcs = parts.map((item) => {
      const length = share(item.contribution) / 100 * CIRC;
      const arc = `<circle cx="68" cy="68" r="${RADIUS}" fill="none" stroke="${item.fill}" stroke-width="17"
        stroke-dasharray="${length.toFixed(2)} ${(CIRC - length).toFixed(2)}" stroke-dashoffset="${(-walked).toFixed(2)}"
        transform="rotate(-90 68 68)"></circle>`;
      walked += length;
      return arc;
    }).join('');

    const glance = `
      <div class="score-glance">
        <figure class="glance-donut" role="img" aria-label="최종 참고점수 ${SL.fmt(data.risk_score)}점을 구성하는 요소별 기여도 도넛 차트">
          <svg viewBox="0 0 136 136" aria-hidden="true">
            <circle cx="68" cy="68" r="${RADIUS}" fill="none" stroke="#edf2f0" stroke-width="17"></circle>
            ${arcs}
          </svg>
          <figcaption>
            <strong>${SL.fmt(data.risk_score)}</strong>
            <span>최종 참고점수</span>
          </figcaption>
        </figure>
        <div class="glance-body">
          <p class="glance-headline">${top ? `점수를 가장 많이 올린 것은 <b>${escapeHtml(top.label)}</b> — 전체의 <b>${SL.fmt(share(top.contribution), 0)}%</b>` : '구성요소 자료가 없습니다.'}</p>
          <ul class="glance-legend">
            ${parts.map((item, index) => `
              <li>
                <em style="background:${item.fill}"></em>
                <b>${escapeHtml(item.label)}</b>
                <span class="legend-share">${SL.fmt(share(item.contribution), 0)}<small>%</small></span>
                <span class="legend-point">${SL.fmt(item.contribution)}점</span>
              </li>`).join('')}
          </ul>
          <p class="glance-foot">100에 가까울수록 서울 안에서 상대위험이 큽니다. 전세사기 발생확률이 아닙니다.</p>
        </div>
      </div>`;

    const components = `<p class="component-detail-title">요소별 자세히 보기</p><div class="component-detail-list">${parts.map((item, index) => `
      <article class="comp-card" style="--comp:${item.fill};--comp-on:${item.on};--comp-ink:${item.ink}">
        <div class="comp-top">
          <span class="comp-rank">${index + 1}</span>
          <strong>${escapeHtml(item.label)}</strong>
          <span class="comp-weight">가중치 ${SL.fmt(item.effWeight, 0)}%</span>
          <span class="comp-score">${SL.fmt(item.score)}<small>/100</small></span>
        </div>
        <div class="comp-track"><i style="width:${Math.min(100, item.score)}%"></i></div>
        <div class="comp-bottom">
          <p>${escapeHtml(item.description)}</p>
          <span class="comp-contrib">최종점수에 <b>+${SL.fmt(item.contribution)}</b></span>
        </div>
      </article>`).join('')}</div>`;

    const missing = explanation.missing_components.length
      ? `<div class="missing-components"><strong>빠진 지표</strong><ul>${explanation.missing_components.map((item) => `<li>${item.label}: ${item.reason}</li>`).join('')}</ul></div>`
      : '';
    document.getElementById('region-components').innerHTML = glance + components + missing;
    document.getElementById('renormalize-note').innerHTML = explanation.renormalized
      ? `<strong>가중치 재조정 적용</strong><p>기본가중치 ${SL.fmt(explanation.used_base_weight_pct)}%에 해당하는 지표만 존재해, 가용 지표끼리 100%로 다시 나누었습니다.</p><code>${explanation.formula}</code>`
      : `<strong>세 구성요소 모두 사용</strong><p>시장 60%, 건물구조 25%, 자치구 공식 배경 15%가 반영되었습니다.</p>`;

    document.getElementById('region-actions').innerHTML = explanation.actions.map((action, index) => `
      <article class="action-item">
        <span class="action-order">${index + 1}</span>
        <div><span class="priority ${SL.priorityClass(action.priority)}">${action.priority}</span><strong>${action.title}</strong><p>${action.detail}</p></div>
      </article>
    `).join('');

    document.getElementById('region-raw').innerHTML = [
      rawItem('매매 거래', SL.fmt(data.sale_count, 0), '건'),
      rawItem('순수전세 거래', SL.fmt(data.jeonse_count, 0), '건'),
      rawItem('최근 36개월 매칭', SL.fmt(data.matched_group_count, 0), '개'),
      rawItem('80% 이상 매칭 비중', SL.fmt(data.high80_share_pct), '%'),
      rawItem('90% 이상 매칭 비중', SL.fmt(data.high90_share_pct), '%'),
      rawItem('매매가격 하락 신호', SL.fmt(data.sale_decline_pct), '%'),
      rawItem('매매활동 감소 신호', SL.fmt(data.sale_activity_decline_pct), '%'),
      rawItem('비아파트 전세 비중', SL.fmt(data.non_apartment_lease_share_pct), '%'),
      rawItem('건축물 표본', SL.fmt(data.building_count, 0), '동'),
      rawItem('건축물 자료계층', SL.value(data.building_source_tier)),
      rawItem('비아파트 건물 비중', SL.fmt(data.nonapt_building_share_pct), '%'),
      rawItem('20년 이상 주거건물', SL.fmt(data.old20_share_pct), '%'),
      rawItem('층별 혼합용도 건물', SL.fmt(data.mixed_use_building_share_pct), '%'),
      rawItem('개별주택가격 표본', SL.fmt(data.individual_house_price_count, 0), '건'),
      rawItem('개별주택가격 중앙값', money(data.individual_house_price_median)),
      rawItem('최근 매매 기준월', SL.value(data.latest_sale_date)),
      rawItem('최근 전세 기준월', SL.value(data.latest_jeonse_date)),
      rawItem('분석 주요 사유', SL.value(data.major_reasons)),
    ].join('');

    const rawSummary = document.getElementById('region-raw-summary');
    if (rawSummary) {
      rawSummary.innerHTML = [
        ['매매', `${SL.fmt(data.sale_count, 0)}건`],
        ['순수전세', `${SL.fmt(data.jeonse_count, 0)}건`],
        ['건축물', `${SL.fmt(data.building_count, 0)}동`],
        ['기준월', SL.value(data.latest_sale_date)],
      ].map(([key, value]) => `<span><i>${key}</i>${escapeHtml(value)}</span>`).join('');
    }

    document.getElementById('region-content').classList.remove('hidden');
  })
  .catch((error) => {
    const box = document.getElementById('region-error');
    box.classList.remove('hidden');
    box.innerHTML = `<strong>불러오기 오류</strong><p>${error.message}</p>`;
  });
