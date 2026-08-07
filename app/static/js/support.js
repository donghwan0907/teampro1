const SL = window.SafeLease;
const form = document.getElementById('support-form');
const regionSelect = document.getElementById('support-region');
const guaranteeList = document.getElementById('guarantee-list');
const resultPanel = document.getElementById('support-results');

function externalLink(url, label, primary = false) {
  return `<a class="${primary ? 'official-button' : 'secondary-button'}" href="${url}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`;
}

function statusClass(status) {
  return { active: 'status-active', always: 'status-always', check: 'status-check', closed: 'status-closed' }[status] || 'status-check';
}

function guaranteeCard(item) {
  return `<article class="support-card guarantee-card">
    <div class="support-card-head"><span class="provider-badge">${item.provider}</span><span class="status-pill status-active">운영 중</span></div>
    <h3>${item.title}</h3><p>${item.summary}</p>
    <small>${item.caution}</small>
    <div class="card-actions">${externalLink(item.official_url, item.action_label, true)}${externalLink(item.guide_url, '안내 보기')}</div>
  </article>`;
}

function programCard(item) {
  const reasons = item.match_reasons?.length ? `<ul class="match-list good">${item.match_reasons.map(x => `<li>${x}</li>`).join('')}</ul>` : '';
  const pending = item.pending_checks?.length ? `<ul class="match-list pending">${item.pending_checks.map(x => `<li>${x}</li>`).join('')}</ul>` : '';
  const failed = item.failed_reasons?.length ? `<ul class="match-list failed">${item.failed_reasons.map(x => `<li>${x}</li>`).join('')}</ul>` : '';
  return `<article class="support-card program-card">
    <div class="support-card-head"><span class="category-chip">${item.category}</span><span class="status-pill ${statusClass(item.status)}">${item.status_label}</span></div>
    <h3>${item.title}</h3><p>${item.summary}</p>
    <dl class="program-meta"><div><dt>대상</dt><dd>${item.target_summary}</dd></div><div><dt>지원</dt><dd>${item.benefit_summary}</dd></div></dl>
    ${item.match_status ? `<div class="match-summary"><strong>${item.match_status}</strong>${reasons}${pending}${failed}</div>` : ''}
    <p class="source-line">${item.source_name} · 최근 확인 ${item.verified_at}</p>
    <div class="card-actions">${externalLink(item.apply_url, '신청·접수 확인', true)}${externalLink(item.official_url, '공식 안내')}</div>
  </article>`;
}

async function loadBase() {
  const [regionResponse, guaranteeResponse] = await Promise.all([fetch('/api/support-regions'), fetch('/api/guarantees')]);
  const regions = (await regionResponse.json()).items;
  const guarantees = (await guaranteeResponse.json()).items;
  regionSelect.innerHTML += regions.map(r => `<option value="${r.code}">${r.name}</option>`).join('');
  guaranteeList.innerHTML = guarantees.map(guaranteeCard).join('');
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!regionSelect.value) { resultPanel.innerHTML = '<h2>지역을 선택하세요.</h2>'; return; }
  const payload = {
    region_code: regionSelect.value,
    age: Number(document.getElementById('support-age').value || 0),
    annual_income: Number(document.getElementById('support-income').value || 0) * 10000,
    deposit: Number(document.getElementById('support-deposit').value || 0) * 10000,
    marital_status: document.getElementById('support-marital').value,
    guarantee_joined: SL.boolValue(document.getElementById('support-guarantee').value),
    victim_confirmed: SL.boolValue(document.getElementById('support-victim').value),
    moved: SL.boolValue(document.getElementById('support-moved').value),
    renter: true,
  };
  const response = await fetch('/api/support-programs/match', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const data = await response.json();
  resultPanel.classList.remove('empty-state');
  resultPanel.innerHTML = `<div class="panel-head"><div><p class="eyebrow">MATCHED PROGRAMS</p><h2>3. ${data.region?.name || ''} 맞춤 결과</h2><p class="section-help">신청 가능성 순서로 정렬했습니다.</p></div></div>
    <div class="support-card-grid">${data.items.map(programCard).join('')}</div><p class="small-note">${data.disclaimer}</p>`;
  resultPanel.scrollIntoView({behavior:'smooth', block:'start'});
});

loadBase().catch(error => { resultPanel.innerHTML = `<h2>지원정보 오류</h2><p>${error.message}</p>`; });
