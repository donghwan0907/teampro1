const SL = window.SafeLease;
const form = document.getElementById('analysis-form');
const summaryPanel = document.getElementById('result-summary');
const stopPanel = document.getElementById('stop-panel');
const documentPanel = document.getElementById('document-panel');
const actionPanel = document.getElementById('action-panel');
const clausePanel = document.getElementById('clause-panel');

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

document.querySelectorAll('.form-section-head').forEach((button) => {
  button.addEventListener('click', () => button.closest('.form-section').classList.toggle('open'));
});

function decisionClass(decision) {
  return { STOP: 'decision-stop', HOLD: 'decision-hold', REVIEW: 'decision-review', CONDITIONAL: 'decision-go' }[decision] || 'decision-hold';
}

function renderSummary(result) {
  summaryPanel.className = `panel decision-result ${decisionClass(result.decision)}`;
  summaryPanel.innerHTML = `
    <div class="decision-label"><span>${escapeHtml(SL.decisionLabel(result.decision))}</span><small>계약 행동 판정</small></div>
    <h2>${escapeHtml(result.decision_label)}</h2>
    <p>${escapeHtml(result.decision_summary)}</p>
    <div class="decision-metrics">
      <div><span>전세가율</span><strong>${result.jeonse_ratio == null ? '확인 필요' : `${SL.fmt(result.jeonse_ratio)}%`}</strong></div>
      <div><span>권리부담 합계</span><strong>${result.rights_ratio == null ? '확인 필요' : `${SL.fmt(result.rights_ratio)}%`}</strong></div>
      <div><span>자료 신뢰도</span><strong>${escapeHtml(result.analysis_confidence)}</strong></div>
    </div>
    <p class="reference-index">참고 위험부담 지수 <b>${SL.fmt(result.reference_score)}</b>/100 · 사기 확률이 아닙니다.</p>`;
}

function renderStops(result) {
  stopPanel.classList.remove('hidden');
  const stops = result.hard_stops.length
    ? result.hard_stops.map((item) => `<article class="stop-item"><i>!</i><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></div></article>`).join('')
    : '<div class="all-clear"><i>✓</i><div><strong>입력 범위에서 즉시 중단 신호는 없습니다.</strong><p>아래 미확인 자료와 잔금일 재확인은 여전히 필요합니다.</p></div></div>';
  const unknowns = result.critical_unknowns.length
    ? `<div class="unknown-box"><strong>확인 전에는 계약을 보류할 ${result.critical_unknowns.length}개 항목</strong><div>${result.critical_unknowns.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}</div></div>` : '';
  stopPanel.innerHTML = `<div class="panel-head"><div><p class="eyebrow">STOP FIRST</p><h2>치명적 조건과 미확인</h2></div></div>${stops}${unknowns}`;
}

function renderDocuments(result) {
  documentPanel.classList.remove('hidden');
  documentPanel.innerHTML = `<div class="panel-head"><div><p class="eyebrow">OFFICIAL EVIDENCE</p><h2>공식서류 확인판</h2></div><a class="text-link" href="/contract">전체 체크리스트 →</a></div>
    <div class="document-list">${result.documents.map((doc) => `<a href="${doc.url}" target="_blank" rel="noopener" class="document-row"><span class="doc-status ${doc.status === '확인 필요' || doc.status === '불가' ? 'needs' : 'done'}">${escapeHtml(doc.status)}</span><div><strong>${escapeHtml(doc.title)}</strong><p>${escapeHtml(doc.purpose)}</p></div><b>공식 사이트 ↗</b></a>`).join('')}</div>`;
}

function renderActions(result) {
  actionPanel.classList.remove('hidden');
  const plan = result.action_plan || [];
  if (!plan.length) { actionPanel.classList.add('hidden'); return; }

  const meta = (action) => [action.when, action.where].filter(Boolean).map((text) => `<span>${escapeHtml(text)}</span>`).join('');

  // 기본 상태는 모든 단계가 동일하고, 강조는 마우스를 올렸을 때만 나타난다.
  const steps = plan.map((action, index) => `
    <article class="step-row${action.priority === '계약 중단' ? ' step-stop' : ''}" tabindex="0">
      <span class="step-num">${index + 1}</span>
      <div class="step-main">
        <strong>${escapeHtml(action.title)}</strong>
        <p>${escapeHtml(action.detail)}</p>
      </div>
      <div class="step-meta"><span class="priority ${SL.priorityClass(action.priority)}">${escapeHtml(action.priority)}</span>${meta(action)}</div>
    </article>`).join('');

  actionPanel.innerHTML = `
    <div class="panel-head"><div><p class="eyebrow">NEXT ACTION</p><h2>지금 해야 할 순서</h2><p class="section-help">위에서부터 차례대로 하나씩. 앞 단계를 끝내기 전에 다음 단계로 넘어가지 마세요.</p></div><span class="step-count">총 ${plan.length}단계</span></div>
    <div class="step-list">${steps}</div>`;
}

function renderClauses(result) {
  clausePanel.classList.remove('hidden');
  const text = result.special_clauses.map((item, i) => `${i + 1}. ${item}`).join('\n\n');
  clausePanel.innerHTML = `<div class="panel-head"><div><p class="eyebrow">SPECIAL CLAUSES</p><h2>상황별 특약 초안</h2><p class="section-help">그대로 서명하지 말고 공인중개사·법률전문가와 계약 상황에 맞게 검토하세요.</p></div><button type="button" id="copy-clauses" class="secondary-button">초안 복사</button></div><div class="clause-paper">${result.special_clauses.map((item, i) => `<p><b>${i + 1}.</b> ${escapeHtml(item)}</p>`).join('')}</div>`;
  document.getElementById('copy-clauses').addEventListener('click', async (event) => {
    await navigator.clipboard.writeText(text);
    event.currentTarget.textContent = '복사 완료';
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = form.querySelector('[type="submit"]');
  button.disabled = true; button.textContent = '판정 중…';
  const payload = {
    deposit: Number(document.getElementById('deposit').value) * 10000,
    estimated_sale_price: Number(document.getElementById('sale').value) * 10000,
    district_score: Number(document.getElementById('district').value),
    building_age: Number(document.getElementById('age').value),
    mortgage: Number(document.getElementById('mortgage').value) * 10000,
    senior_deposit: Number(document.getElementById('senior-deposit').value) * 10000,
    guarantee_available: SL.boolValue(document.getElementById('guarantee').value),
    violation_building: SL.boolValue(document.getElementById('violation').value),
    trust_registration: SL.boolValue(document.getElementById('trust').value),
    owner_match: SL.boolValue(document.getElementById('owner-match').value),
    tax_checked: SL.boolValue(document.getElementById('tax-checked').value),
    broker_verified: SL.boolValue(document.getElementById('broker-verified').value),
    registry_checked: SL.boolValue(document.getElementById('registry-checked').value),
    mortgage_confirmed: SL.boolValue(document.getElementById('mortgage-confirmed').value),
    senior_deposit_confirmed: SL.boolValue(document.getElementById('senior-confirmed').value),
  };
  try {
    const response = await fetch('/api/property-risk', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error('진단 요청에 실패했습니다. 입력값을 확인하세요.');
    const result = await response.json();
    renderSummary(result); renderStops(result); renderDocuments(result); renderActions(result); renderClauses(result);
    sessionStorage.setItem('safelease-last-result', JSON.stringify({ savedAt: new Date().toISOString(), result }));
  } catch (error) {
    summaryPanel.className = 'panel decision-result decision-stop';
    summaryPanel.innerHTML = `<h2>진단 오류</h2><p>${escapeHtml(error.message)}</p>`;
  } finally { button.disabled = false; button.textContent = '계약 판정과 행동계획 만들기'; }
});

async function searchDong() {
  const query = document.getElementById('dong-search').value.trim();
  const box = document.getElementById('dong-search-results');
  if (!query) { box.textContent = '자치구 또는 법정동을 입력하세요.'; return; }
  box.textContent = '검색 중…';
  const response = await fetch(`/api/dong-risk?query=${encodeURIComponent(query)}&limit=8`);
  const { items } = await response.json();
  box.innerHTML = items.length ? items.map((item) => `<button type="button" data-code="${item.legal_dong_code}" data-score="${item.risk_score}" data-name="${escapeHtml(item.district)} ${escapeHtml(item.legal_dong)}">${escapeHtml(item.district)} ${escapeHtml(item.legal_dong)} <small>지역 참고 ${SL.fmt(item.risk_score)}</small></button>`).join('') : '<span>일치하는 서울 법정동이 없습니다.</span>';
  box.querySelectorAll('button').forEach((button) => button.addEventListener('click', () => {
    document.getElementById('district').value = button.dataset.score || 50;
    document.getElementById('selected-dong-code').value = button.dataset.code;
    document.getElementById('selected-dong').innerHTML = `<b>${escapeHtml(button.dataset.name)}</b> 선택 · 지역 참고점수 ${SL.fmt(button.dataset.score)}`;
    box.innerHTML = '';
  }));
}
document.getElementById('dong-search-button').addEventListener('click', searchDong);
document.getElementById('dong-search').addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); searchDong(); } });
