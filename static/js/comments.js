export var AUTHOR_KEY = 'comment_author';
export var EMAIL_KEY = 'comment_email';
export var EMAIL_REPLY_HINT = "We'll email you if someone replies — after you confirm that address.";

export function readIdentity(storage) {
  var author = '';
  var email = '';
  try {
    if (storage) {
      author = (storage.getItem(AUTHOR_KEY) || '').trim();
      email = (storage.getItem(EMAIL_KEY) || '').trim();
    }
  } catch (_) { }
  return { author: author, email: email };
}

export function writeIdentity(storage, author, email) {
  try {
    if (!storage) return;
    var name = (author || '').trim();
    if (name) storage.setItem(AUTHOR_KEY, name);
    if (email != null) storage.setItem(EMAIL_KEY, String(email).trim());
  } catch (_) { }
}

export function mergeIdentity(formAuthor, formEmail, stored) {
  var fromStore = stored || { author: '', email: '' };
  return {
    author: (formAuthor || '').trim() || fromStore.author || '',
    email: (formEmail || '').trim() || fromStore.email || ''
  };
}

export function buildThread(comments) {
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

function initComments() {
  if (typeof document === 'undefined') return;

  var section = document.getElementById('comments');
  if (!section) return;

  var listEl = section.querySelector('.comments-list');
  var formEl = section.querySelector('.comments-form');
  var errorEl = section.querySelector('.comments-error');
  if (!listEl || !formEl) return;

  var siteKey = (section.dataset && section.dataset.turnstileSitekey) ? section.dataset.turnstileSitekey.trim() : '';
  var mainWidgetId = null;
  var replyWidgetId = null;

  var STORAGE_KEY = 'comment_tokens';

  function identityStorage() {
    try {
      return localStorage;
    } catch (_) {
      return null;
    }
  }

  function normalizeUrl() {
    var fromPage = section.dataset && section.dataset.pageUrl;
    if (fromPage) {
      return fromPage.replace(/\/?$/, '/');
    }
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
    } catch (_) { }
  }

  function getToken(id) {
    return getTokens()[String(id)];
  }

  function removeToken(id) {
    var tokens = getTokens();
    delete tokens[String(id)];
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } catch (_) { }
  }

  function identityFromForm(form) {
    var authorInput = form && form.querySelector('[name="author"]');
    var emailInput = form && form.querySelector('[name="email"]');
    return mergeIdentity(
      authorInput && authorInput.value,
      emailInput && emailInput.value,
      readIdentity(identityStorage())
    );
  }

  function fillIdentityFields(root, identity) {
    if (!root || !identity) return;
    var authorInputs = root.querySelectorAll('[name="author"]');
    var emailInputs = root.querySelectorAll('[name="email"]');
    var i;
    for (i = 0; i < authorInputs.length; i++) {
      if (identity.author) authorInputs[i].value = identity.author;
    }
    for (i = 0; i < emailInputs.length; i++) {
      if (identity.email != null) emailInputs[i].value = identity.email;
    }
    var names = root.querySelectorAll('.comments-identity-name');
    for (i = 0; i < names.length; i++) {
      names[i].textContent = identity.author || '';
    }
  }

  function setIdentityCollapsed(form, collapsed) {
    if (!form) return;
    var fields = form.querySelector('.comments-identity-fields');
    var status = form.querySelector('.comments-identity-status');
    var changeBtn = form.querySelector('.comment-identity-change');
    var authorInput = form.querySelector('[name="author"]');
    var identity = identityFromForm(form);
    if (identity.author) fillIdentityFields(form, identity);
    if (!fields) return;
    var hideFields = !!(collapsed && identity.author && identity.email);
    fields.hidden = hideFields;
    if (status) status.hidden = !identity.author;
    if (authorInput) authorInput.required = !hideFields;
    if (changeBtn) changeBtn.setAttribute('aria-expanded', hideFields ? 'false' : 'true');
  }

  function persistIdentityFromForm(form) {
    var identity = identityFromForm(form);
    if (!identity.author) return identity;
    writeIdentity(identityStorage(), identity.author, identity.email);
    fillIdentityFields(section, identity);
    return identity;
  }

  function parseJson(r) {
    var ct = r.headers.get('Content-Type') || '';
    if (!ct.includes('application/json')) {
      throw new Error('Comments service unavailable. Is the comments API running?');
    }
    return r.json();
  }

  function destroyReplyTurnstile() {
    if (replyWidgetId != null && typeof turnstile !== 'undefined') {
      try {
        turnstile.remove(replyWidgetId);
      } catch (_) { }
    }
    replyWidgetId = null;
  }

  function mountReplyTurnstile(container) {
    destroyReplyTurnstile();
    if (!siteKey || typeof turnstile === 'undefined' || !container) return;
    try {
      replyWidgetId = turnstile.render(container, { sitekey: siteKey });
    } catch (_) { }
  }

  function closeOpenReplyForm() {
    destroyReplyTurnstile();
    var open = section.querySelector('.comments-reply-form');
    if (open) open.remove();
    var expanded = section.querySelectorAll('.comment-reply-btn[aria-expanded="true"]');
    for (var i = 0; i < expanded.length; i++) {
      expanded[i].setAttribute('aria-expanded', 'false');
    }
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

  function turnstileToken(widgetId) {
    var hasWidget = siteKey && typeof turnstile !== 'undefined' && widgetId != null;
    if (!hasWidget) return { hasWidget: false, token: '' };
    var token = turnstile.getResponse(widgetId);
    return { hasWidget: true, token: token || '' };
  }

  function renderReplyForm(parentId, parentAuthor, onCancel) {
    closeOpenReplyForm();
    var form = document.createElement('form');
    form.className = 'comments-form comments-reply-form';
    form.setAttribute('aria-label', 'Reply to ' + parentAuthor);
    form.innerHTML =
      '<p class="comments-reply-heading">Reply to ' + escapeHtml(parentAuthor) + '</p>' +
      '<label for="comment-reply-text">Reply</label>' +
      '<textarea id="comment-reply-text" name="text" required rows="2" maxlength="5000" placeholder="Write a reply…"></textarea>' +
      '<p class="comments-identity-status" hidden>' +
      'Replying as <strong class="comments-identity-name"></strong> ' +
      '<button type="button" class="comment-identity-change" aria-expanded="false" aria-controls="comments-reply-identity-fields">Change</button>' +
      '</p>' +
      '<div id="comments-reply-identity-fields" class="comments-identity-fields">' +
      '<label for="comment-reply-author">Name</label>' +
      '<input id="comment-reply-author" name="author" type="text" required autocomplete="name" maxlength="200" placeholder="Your name">' +
      '<label for="comment-reply-email">Email <span class="comments-optional">(optional)</span></label>' +
      '<input id="comment-reply-email" name="email" type="email" autocomplete="email" placeholder="you@example.com" aria-describedby="comment-reply-email-hint">' +
      '<p id="comment-reply-email-hint" class="comments-email-hint">' + EMAIL_REPLY_HINT + '</p>' +
      '</div>' +
      '<div class="comments-turnstile comments-reply-turnstile" role="group" aria-label="Verification"></div>' +
      '<div class="comments-form-actions">' +
      '<button type="button" class="comment-cancel">Cancel</button>' +
      '<button type="submit">Reply</button>' +
      '</div>';

    var known = identityFromForm(formEl);
    fillIdentityFields(form, known);
    setIdentityCollapsed(form, !!known.author);

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
      var identity = persistIdentityFromForm(form);
      if (!identity.author) {
        showError('Add your name to reply.');
        setIdentityCollapsed(form, false);
        var nameInput = form.querySelector('[name="author"]');
        if (nameInput) nameInput.focus();
        return;
      }
      var widget = turnstileToken(replyWidgetId != null ? replyWidgetId : mainWidgetId);
      if (widget.hasWidget && !widget.token) {
        showError('Please complete the verification.');
        return;
      }
      var payload = {
        url: normalizeUrl(),
        author: identity.author,
        text: text.trim(),
        parent_id: parentId
      };
      if (identity.email) payload.email = identity.email;
      if (widget.hasWidget) payload.cf_turnstile_response = widget.token;
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
          writeIdentity(identityStorage(), identity.author, identity.email);
          fillIdentityFields(formEl, identity);
          setIdentityCollapsed(formEl, true);
          if (widget.hasWidget && typeof turnstile !== 'undefined') {
            var resetId = replyWidgetId != null ? replyWidgetId : mainWidgetId;
            turnstile.reset(resetId);
          }
          closeOpenReplyForm();
          loadComments();
          listEl.focus();
        })
        .catch(function (err) {
          showError(err.message || 'Could not post reply.');
        });
    });
    return { form: form };
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

    var replyBtn = document.createElement('button');
    replyBtn.type = 'button';
    replyBtn.className = 'comment-action comment-reply-btn';
    replyBtn.textContent = 'Reply';
    replyBtn.setAttribute('aria-label', 'Reply to ' + c.author);
    replyBtn.setAttribute('aria-expanded', 'false');
    replyBtn.addEventListener('click', function () {
      var openOnThis = content.querySelector(':scope > .comments-reply-form');
      if (openOnThis) {
        closeOpenReplyForm();
        return;
      }
      closeOpenEdit();
      var result = renderReplyForm(c.id, c.author, function () { });
      content.appendChild(result.form);
      mountReplyTurnstile(result.form.querySelector('.comments-reply-turnstile'));
      replyBtn.setAttribute('aria-expanded', 'true');
      var identity = identityFromForm(result.form);
      var firstInput = (!identity.author && result.form.querySelector('[name="author"]'))
        || result.form.querySelector('textarea');
      if (firstInput) firstInput.focus();
    });
    appendAction(replyBtn);
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
        var nameLabel = document.createElement('label');
        nameLabel.htmlFor = 'comment-edit-author-' + c.id;
        nameLabel.textContent = 'Display name';
        var nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.id = 'comment-edit-author-' + c.id;
        nameInput.className = 'comment-edit-author';
        nameInput.maxLength = 200;
        nameInput.value = c.author || '';
        nameInput.setAttribute('aria-label', 'Your display name (updates on all your comments if you used the same email)');
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
          var newAuthor = (nameInput.value && nameInput.value.trim()) || null;
          var payload = { id: c.id, text: newText, edit_token: token };
          if (newAuthor !== null) payload.author = newAuthor.trim();
          fetch('/api/comments', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          })
            .then(function (r) {
              return parseJson(r).then(function (data) {
                if (!r.ok) throw new Error(data.error || 'Failed to update');
                return data;
              });
            })
            .then(function () {
              if (newAuthor) {
                var stored = readIdentity(identityStorage());
                writeIdentity(identityStorage(), newAuthor, stored.email);
                fillIdentityFields(section, { author: newAuthor, email: stored.email });
                setIdentityCollapsed(formEl, true);
              }
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
        wrap.appendChild(nameLabel);
        wrap.appendChild(nameInput);
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
        fetch('/api/comments', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: c.id, edit_token: token })
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

    if (thread && thread.byParent[c.id] && thread.byParent[c.id].length) {
      var repliesList = document.createElement('ul');
      repliesList.className = 'comment-replies';
      repliesList.setAttribute('role', 'list');
      repliesList.setAttribute('aria-label', 'Replies to ' + c.author);
      thread.byParent[c.id].forEach(function (r) {
        repliesList.appendChild(renderComment(r, true, thread, c.author));
      });
      li.appendChild(repliesList);
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

  function showLoadError(msg) {
    listEl.innerHTML = '<li class="comments-error-state" role="alert">' + escapeHtml(msg || 'Could not load comments.') + '</li>';
    showError(msg || 'Could not load comments.');
  }

  function loadComments() {
    var url = normalizeUrl();
    var fetchUrl = '/api/comments?url=' + encodeURIComponent(url);
    fetch(fetchUrl)
      .then(function (r) {
        if (!r.ok) throw new Error('Failed to load comments');
        return parseJson(r);
      })
      .then(renderComments)
      .catch(function (err) {
        showLoadError(err.message || 'Could not load comments. Check that the comments API is running.');
      });
  }

  formEl.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();
    var textInput = formEl.querySelector('[name="text"]');
    var text = textInput && textInput.value ? textInput.value.trim() : '';
    var identity = persistIdentityFromForm(formEl);

    if (!identity.author || !text) {
      showError('Please fill in your name and comment.');
      if (!identity.author) {
        setIdentityCollapsed(formEl, false);
        var nameInput = formEl.querySelector('[name="author"]');
        if (nameInput) nameInput.focus();
      }
      return;
    }
    var widget = turnstileToken(mainWidgetId);
    if (widget.hasWidget && !widget.token) {
      showError('Please complete the verification.');
      return;
    }

    var payload = { url: normalizeUrl(), author: identity.author, text: text };
    if (identity.email) payload.email = identity.email;
    if (widget.hasWidget) payload.cf_turnstile_response = widget.token;

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
        writeIdentity(identityStorage(), identity.author, identity.email);
        fillIdentityFields(formEl, identity);
        setIdentityCollapsed(formEl, true);
        textInput.value = '';
        if (widget.hasWidget) turnstile.reset(mainWidgetId);
        loadComments();
        listEl.focus();
      })
      .catch(function (err) {
        showError(err.message || 'Could not post comment.');
      });
  });

  section.addEventListener('click', function (e) {
    var btn = e.target.closest('.comment-identity-change');
    if (!btn || !section.contains(btn)) return;
    var form = btn.closest('form');
    if (!form) return;
    setIdentityCollapsed(form, false);
    var nameInput = form.querySelector('[name="author"]');
    if (nameInput) nameInput.focus();
  });

  section.addEventListener('change', function (e) {
    var t = e.target;
    if (!t || (t.name !== 'author' && t.name !== 'email')) return;
    if (!section.contains(t)) return;
    var form = t.closest('form');
    if (!form) return;
    persistIdentityFromForm(form);
  });

  var stored = readIdentity(identityStorage());
  fillIdentityFields(formEl, stored);
  setIdentityCollapsed(formEl, !!stored.author);

  try {
    if (siteKey && typeof turnstile !== 'undefined') {
      var container = section.querySelector('#comments-turnstile-container');
      if (container) {
        turnstile.ready(function () {
          mainWidgetId = turnstile.render(container, { sitekey: siteKey });
        });
      }
    }
  } catch (_) { }

  loadComments();
}

initComments();
