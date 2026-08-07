const storageKey = 'safelease-contract-checklist-v2';
const items = [...document.querySelectorAll('.check-item')];
const accountPanel = document.getElementById('checklist-account');
let state = {};
let currentUser = null;
let saveTimer = null;

function readGuestState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch (_) {
    return {};
  }
}

function setInputsDisabled(disabled) {
  items.forEach((item) => {
    item.querySelector('input[type="checkbox"]').disabled = disabled;
    item.querySelector('.evidence-date').disabled = disabled;
  });
}

function applyState() {
  items.forEach((item) => {
    const entry = state[item.dataset.key] || {};
    const checkbox = item.querySelector('input[type="checkbox"]');
    const date = item.querySelector('.evidence-date');
    checkbox.checked = Boolean(entry.checked);
    date.value = typeof entry.date === 'string' ? entry.date : '';
    item.classList.toggle('completed', checkbox.checked);
  });
  updateProgress();
}

function updateProgress() {
  const completed = items.filter((item) => state[item.dataset.key]?.checked).length;
  const pct = items.length ? Math.round(completed / items.length * 100) : 0;
  document.getElementById('progress-value').textContent = `${pct}%`;
  const orb = document.querySelector('.progress-orb');
  if (orb) orb.style.background = `conic-gradient(#176b5b ${pct * 3.6}deg, #e5ece9 0)`;
  document.getElementById('progress-label').textContent = `${completed} / ${items.length} 확인`;
  document.getElementById('master-progress-bar').style.width = `${pct}%`;
}

function setSyncStatus(message, status = '') {
  const target = document.getElementById('checklist-sync-status');
  if (!target) return;
  target.textContent = message;
  target.className = status;
}

function renderAccount() {
  if (currentUser) {
    accountPanel.classList.add('signed-in');
    accountPanel.innerHTML = `
      <div class="account-summary"><span class="account-dot"></span><div><strong><span id="checklist-username"></span>님의 계정 저장</strong><p id="checklist-sync-status">저장된 체크리스트를 불러왔습니다.</p></div></div>
      <button type="button" id="checklist-logout" class="secondary-button">로그아웃</button>`;
    document.getElementById('checklist-username').textContent = currentUser.username;
    document.getElementById('checklist-logout').addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
      window.location.reload();
    });
    return;
  }
  accountPanel.classList.remove('signed-in');
  accountPanel.innerHTML = `
    <div class="account-summary"><span class="account-dot"></span><div><strong>이 기기에 임시 저장 중</strong><p id="checklist-sync-status">로그인하면 체크 기록을 계정별로 저장하고 다시 불러올 수 있습니다.</p></div></div>
    <a class="secondary-button" href="/login">로그인·가입</a>`;
}

async function saveToServer() {
  if (!currentUser) return;
  setSyncStatus('계정 저장소에 저장 중…', 'saving');
  try {
    const response = await fetch('/api/auth/checklist', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state }),
    });
    if (response.status === 401) {
      currentUser = null;
      localStorage.setItem(storageKey, JSON.stringify(state));
      renderAccount();
      setSyncStatus('로그인이 만료되어 이 기기에 임시 저장했습니다.', 'error');
      return;
    }
    if (!response.ok) throw new Error('저장 실패');
    const now = new Date();
    setSyncStatus(`계정 저장 완료 · ${now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`, 'saved');
  } catch (_) {
    setSyncStatus('저장하지 못했습니다. 네트워크를 확인한 뒤 다시 체크해 주세요.', 'error');
  }
}

function persist() {
  if (!currentUser) {
    localStorage.setItem(storageKey, JSON.stringify(state));
    setSyncStatus('이 기기에 임시 저장했습니다.', 'saved');
    return;
  }
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveToServer, 200);
}

function bindChecklist() {
  items.forEach((item) => {
    const key = item.dataset.key;
    const checkbox = item.querySelector('input[type="checkbox"]');
    const date = item.querySelector('.evidence-date');
    checkbox.addEventListener('change', () => {
      state[key] = { checked: checkbox.checked, date: date.value };
      item.classList.toggle('completed', checkbox.checked);
      persist();
      updateProgress();
    });
    date.addEventListener('change', () => {
      state[key] = { checked: checkbox.checked, date: date.value };
      persist();
    });
  });
}

async function initializeChecklist() {
  setInputsDisabled(true);
  try {
    const meResponse = await fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' });
    const me = await meResponse.json();
    if (me.authenticated) {
      currentUser = me.user;
      const checklistResponse = await fetch('/api/auth/checklist', { credentials: 'same-origin', cache: 'no-store' });
      if (!checklistResponse.ok) throw new Error('체크리스트를 불러오지 못했습니다.');
      const saved = await checklistResponse.json();
      state = saved.state || {};
    } else {
      state = readGuestState();
    }
  } catch (_) {
    currentUser = null;
    state = readGuestState();
  }
  renderAccount();
  applyState();
  setInputsDisabled(false);
}

document.querySelectorAll('.stage-nav button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.stage-nav button').forEach((item) => item.classList.remove('active'));
    document.querySelectorAll('.check-stage').forEach((item) => item.classList.remove('active'));
    button.classList.add('active');
    document.getElementById(button.dataset.target).classList.add('active');
  });
});

document.getElementById('print-checklist').addEventListener('click', () => window.print());
document.getElementById('reset-checklist').addEventListener('click', async () => {
  const target = currentUser ? '로그인 계정 저장소' : '이 브라우저';
  if (!window.confirm(`${target}에 저장된 체크 기록을 모두 지울까요?`)) return;
  state = {};
  clearTimeout(saveTimer);
  if (currentUser) await saveToServer();
  else localStorage.removeItem(storageKey);
  applyState();
});

bindChecklist();
initializeChecklist();
