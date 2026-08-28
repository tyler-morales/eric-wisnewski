export const PENDING_EMAIL_KEY = 'subscribe_pending_email';
export const SAVED_LISTS_KEY = 'subscribe_lists';

const VALID_LIST_IDS = ['posts', 'gradys-tour', 'da-breakdown-w-tad'];

export function normalizePendingEmail(value) {
  if (typeof value !== 'string') return '';
  if (/[\r\n]/.test(value)) return '';
  var email = value.trim().toLowerCase();
  if (!email || email.length > 320 || email.indexOf('@') < 0) return '';
  return email;
}

function browserStorage() {
  try {
    return window.localStorage;
  } catch (_) {
    return null;
  }
}

export function readPendingEmail(store) {
  if (!store || typeof store.getItem !== 'function') return '';
  try {
    return normalizePendingEmail(store.getItem(PENDING_EMAIL_KEY) || '');
  } catch (_) {
    return '';
  }
}

export function writePendingEmail(store, email) {
  var value = normalizePendingEmail(email);
  if (!store || typeof store.setItem !== 'function' || !value) return;
  try {
    store.setItem(PENDING_EMAIL_KEY, value);
  } catch (_) { }
}

export function clearPendingEmail(store) {
  if (!store || typeof store.removeItem !== 'function') return;
  try {
    store.removeItem(PENDING_EMAIL_KEY);
  } catch (_) { }
}

export function normalizeSavedLists(value) {
  var raw = value;
  if (typeof raw === 'string') {
    try {
      raw = JSON.parse(raw);
    } catch (_) {
      return [];
    }
  }
  if (!Array.isArray(raw)) return [];
  var out = [];
  var seen = {};
  var i;
  for (i = 0; i < raw.length; i++) {
    var list = typeof raw[i] === 'string' ? raw[i].trim() : '';
    if (VALID_LIST_IDS.indexOf(list) < 0 || seen[list]) continue;
    seen[list] = true;
    out.push(list);
  }
  return out;
}

export function readSavedLists(store) {
  if (!store || typeof store.getItem !== 'function') return [];
  try {
    return normalizeSavedLists(store.getItem(SAVED_LISTS_KEY) || '');
  } catch (_) {
    return [];
  }
}

export function writeSavedLists(store, lists) {
  if (!store || typeof store.setItem !== 'function') return;
  try {
    store.setItem(SAVED_LISTS_KEY, JSON.stringify(normalizeSavedLists(lists)));
  } catch (_) { }
}

export function mergeSavedLists(current, added) {
  return normalizeSavedLists([].concat(current || [], added || []));
}

function selectedLists(formEl) {
  var boxes = formEl.querySelectorAll('input[name="lists"]:checked');
  var lists = [];
  for (var i = 0; i < boxes.length; i++) {
    lists.push(boxes[i].value);
  }
  return lists;
}

function showStatus(statusEl, errorEl, msg) {
  if (!statusEl) return;
  statusEl.textContent = msg;
  statusEl.hidden = false;
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.hidden = true;
  }
}

function showError(statusEl, errorEl, msg) {
  if (!errorEl) return;
  errorEl.textContent = msg;
  errorEl.hidden = false;
  if (statusEl) {
    statusEl.textContent = '';
    statusEl.hidden = true;
  }
}

function clearMessages(statusEl, errorEl) {
  if (statusEl) {
    statusEl.textContent = '';
    statusEl.hidden = true;
  }
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.hidden = true;
  }
}

export function applyLists(formEl, lists) {
  var wanted = {};
  var i;
  for (i = 0; i < (lists || []).length; i++) {
    wanted[lists[i]] = true;
  }
  var boxes = formEl.querySelectorAll('input[name="lists"]');
  for (i = 0; i < boxes.length; i++) {
    boxes[i].checked = !!wanted[boxes[i].value];
  }
}

function parseJsonResponse(res) {
  return res.text().then(function (text) {
    var data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (_) {
        data = {};
      }
    }
    return { ok: res.ok, status: res.status, data: data };
  });
}

function initSignup() {
  var section = document.getElementById('subscribe');
  if (!section) return;

  var formEl = section.querySelector('.subscribe-form');
  var statusEl = section.querySelector('.subscribe-status');
  var errorEl = section.querySelector('.subscribe-error');
  var headingEl = section.querySelector('.subscribe-heading');
  var nextEl = document.getElementById('subscribe-confirm-next');
  var nextCopyEl = document.getElementById('subscribe-confirm-copy');
  var nextBackEl = document.getElementById('subscribe-confirm-back');
  if (!formEl) return;

  var defaultHeading = headingEl ? headingEl.textContent : '';

  var siteKey = (section.dataset && section.dataset.turnstileSitekey)
    ? section.dataset.turnstileSitekey.trim()
    : '';
  var widgetId = null;

  function renderTurnstile() {
    var container = document.getElementById('subscribe-turnstile-container');
    if (!container || !siteKey || typeof turnstile === 'undefined') return;
    try {
      if (widgetId != null) {
        turnstile.remove(widgetId);
      }
      widgetId = turnstile.render(container, {
        sitekey: siteKey,
        theme: 'light'
      });
    } catch (_) {
      widgetId = null;
    }
  }

  function getTurnstileToken() {
    if (widgetId == null || typeof turnstile === 'undefined') return '';
    try {
      return turnstile.getResponse(widgetId) || '';
    } catch (_) {
      return '';
    }
  }

  function resetTurnstile() {
    if (widgetId == null || typeof turnstile === 'undefined') return;
    try {
      turnstile.reset(widgetId);
    } catch (_) { }
  }

  function setProgress(step) {
    var items = section.querySelectorAll('.subscribe-progress [data-step]');
    var i;
    for (i = 0; i < items.length; i++) {
      var el = items[i];
      var name = el.getAttribute('data-step');
      el.classList.remove('subscribe-progress-done', 'subscribe-progress-current');
      el.removeAttribute('aria-current');
      if (step === 'confirm') {
        if (name === 'email') el.classList.add('subscribe-progress-done');
        if (name === 'confirm') {
          el.classList.add('subscribe-progress-current');
          el.setAttribute('aria-current', 'step');
        }
      } else if (name === 'email') {
        el.classList.add('subscribe-progress-current');
        el.setAttribute('aria-current', 'step');
      }
    }
  }

  function confirmNextCopy(email) {
    return (
      'We sent a link to ' +
      email +
      '. Open that email and click Confirm. You will not get posts until you do. If you don\'t see it, check spam.'
    );
  }

  function showConfirmNext(email, silent) {
    if (!nextEl || !nextCopyEl) {
      showStatus(statusEl, errorEl, confirmNextCopy(email));
      return;
    }
    formEl.hidden = true;
    nextCopyEl.textContent = confirmNextCopy(email);
    nextEl.hidden = false;
    setProgress('confirm');
    if (headingEl) headingEl.textContent = 'Check your email';
    if (!silent) nextEl.focus();
  }

  function showSignupForm() {
    clearPendingEmail(browserStorage());
    if (nextEl) nextEl.hidden = true;
    formEl.hidden = false;
    setProgress('email');
    if (headingEl && defaultHeading) headingEl.textContent = defaultHeading;
    var emailInput = formEl.querySelector('#subscribe-email');
    if (emailInput) emailInput.focus();
  }

  if (nextBackEl) {
    nextBackEl.addEventListener('click', function () {
      showSignupForm();
      resetTurnstile();
    });
  }

  try {
    if (typeof turnstile !== 'undefined' && turnstile.ready) {
      turnstile.ready(renderTurnstile);
    } else {
      window.addEventListener('load', function () {
        setTimeout(renderTurnstile, 100);
      });
    }
  } catch (_) { }

  formEl.addEventListener('submit', function (e) {
    e.preventDefault();
    clearMessages(statusEl, errorEl);

    var emailInput = formEl.querySelector('#subscribe-email');
    var email = emailInput ? emailInput.value.trim() : '';
    var lists = selectedLists(formEl);

    if (!email) {
      showError(statusEl, errorEl, 'Enter your email address.');
      if (emailInput) emailInput.focus();
      return;
    }
    if (!lists.length) {
      showError(statusEl, errorEl, 'Select at least one list.');
      return;
    }

    var token = getTurnstileToken();
    var turnstilePresent = !!document.getElementById('subscribe-turnstile-container') &&
      !!siteKey &&
      typeof turnstile !== 'undefined' &&
      widgetId != null;
    if (turnstilePresent && !token) {
      showError(statusEl, errorEl, 'Complete the verification checkbox.');
      return;
    }

    var submitBtn = formEl.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: email,
        lists: lists,
        cf_turnstile_response: token
      })
    })
      .then(parseJsonResponse)
      .then(function (result) {
        if (!result.ok) {
          showError(statusEl, errorEl, (result.data && result.data.error) || 'Could not subscribe. Try again.');
          resetTurnstile();
          return;
        }
        var store = browserStorage();
        writeSavedLists(store, mergeSavedLists(readSavedLists(store), lists));
        if (result.data && result.data.needsConfirm) {
          writePendingEmail(browserStorage(), email);
          showConfirmNext(email);
        } else {
          clearPendingEmail(browserStorage());
          showStatus(
            statusEl,
            errorEl,
            (result.data && result.data.message) || 'Check your inbox to confirm.'
          );
        }
        resetTurnstile();
      })
      .catch(function () {
        showError(statusEl, errorEl, 'Could not reach the server. Try again.');
        resetTurnstile();
      })
      .finally(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  });

  var saved = readSavedLists(browserStorage());
  if (saved.length) applyLists(formEl, saved);

  var pending = readPendingEmail(browserStorage());
  if (pending) showConfirmNext(pending, true);
}

function initConfirmed() {
  if (typeof location === 'undefined') return;
  if (!/\/subscribe\/confirmed\/?$/.test(location.pathname || '')) return;
  clearPendingEmail(browserStorage());
}

function initManage() {
  var section = document.getElementById('subscribe-manage');
  if (!section) return;

  var formEl = section.querySelector('.subscribe-form');
  var statusEl = section.querySelector('.subscribe-status');
  var errorEl = section.querySelector('.subscribe-error');
  var emailEl = document.getElementById('subscribe-manage-email');
  if (!formEl) return;

  var params = new URLSearchParams(window.location.search);
  var token = (params.get('token') || '').trim();
  if (!token) {
    formEl.hidden = true;
    showError(
      statusEl,
      errorEl,
      'This preferences link is missing or invalid. Use the unsubscribe link from your email.'
    );
    if (errorEl) errorEl.focus();
    return;
  }

  showStatus(statusEl, errorEl, 'Loading your preferences…');
  var controls = formEl.querySelectorAll('input, button');
  var i;
  for (i = 0; i < controls.length; i++) {
    controls[i].disabled = true;
  }

  fetch('/api/subscribe?preferences=' + encodeURIComponent(token))
    .then(parseJsonResponse)
    .then(function (result) {
      if (!result.ok) {
        formEl.hidden = true;
        showError(
          statusEl,
          errorEl,
          (result.data && result.data.error) || 'Invalid or expired link.'
        );
        if (errorEl) errorEl.focus();
        return;
      }
      applyLists(formEl, result.data && result.data.lists);
      if (result.data && Array.isArray(result.data.lists)) {
        writeSavedLists(browserStorage(), result.data.lists);
      }
      if (emailEl && result.data && result.data.email) {
        emailEl.textContent = 'Updating preferences for ' + result.data.email;
        emailEl.hidden = false;
      }
      clearMessages(statusEl, errorEl);
      for (i = 0; i < controls.length; i++) {
        controls[i].disabled = false;
      }
    })
    .catch(function () {
      formEl.hidden = true;
      showError(statusEl, errorEl, 'Could not reach the server. Try again.');
      if (errorEl) errorEl.focus();
    });

  formEl.addEventListener('submit', function (e) {
    e.preventDefault();
    clearMessages(statusEl, errorEl);

    var lists = selectedLists(formEl);
    var submitBtn = formEl.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    fetch('/api/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token, lists: lists })
    })
      .then(parseJsonResponse)
      .then(function (result) {
        if (!result.ok) {
          showError(
            statusEl,
            errorEl,
            (result.data && result.data.error) || 'Could not save preferences. Try again.'
          );
          return;
        }
        if (result.data && result.data.lists) {
          applyLists(formEl, result.data.lists);
          writeSavedLists(browserStorage(), result.data.lists);
        }
        showStatus(
          statusEl,
          errorEl,
          (result.data && result.data.message) || 'Preferences saved.'
        );
      })
      .catch(function () {
        showError(statusEl, errorEl, 'Could not reach the server. Try again.');
      })
      .finally(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  });
}

if (typeof document !== 'undefined') {
  initSignup();
  initManage();
  initConfirmed();
}
