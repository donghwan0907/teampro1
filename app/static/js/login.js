const authForm = document.getElementById('auth-form');
const tabs = [...document.querySelectorAll('.auth-tabs button')];
const title = document.getElementById('auth-title');
const help = document.getElementById('auth-help');
const errorBox = document.getElementById('auth-error');
const password = document.getElementById('auth-password');
const submitButton = authForm.querySelector('[type="submit"]');
let mode = 'login';

function setMode(nextMode) {
  mode = nextMode;
  tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.mode === mode));
  errorBox.textContent = '';
  if (mode === 'register') {
    title.textContent = '처음 가입';
    help.textContent = '간단한 아이디를 만들고 체크리스트를 계정별로 안전하게 저장합니다.';
    password.autocomplete = 'new-password';
    submitButton.textContent = '가입하고 체크리스트 열기';
  } else {
    title.textContent = '로그인';
    help.textContent = '저장해 둔 체크리스트를 불러옵니다.';
    password.autocomplete = 'current-password';
    submitButton.textContent = '로그인하고 체크리스트 열기';
  }
}

tabs.forEach((tab) => tab.addEventListener('click', () => setMode(tab.dataset.mode)));

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorBox.textContent = '';
  submitButton.disabled = true;
  submitButton.textContent = mode === 'register' ? '가입 중…' : '로그인 중…';
  try {
    const response = await fetch(`/api/auth/${mode}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: document.getElementById('auth-username').value.trim(),
        password: password.value,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || '처리하지 못했습니다. 입력값을 확인해 주세요.');
    window.location.href = '/contract';
  } catch (error) {
    errorBox.textContent = error.message;
    submitButton.disabled = false;
    setMode(mode);
    errorBox.textContent = error.message;
  }
});

fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' })
  .then((response) => response.json())
  .then((data) => {
    if (data.authenticated) window.location.replace('/contract');
  })
  .catch(() => {});
