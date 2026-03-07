(function () {
  var section = document.getElementById('comments');
  if (!section) return;

  var listEl = section.querySelector('.comments-list');
  var formEl = section.querySelector('.comments-form');
  var errorEl = section.querySelector('.comments-error');
  if (!listEl || !formEl) return;

  var STORAGE_KEY = 'comment_tokens';
  var AUTHOR_KEY = 'comment_author';
  var EMAIL_KEY = 'comment_email';

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

  function getInitial(author) {
    if (!author || typeof author !== 'string') return '?';
    var first = author.trim().charAt(0);
    return first ? first.toUpperCase() : '?';
  }

  var AVATAR_COLORS = [
    '#2563eb', '#059669', '#7c3aed', '#dc2626', '#ea580c', '#0891b2'
  ];
  function getAvatarColor(author) {
    var c = (author && author.trim().charAt(0)) || '?';
    var i = c.charCodeAt(0) % AVATAR_COLORS.length;
    return AVATAR_COLORS[i];
  }

  function timeAgo(iso) {
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      var now = Date.now();
      var diff = Math.floor((now - d.getTime()) / 1000);
      if (diff < 60) return 'just now';
      if (diff < 3600) return Math.floor(diff / 60) + ' minute' + (diff >= 120 ? 's' : '') + ' ago';
      if (diff < 86400) return Math.floor(diff / 3600) + ' hour' + (diff >= 7200 ? 's' : '') + ' ago';
      if (diff < 604800) return Math.floor(diff / 86400) + ' day' + (diff >= 172800 ? 's' : '') + ' ago';
      if (diff < 2592000) return Math.floor(diff / 604800) + ' week' + (diff >= 1209600 ? 's' : '') + ' ago';
      return formatDate(iso);
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

  function getTokens() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (_) {
      return {};
    }
  }

  function saveToken(id, token) {
    var tokens = getTokens();
    tokens[String(id)] = token;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } catch (_) {}
  }

  function saveAuthorEmail(author, email) {
    try {
      if (author) localStorage.setItem(AUTHOR_KEY, author);
      if (email != null) localStorage.setItem(EMAIL_KEY, email);
    } catch (_) {}
  }

  function getAuthorEmail() {
    var author = null;
    var email = null;
    try {
      author = localStorage.getItem(AUTHOR_KEY);
      email = localStorage.getItem(EMAIL_KEY);
    } catch (_) {}
    return { author: author || '', email: email || '' };
  }

  function getToken(id) {
    return getTokens()[String(id)];
  }

  function removeToken(id) {
    var tokens = getTokens();
    delete tokens[String(id)];
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } catch (_) {}
  }

  function parseJson(r) {
    var ct = r.headers.get('Content-Type') || '';
    if (!ct.includes('application/json')) {
      throw new Error('Comments service unavailable. Is the comments API running?');
    }
    return r.json();
  }

  function buildThread(comments) {
    var top = [];
    var byParent = {};
    (comments || []).forEach(function (c) {
      var pid = c.parent_id;
      if (pid == null) {
        top.push(c);
      } else {
        if (!byParent[pid]) byParent[pid] = [];
        byParent[pid].push(c);
      }
    });
    top.sort(function (a, b) {
      return new Date(a.created_at) - new Date(b.created_at);
    });
    Object.keys(byParent).forEach(function (pid) {
      byParent[pid].sort(function (a, b) {
        return new Date(a.created_at) - new Date(b.created_at);
      });
    });
    return { top: top, byParent: byParent };
  }

  function closeOpenReplyForm() {
    var open = section.querySelector('.comments-reply-form');
    if (open) open.remove();
  }

  function closeOpenEdit() {
    var open = section.querySelector('.comment-item .comment-edit-active');
    if (open) {
      var item = open.closest('.comment-item');
      var body = item.querySelector('.comment-body');
      var current = item.getAttribute('data-body');
      if (body && current != null) {
        body.textContent = current;
        body.hidden = false;
      }
      open.remove();
    }
  }

  function renderReplyForm(parentId, parentAuthor, onCancel) {
    closeOpenReplyForm();
    var form = document.createElement('form');
    form.className = 'comments-form comments-reply-form';
    form.setAttribute('aria-label', 'Reply to ' + parentAuthor);
    form.innerHTML =
      '<label for="comment-reply-text">Reply</label>' +
      '<textarea id="comment-reply-text" name="text" required rows="2" maxlength="5000" placeholder="Write a reply…"></textarea>' +
      '<div class="comments-form-actions">' +
      '<button type="button" class="comment-cancel">Cancel</button>' +
      '<button type="submit">Post reply</button>' +
      '</div>';
    form.querySelector('.comment-cancel').addEventListener('click', function () {
      closeOpenReplyForm();
      if (onCancel) onCancel();
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clearError();
      var text = (form.querySelector('[name="text"]') || {}).value;
      if (!text || !text.trim()) {
        showError('Please enter a reply.');
        return;
      }
      var authorInput = formEl.querySelector('[name="author"]');
      var emailInput = formEl.querySelector('[name="email"]');
      var author = (authorInput && authorInput.value && authorInput.value.trim()) || '';
      var email = (emailInput && emailInput.value && emailInput.value.trim()) || '';
      if (!author) {
        var stored = getAuthorEmail();
        author = stored.author;
        email = email || stored.email;
      }
      if (!author) {
        showError('Enter your name in the form below, then reply.');
        return;
      }
      var payload = { url: normalizeUrl(), author: author.trim(), text: text.trim(), parent_id: parentId };
      if (email) payload.email = email.trim();
      fetch('/api/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(function (r) {
          return parseJson(r).then(function (data) {
            if (!r.ok) throw new Error(data.error || 'Failed to post reply');
            return data;
          });
        })
        .then(function (data) {
          if (data.edit_token) saveToken(data.id, data.edit_token);
          saveAuthorEmail(author, email);
          closeOpenReplyForm();
          loadComments();
          listEl.focus();
        })
        .catch(function (err) {
          showError(err.message || 'Could not post reply.');
        });
    });
    return form;
  }

  function renderComment(c, isReply, thread, parentAuthor) {
    var li = document.createElement('li');
    li.className = 'comment-item' + (isReply ? ' comment-reply' : '');
    li.setAttribute('data-comment-id', c.id);
    li.setAttribute('data-body', c.body);

    var avatar = document.createElement('div');
    avatar.className = 'comment-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.style.backgroundColor = getAvatarColor(c.author);
    avatar.textContent = getInitial(c.author);
    li.appendChild(avatar);

    var content = document.createElement('div');
    content.className = 'comment-content';

    var meta = document.createElement('div');
    meta.className = 'comment-meta';
    var metaParts = [
      '<cite class="comment-author">' + escapeHtml(c.author) + '</cite>'
    ];
    if (isReply && parentAuthor) {
      metaParts.push(' <span class="comment-reply-to">→ ' + escapeHtml(parentAuthor) + '</span>');
    }
    metaParts.push(' <time class="comment-date" datetime="' + escapeHtml(c.created_at) + '">' + timeAgo(c.created_at) + '</time>');
    meta.innerHTML = metaParts.join('');
    content.appendChild(meta);

    var bodyWrap = document.createElement('div');
    bodyWrap.className = 'comment-body-wrap';
    var bodyEl = document.createElement('div');
    bodyEl.className = 'comment-body';
    bodyEl.textContent = c.body;
    bodyWrap.appendChild(bodyEl);
    content.appendChild(bodyWrap);

    var actions = document.createElement('div');
    actions.className = 'comment-actions';
    var canEdit = !!getToken(c.id);

    function appendAction(btn) {
      if (actions.childNodes.length) actions.appendChild(document.createTextNode(' · '));
      actions.appendChild(btn);
    }

    if (!isReply) {
      var replyBtn = document.createElement('button');
      replyBtn.type = 'button';
      replyBtn.className = 'comment-action comment-reply-btn';
      replyBtn.textContent = 'Reply';
      replyBtn.setAttribute('aria-label', 'Reply to ' + escapeHtml(c.author));
      replyBtn.addEventListener('click', function () {
        closeOpenEdit();
        var container = li.querySelector('.comment-replies') || (function () {
          var div = document.createElement('div');
          div.className = 'comment-replies';
          li.appendChild(div);
          return div;
        })();
        var form = renderReplyForm(c.id, c.author, function () {});
        container.insertBefore(form, container.firstChild);
        var firstInput = form.querySelector('input, textarea');
        if (firstInput) firstInput.focus();
      });
      appendAction(replyBtn);
    }
    if (canEdit) {
      var editBtn = document.createElement('button');
      editBtn.type = 'button';
      editBtn.className = 'comment-action comment-edit-btn';
      editBtn.textContent = 'Edit';
      editBtn.setAttribute('aria-label', 'Edit your comment');
      editBtn.addEventListener('click', function () {
        closeOpenReplyForm();
        closeOpenEdit();
        bodyEl.hidden = true;
        var wrap = document.createElement('div');
        wrap.className = 'comment-edit-active';
        var textarea = document.createElement('textarea');
        textarea.rows = 3;
        textarea.maxLength = 5000;
        textarea.value = c.body;
        textarea.setAttribute('aria-label', 'Edit comment text');
        var btnWrap = document.createElement('div');
        btnWrap.className = 'comment-edit-actions';
        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', function () {
          bodyEl.hidden = false;
          wrap.remove();
        });
        var saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.textContent = 'Save';
        saveBtn.addEventListener('click', function () {
          var newText = textarea.value.trim();
          if (!newText) return;
          var token = getToken(c.id);
          if (!token) {
            showError('Session expired. Refresh to edit.');
            return;
          }
          fetch('/api/comments', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: c.id, text: newText, edit_token: token })
          })
            .then(function (r) {
              return parseJson(r).then(function (data) {
                if (!r.ok) throw new Error(data.error || 'Failed to update');
                return data;
              });
            })
            .then(function () {
              li.setAttribute('data-body', newText);
              bodyEl.textContent = newText;
              bodyEl.hidden = false;
              wrap.remove();
              loadComments();
            })
            .catch(function (err) {
              showError(err.message || 'Could not update comment.');
            });
        });
        btnWrap.appendChild(cancelBtn);
        btnWrap.appendChild(saveBtn);
        wrap.appendChild(textarea);
        wrap.appendChild(btnWrap);
        bodyWrap.appendChild(wrap);
        textarea.focus();
      });
      appendAction(editBtn);

      var delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'comment-action comment-delete-btn';
      delBtn.textContent = 'Delete';
      delBtn.setAttribute('aria-label', 'Delete your comment');
      delBtn.addEventListener('click', function () {
        if (!confirm('Delete this comment? This cannot be undone.')) return;
        var token = getToken(c.id);
        if (!token) {
          showError('Session expired. Refresh the page.');
          return;
        }
        fetch('/api/comments?id=' + encodeURIComponent(c.id) + '&edit_token=' + encodeURIComponent(token), {
          method: 'DELETE'
        })
          .then(function (r) {
            if (!r.ok) return r.json().then(function (data) { throw new Error(data.error || 'Delete failed'); });
          })
          .then(function () {
            removeToken(c.id);
            loadComments();
          })
          .catch(function (err) {
            showError(err.message || 'Could not delete comment.');
          });
      });
      appendAction(delBtn);
    }
    content.appendChild(actions);
    li.appendChild(content);

    if (!isReply && thread && thread.byParent[c.id] && thread.byParent[c.id].length) {
      var repliesDiv = document.createElement('div');
      repliesDiv.className = 'comment-replies';
      thread.byParent[c.id].forEach(function (r) {
        repliesDiv.appendChild(renderComment(r, true, null, c.author));
      });
      li.appendChild(repliesDiv);
    }

    return li;
  }

  function renderComments(comments) {
    closeOpenReplyForm();
    closeOpenEdit();
    var countEl = section.querySelector('.comments-count');
    if (countEl) countEl.textContent = (comments && comments.length) ? String(comments.length) : '0';
    listEl.innerHTML = '';
    if (!comments || comments.length === 0) {
      listEl.innerHTML = '<li class="comments-empty">No comments yet.</li>';
      return;
    }
    var thread = buildThread(comments);
    thread.top.forEach(function (c) {
      listEl.appendChild(renderComment(c, false, thread));
    });
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
      .then(function (data) {
        if (data.edit_token) saveToken(data.id, data.edit_token);
        saveAuthorEmail(author, email);
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
