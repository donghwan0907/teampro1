(() => {
  const accountLink = document.getElementById('header-account');
  if (!accountLink) return;

  fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' })
    .then((response) => response.json())
    .then((data) => {
      if (!data.authenticated) return;
      accountLink.textContent = `${data.user.username} · 로그아웃`;
      accountLink.href = '#';
      accountLink.classList.add('signed-in');
      accountLink.addEventListener('click', async (event) => {
        event.preventDefault();
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
        window.location.reload();
      });
    })
    .catch(() => {});
})();
