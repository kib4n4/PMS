(function () {
  const STORAGE_KEY = 'pms-admin-theme';
  const DEFAULT_THEME = 'theme-1';
  const THEMES = ['theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5', 'theme-6', 'theme-7'];

  function getPreferredTheme() {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved && THEMES.includes(saved)) return saved;
    const fromBody = document.body && document.body.dataset && document.body.dataset.adminTheme;
    if (fromBody && THEMES.includes(fromBody)) return fromBody;
    return DEFAULT_THEME;
  }

  function applyTheme(theme) {
    if (!THEMES.includes(theme)) {
      theme = DEFAULT_THEME;
    }
    document.body.dataset.adminTheme = theme;
    window.localStorage.setItem(STORAGE_KEY, theme);
  }

  const labels = {
    'theme-1': 'Blue',
    'theme-2': 'Cyan',
    'theme-3': 'Indigo',
    'theme-4': 'Teal',
    'theme-5': 'Purple',
    'theme-6': 'Green',
    'theme-7': 'Slate',
  };

  function ensureThemeControl() {
    const existing = document.querySelector('[data-admin-theme-toggle]');
    if (existing) return existing;

    const header = document.querySelector('#nav-sidebar') || document.querySelector('#header') || document.querySelector('header');
    if (!header) return null;

    const wrapper = document.createElement('div');
    wrapper.className = 'pms-admin-theme-picker';

    const icon = document.createElement('span');
    icon.className = 'material-symbols-outlined pms-admin-theme-icon';
    icon.textContent = 'palette';

    const select = document.createElement('select');
    select.setAttribute('data-admin-theme-toggle', 'true');
    select.setAttribute('aria-label', 'Admin theme');
    select.style.padding = '0.45rem 0.7rem';
    select.style.borderRadius = '0.7rem';
    select.style.border = '1px solid rgba(255,255,255,0.25)';
    select.style.background = 'rgba(255,255,255,0.1)';
    select.style.color = '#fff';
    select.style.outline = 'none';

    THEMES.forEach(function (theme) {
      const option = document.createElement('option');
      option.value = theme;
      option.textContent = labels[theme] || theme;
      select.appendChild(option);
    });

    wrapper.appendChild(icon);
    wrapper.appendChild(select);
    header.appendChild(wrapper);
    return select;
  }

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(getPreferredTheme());

    const control = ensureThemeControl();
    if (control) {
      control.value = document.body.dataset.adminTheme;
      control.addEventListener('change', function () {
        applyTheme(this.value);
      });
    }
  });
})();
