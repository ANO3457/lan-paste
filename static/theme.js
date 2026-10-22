(() => {
  const root = document.documentElement;
  const toggle = document.querySelector('[data-theme-toggle]');
  const label = document.querySelector('[data-theme-label]');
  const icon = document.querySelector('.theme-icon');
  const metaTheme = document.querySelector('meta[name="theme-color"]');

  function applyTheme(theme, persist = true) {
    const next = theme === 'dark' ? 'dark' : 'light';
    root.dataset.theme = next;
    if (persist) {
      try { localStorage.setItem('lan-paste-theme', next); } catch (_) {}
    }
    if (label) label.textContent = next === 'dark' ? 'Dark' : 'Light';
    if (icon) icon.textContent = next === 'dark' ? '☾' : '☼';
    if (toggle) {
      toggle.setAttribute('aria-label', 'Switch to ' + (next === 'dark' ? 'light' : 'dark') + ' theme');
      toggle.setAttribute('aria-pressed', String(next === 'dark'));
      toggle.title = 'Switch to ' + (next === 'dark' ? 'light' : 'dark') + ' theme';
    }
    if (metaTheme) metaTheme.setAttribute('content', next === 'dark' ? '#0b1020' : '#f5f7fb');
  }

  let saved = null;
  try { saved = localStorage.getItem('lan-paste-theme'); } catch (_) {}
  applyTheme(saved === 'light' || saved === 'dark' ? saved : root.dataset.theme || 'light', false);

  if (toggle) {
    toggle.addEventListener('click', () => {
      applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
    });
  }
})();
