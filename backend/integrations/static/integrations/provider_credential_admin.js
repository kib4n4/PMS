// Admin enhancements: dynamic provider fields, fold/unfold sections with icons, and theme picker
(function () {
  function $(id) { return document.getElementById(id); }

  function setVisibility(fieldId, visible) {
    var el = $(fieldId);
    if (!el) return;
    var row = el.closest('.form-row') || el.closest('.field-box') || el.parentElement;
    if (row) row.style.display = visible ? '' : 'none';
    el.required = visible && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA');
  }

  // Inline SVG icons for providers
  var ICONS = {
    twilio: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 7L9 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 7H14L9 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    resend: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 8l7.89 5.26a2 2 0 0 0 2.22 0L21 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 19H3V8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    daraja: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 1v22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M17 5H7a5 5 0 0 0 0 10h10a5 5 0 1 0 0-10z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    default: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/></svg>'
  };

  function applyForProvider(provider) {
    var mapping = {
      'twilio': 'oauth2',
      'daraja': 'oauth2',
      'resend': 'bearer'
    };
    var auth = mapping[provider] || 'json';

    // set auth_type select if present
    var authEl = $('id_auth_type');
    if (authEl) {
      authEl.value = auth;
      var ev = new Event('change', { bubbles: true });
      authEl.dispatchEvent(ev);
    }

    var showJson = auth === 'json';
    var showOauth = auth === 'oauth2';
    var showBearer = auth === 'bearer';

    setVisibility('id_credentials_json', showJson);
    setVisibility('id_client_id', showOauth);
    setVisibility('id_client_secret', showOauth);
    setVisibility('id_bearer_token', showBearer);
    setVisibility('id_whatsapp_number', provider === 'twilio');

    // Attach icon to provider label
    attachProviderIcon(provider);
  }

  function attachProviderIcon(provider) {
    var providerLabel = document.querySelector("label[for='id_provider']");
    if (!providerLabel) return;
    // remove existing icon if any
    var existing = providerLabel.querySelector('.provider-icon');
    if (existing) existing.remove();
    var span = document.createElement('span');
    span.className = 'provider-icon';
    span.style.marginLeft = '8px';
    span.innerHTML = ICONS[provider] || ICONS.default;
    providerLabel.appendChild(span);
  }

  // Folding helper: allow toggling visibility of a form-row
  function makeFoldable(fieldId) {
    var el = $(fieldId);
    if (!el) return;
    var row = el.closest('.form-row') || el.closest('.field-box') || el.parentElement;
    if (!row) return;
    var header = row.querySelector('label') || row.querySelector('h3') || row.firstElementChild;
    if (!header) return;
    // avoid duplicating toggle
    if (header.querySelector('.fold-toggle')) return;
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'fold-toggle';
    toggle.title = 'Toggle details';
    toggle.innerHTML = '<span class="fold-icon">▾</span>';
    toggle.addEventListener('click', function () {
      var collapsed = row.classList.toggle('collapsed');
      var icon = toggle.querySelector('.fold-icon');
      if (collapsed) icon.textContent = '▸'; else icon.textContent = '▾';
    });
    // insert at start of header
    header.insertBefore(toggle, header.firstChild);
  }

  // Theme picker: 7 palettes, mostly blue default
  var THEMES = [
    { name: 'Blue (Default)', class: 'theme-1' },
    { name: 'Cyan', class: 'theme-2' },
    { name: 'Indigo', class: 'theme-3' },
    { name: 'Teal', class: 'theme-4' },
    { name: 'Purple', class: 'theme-5' },
    { name: 'Green', class: 'theme-6' },
    { name: 'Slate', class: 'theme-7' }
  ];

  function applyTheme(themeClass) {
    document.body.classList.remove(...THEMES.map(t => t.class));
    document.body.classList.add(themeClass);
    try { localStorage.setItem('integrations_admin_theme', themeClass); } catch (e) {}
  }

  function buildThemePicker() {
    var container = document.createElement('div');
    container.className = 'theme-picker';
    THEMES.forEach(function (t, idx) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'theme-swatch ' + t.class;
      btn.title = t.name;
      btn.addEventListener('click', function () { applyTheme(t.class); });
      container.appendChild(btn);
    });
    // add to top-right of admin
    document.body.appendChild(container);
    // apply saved
    try {
      var saved = localStorage.getItem('integrations_admin_theme');
      if (saved) applyTheme(saved);
    } catch (e) {}
  }

  function init() {
    var providerEl = $('id_provider');
    if (providerEl) {
      applyForProvider(providerEl.value);
      providerEl.addEventListener('change', function (e) { applyForProvider(e.target.value); });
    }

    // Make certain credential blocks foldable
    ['id_credentials_json', 'id_client_id', 'id_client_secret', 'id_bearer_token', 'id_whatsapp_number'].forEach(function (fid) { makeFoldable(fid); });

    // Build theme picker
    buildThemePicker();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
