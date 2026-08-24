(function () {
  var section = document.getElementById('subscribe');
  if (!section) return;

  var formEl = section.querySelector('.subscribe-form');
  var statusEl = section.querySelector('.subscribe-status');
  var errorEl = section.querySelector('.subscribe-error');
  if (!formEl) return;

  var siteKey = (section.dataset && section.dataset.turnstileSitekey)
    ? section.dataset.turnstileSitekey.trim()
    : '';
  var widgetId = null;

  function showStatus(msg) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.hidden = false;
    if (errorEl) {
      errorEl.textContent = '';
      errorEl.hidden = true;
    }
  }

  function showError(msg) {
    if (!errorEl) return;
    errorEl.textContent = msg;
    errorEl.hidden = false;
    if (statusEl) {
      statusEl.textContent = '';
      statusEl.hidden = true;
    }
  }

  function clearMessages() {
    if (statusEl) {
      statusEl.textContent = '';
      statusEl.hidden = true;
    }
    if (errorEl) {
      errorEl.textContent = '';
      errorEl.hidden = true;
    }
  }

  function selectedLists() {
    var boxes = formEl.querySelectorAll('input[name="lists"]:checked');
    var lists = [];
    for (var i = 0; i < boxes.length; i++) {
      lists.push(boxes[i].value);
    }
    return lists;
  }

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
    } catch (_) {}
  }

  try {
    if (typeof turnstile !== 'undefined' && turnstile.ready) {
      turnstile.ready(renderTurnstile);
    } else {
      window.addEventListener('load', function () {
        setTimeout(renderTurnstile, 100);
      });
    }
  } catch (_) {}

  formEl.addEventListener('submit', function (e) {
    e.preventDefault();
    clearMessages();

    var emailInput = formEl.querySelector('#subscribe-email');
    var email = emailInput ? emailInput.value.trim() : '';
    var lists = selectedLists();

    if (!email) {
      showError('Enter your email address.');
      if (emailInput) emailInput.focus();
      return;
    }
    if (!lists.length) {
      showError('Select at least one list.');
      return;
    }

    var token = getTurnstileToken();
    var turnstilePresent = !!document.getElementById('subscribe-turnstile-container') &&
      !!siteKey &&
      typeof turnstile !== 'undefined' &&
      widgetId != null;
    if (turnstilePresent && !token) {
      showError('Complete the verification checkbox.');
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
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, status: res.status, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          showError((result.data && result.data.error) || 'Could not subscribe. Try again.');
          resetTurnstile();
          return;
        }
        showStatus((result.data && result.data.message) || 'Check your inbox to confirm.');
        formEl.reset();
        // Restore default list checkbox after reset
        var def = (section.dataset && section.dataset.defaultList) || 'posts';
        var box = formEl.querySelector('input[name="lists"][value="' + def + '"]');
        if (box) box.checked = true;
        resetTurnstile();
      })
      .catch(function () {
        showError('Could not reach the server. Try again.');
        resetTurnstile();
      })
      .finally(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  });
})();
