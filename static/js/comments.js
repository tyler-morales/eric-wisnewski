(function () {
  var section = document.getElementById('comments');
  if (!section) return;

  var listEl = section.querySelector('.comments-list');
  var formEl = section.querySelector('.comments-form');
  var errorEl = section.querySelector('.comments-error');
  if (!listEl || !formEl) return;

  function normalizeUrl() {
    return location.pathname.replace(/\/?$/, '/');
  }

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function formatDate(iso) {
    try {
      var d = new Date(iso);
      return isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch (_) {
      return iso;
    }
  }

  function showError(msg) {
    if (!errorEl) return;
    errorEl.textContent = msg;
    errorEl.hidden = false;
  }

  function clearError() {
    if (errorEl) {
      errorEl.textContent = '';
      errorEl.hidden = true;
    }
  }

  function renderComments(comments) {
    listEl.innerHTML = '';
    if (!comments || comments.length === 0) {
      listEl.innerHTML = '<li class="comments-empty">No comments yet.</li>';
      return;
    }
    comments.forEach(function (c) {
      var li = document.createElement('li');
      li.className = 'comment-item';
      li.innerHTML =
        '<cite class="comment-author">' + escapeHtml(c.author) + '</cite> ' +
        '<time class="comment-date" datetime="' + escapeHtml(c.created_at) + '">' + formatDate(c.created_at) + '</time>' +
        '<div class="comment-body">' + escapeHtml(c.body) + '</div>';
      listEl.appendChild(li);
    });
  }

  function parseJson(r) {
    var ct = r.headers.get('Content-Type') || '';
    if (!ct.includes('application/json')) {
      throw new Error('Comments service unavailable. Is the comments API running?');
    }
    return r.json();
  }

  function loadComments() {
    var url = normalizeUrl();
    fetch('/api/comments?url=' + encodeURIComponent(url))
      .then(function (r) {
        if (!r.ok) throw new Error('Failed to load comments');
        return parseJson(r);
      })
      .then(renderComments)
      .catch(function (err) {
        showError(err.message || 'Could not load comments.');
      });
  }

  formEl.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();
    var authorInput = formEl.querySelector('[name="author"]');
    var emailInput = formEl.querySelector('[name="email"]');
    var textInput = formEl.querySelector('[name="text"]');
    var author = authorInput && authorInput.value ? authorInput.value.trim() : '';
    var email = emailInput && emailInput.value ? emailInput.value.trim() : '';
    var text = textInput && textInput.value ? textInput.value.trim() : '';

    if (!author || !text) {
      showError('Please fill in your name and comment.');
      return;
    }

    var payload = { url: normalizeUrl(), author: author, text: text };
    if (email) payload.email = email;

    fetch('/api/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) {
        return parseJson(r).then(function (data) {
          if (!r.ok) throw new Error(data.error || 'Failed to post comment');
          return data;
        });
      })
      .then(function () {
        authorInput.value = '';
        if (emailInput) emailInput.value = '';
        textInput.value = '';
        loadComments();
        listEl.focus();
      })
      .catch(function (err) {
        showError(err.message || 'Could not post comment.');
      });
  });

  loadComments();
})();
