(() => {
  const root = document.documentElement;
  const button = document.getElementById('themeToggle');
  const applyTheme = (theme) => {
    const dark = theme === 'dark';
    root.dataset.theme = dark ? 'dark' : 'light';
    document.body.classList.toggle('dark-mode', dark);
    if (button) {
      button.setAttribute('aria-pressed', String(dark));
      button.setAttribute('aria-label', dark ? 'Activar modo claro' : 'Activar modo oscuro');
      button.title = dark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
      const icon = button.querySelector('.theme-toggle-icon');
      const label = button.querySelector('.theme-toggle-label');
      if (icon) icon.textContent = dark ? '☀' : '☾';
      if (label) label.textContent = dark ? 'Modo claro' : 'Modo oscuro';
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', dark ? '#171916' : '#f6f4ef');
  };
  let current = 'light';
  try { current = localStorage.getItem('vesta-theme') || 'light'; } catch (_) { /* storage might be disabled */ }
  applyTheme(current);
  button?.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem('vesta-theme', next); } catch (_) { /* theme still changes for this page */ }
  });
})();
