export var PANELS = ['posts', 'map', 'list'];
export var DEFAULT_PANEL = 'posts';

export function panelFromHash(hash) {
  var id = String(hash || '').replace(/^#/, '').toLowerCase();
  return PANELS.indexOf(id) >= 0 ? id : DEFAULT_PANEL;
}

export function applyPanel(root, panel) {
  if (!root) return DEFAULT_PANEL;
  var id = panelFromHash('#' + String(panel || ''));
  var panels = root.querySelectorAll('[data-d1-panel]');
  Array.prototype.forEach.call(panels, function (el) {
    var on = el.getAttribute('data-d1-panel') === id;
    el.classList.toggle('is-current', on);
    if (on) el.removeAttribute('hidden');
    else el.setAttribute('hidden', '');
  });
  var links = root.querySelectorAll('[data-d1-nav] a[href^="#"]');
  Array.prototype.forEach.call(links, function (a) {
    var href = a.getAttribute('href') || '';
    if (href === '#' + id) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  if (id === 'map') revealMap(root);
  return id;
}

function revealMap(root) {
  var iframe = root.querySelector('#map iframe');
  if (!iframe || iframe.getAttribute('data-shown') === '1') return;
  iframe.setAttribute('data-shown', '1');
  var src = iframe.getAttribute('src');
  if (src) iframe.setAttribute('src', src);
}

function bindMissionNav(root) {
  if (!root) return;
  root.classList.add('d1-mission-page--tabs');
  function sync() {
    applyPanel(root, panelFromHash(window.location.hash));
  }
  window.addEventListener('hashchange', sync);
  sync();
}

function initMissionNav() {
  if (typeof document === 'undefined') return;
  var page = document.querySelector('[data-d1-mission]');
  if (page) bindMissionNav(page);
}

initMissionNav();
