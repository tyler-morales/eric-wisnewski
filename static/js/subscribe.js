(function () {
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

  function applyLists(formEl, lists) {
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
    if (!formEl) return;

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
          showStatus(
            statusEl,
            errorEl,
            (result.data && result.data.message) || 'Check your inbox to confirm.'
          );
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

  initSignup();
  initManage();
})();
