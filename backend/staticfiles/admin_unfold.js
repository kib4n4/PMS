// Global admin unfold/fold behavior for Django admin
document.addEventListener('DOMContentLoaded', function () {
  function makeFoldableRow(row) {
    if (!row || row.classList.contains('foldable-initialized')) return;
    row.classList.add('foldable-initialized');
    var header = row.querySelector('label') || row.querySelector('h3') || row.firstElementChild;
    if (!header) return;
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'fold-toggle';
    toggle.setAttribute('aria-expanded', 'true');
    toggle.innerHTML = '<span class="fold-icon">▾</span>';
    toggle.addEventListener('click', function () {
      var collapsed = row.classList.toggle('collapsed');
      toggle.setAttribute('aria-expanded', !collapsed);
      var icon = toggle.querySelector('.fold-icon');
      icon.textContent = collapsed ? '▸' : '▾';
    });
    header.insertBefore(toggle, header.firstChild);
  }

  // Apply to form rows in admin forms
  document.querySelectorAll('.change-form .form-row, .change-form .field-box').forEach(makeFoldableRow);

  // Apply to inlines
  document.querySelectorAll('.inline-related').forEach(function (inline) {
    inline.querySelectorAll('.form-row, .field-box').forEach(makeFoldableRow);
  });

  // Also make list filter groups foldable
  document.querySelectorAll('.module .module caption, .filter').forEach(function (el) {
    var container = el.closest('.module') || el.parentElement;
    if (container) makeFoldableRow(container);
  });

  // Provide a global toggle to expand/collapse all
  var adminHeader = document.querySelector('#header');
  if (adminHeader) {
    var globalToggle = document.createElement('button');
    globalToggle.type = 'button';
    globalToggle.textContent = 'Toggle detail fold';
    globalToggle.className = 'global-fold-toggle';
    globalToggle.style.marginLeft = '12px';
    globalToggle.addEventListener('click', function () {
      var anyCollapsed = !!document.querySelector('.form-row.collapsed, .field-box.collapsed');
      document.querySelectorAll('.form-row, .field-box').forEach(function (r) {
        if (anyCollapsed) r.classList.remove('collapsed'); else r.classList.add('collapsed');
      });
    });
    adminHeader.appendChild(globalToggle);
  }

});
