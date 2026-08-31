export function relocateCommentUrl(url) {
  if (typeof url !== 'string' || !url) return '';
  var t = url.trim().replace(/\/+/g, '/');
  if (!t.startsWith('/')) return '';
  if (t !== '/' && !t.endsWith('/')) t += '/';
  if (t === '/posts/gradys-how-to-use-this-blog/') {
    return '/gradys-tour/how-to-use-this-blog/';
  }
  if (t.indexOf('/posts/gradys-tour/') === 0) {
    return '/gradys-tour/' + t.slice('/posts/gradys-tour/'.length);
  }
  return t;
}

function commentTime(c) {
  var raw = c && c.created_at;
  if (!raw) return 0;
  var s = String(raw).trim();
  if (!s) return 0;
  if (!(/Z$/i.test(s) || /[+-]\d{2}:\d{2}$/.test(s))) s = s.replace(' ', 'T') + 'Z';
  else s = s.replace(' ', 'T');
  var t = Date.parse(s);
  return isNaN(t) ? 0 : t;
}

function formatPostedAt(raw) {
  var t = commentTime({ created_at: raw });
  if (!t) return raw || '';
  return new Date(t).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  });
}

function lookupPost(url, postIndex) {
  var live = relocateCommentUrl(url) || url || '';
  var info = postIndex && (postIndex[live] || postIndex[url]);
  if (info) {
    return {
      url: live,
      title: info.title || live,
      author: info.author || 'Other',
      slug: info.slug || ''
    };
  }
  return { url: live, title: live || '(no url)', author: 'Other', slug: '' };
}

export function organizeAdminComments(comments, postIndex, authorSlug) {
  var byAuthor = {};
  (comments || []).forEach(function (c) {
    var post = lookupPost(c.url, postIndex);
    if (authorSlug && post.slug !== authorSlug) return;
    var key = post.slug || '';
    if (!byAuthor[key]) {
      byAuthor[key] = { slug: key, name: post.author, posts: {}, latest: 0 };
    }
    var author = byAuthor[key];
    if (!author.posts[post.url]) {
      author.posts[post.url] = { url: post.url, title: post.title, comments: [], latest: 0 };
    }
    var group = author.posts[post.url];
    group.comments.push(c);
    var t = commentTime(c);
    if (t > group.latest) group.latest = t;
    if (t > author.latest) author.latest = t;
  });

  return Object.keys(byAuthor).map(function (key) {
    var a = byAuthor[key];
    var posts = Object.keys(a.posts).map(function (u) { return a.posts[u]; });
    posts.forEach(function (p) {
      p.comments.sort(function (x, y) { return commentTime(y) - commentTime(x); });
    });
    posts.sort(function (x, y) { return y.latest - x.latest; });
    var count = 0;
    posts.forEach(function (p) {
      count += p.comments.length;
      delete p.latest;
    });
    return { slug: a.slug, name: a.name, count: count, latest: a.latest, posts: posts };
  }).sort(function (a, b) {
    return b.latest - a.latest;
  }).map(function (a) {
    delete a.latest;
    return a;
  });
}

function readJson(id, fallback) {
  var el = document.getElementById(id);
  if (!el) return fallback;
  try {
    var parsed = JSON.parse(el.textContent || '');
    if (typeof parsed === 'string') parsed = JSON.parse(parsed);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return fallback;
    return parsed;
  } catch (_) {
    return fallback;
  }
}

function escapeHtml(s) {
  if (!s) return '';
  var div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function selectedAuthorSlug() {
  var checked = document.querySelector('input[name="admin-author-filter"]:checked');
  return checked ? String(checked.value || '') : '';
}

function appendCommentItem(ol, c) {
  var li = document.createElement('li');
  li.className = 'admin-comment-item';
  li.dataset.id = String(c.id);
  var view = document.createElement('div');
  view.className = 'admin-comment-view';
  var meta = document.createElement('div');
  meta.className = 'admin-comment-meta';
  var statusLabel = (c.status === 'pending') ? 'pending' : 'approved';
  var postedMs = commentTime(c);
  var createdIso = postedMs ? new Date(postedMs).toISOString() : (c.created_at || '');
  meta.innerHTML = '<span class="admin-comment-author">' + escapeHtml(c.author) + '</span> <time datetime="' + escapeHtml(createdIso) + '">' + escapeHtml(formatPostedAt(c.created_at)) + '</time> <span class="admin-comment-status admin-comment-status-' + statusLabel + '" aria-label="Status">' + escapeHtml(statusLabel) + '</span>';
  view.appendChild(meta);
  var body = document.createElement('div');
  body.className = 'admin-comment-body';
  body.textContent = c.body || '';
  view.appendChild(body);
  var actions = document.createElement('div');
  actions.className = 'admin-comment-actions';
  var editBtn = document.createElement('button');
  editBtn.type = 'button';
  editBtn.className = 'admin-comment-edit';
  editBtn.textContent = 'Edit';
  editBtn.setAttribute('aria-label', 'Edit this comment');
  editBtn.dataset.id = String(c.id);
  actions.appendChild(editBtn);
  var delBtn = document.createElement('button');
  delBtn.type = 'button';
  delBtn.className = 'admin-comment-delete';
  delBtn.textContent = 'Delete';
  delBtn.setAttribute('aria-label', 'Delete this comment');
  delBtn.dataset.id = String(c.id);
  actions.appendChild(delBtn);
  view.appendChild(actions);
  li.appendChild(view);
  var editForm = document.createElement('div');
  editForm.className = 'admin-comment-edit-form';
  editForm.hidden = true;
  editForm.setAttribute('aria-label', 'Edit comment');
  var authorLabel = document.createElement('label');
  authorLabel.htmlFor = 'admin-edit-author-' + c.id;
  authorLabel.textContent = 'Commenter';
  var authorInput = document.createElement('input');
  authorInput.type = 'text';
  authorInput.id = 'admin-edit-author-' + c.id;
  authorInput.className = 'admin-edit-author';
  authorInput.value = c.author || '';
  authorInput.maxLength = 200;
  authorInput.setAttribute('aria-label', 'Commenter name');
  var bodyLabel = document.createElement('label');
  bodyLabel.htmlFor = 'admin-edit-body-' + c.id;
  bodyLabel.textContent = 'Comment';
  var bodyTextarea = document.createElement('textarea');
  bodyTextarea.id = 'admin-edit-body-' + c.id;
  bodyTextarea.className = 'admin-edit-body';
  bodyTextarea.rows = 3;
  bodyTextarea.maxLength = 5000;
  bodyTextarea.value = c.body || '';
  bodyTextarea.setAttribute('aria-label', 'Comment text');
  var editActions = document.createElement('div');
  editActions.className = 'admin-comment-edit-actions';
  var saveBtn = document.createElement('button');
  saveBtn.type = 'button';
  saveBtn.className = 'admin-comment-save';
  saveBtn.textContent = 'Save';
  saveBtn.setAttribute('aria-label', 'Save changes');
  saveBtn.dataset.id = String(c.id);
  var cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.className = 'admin-comment-cancel';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.setAttribute('aria-label', 'Cancel editing');
  cancelBtn.dataset.id = String(c.id);
  editActions.appendChild(saveBtn);
  editActions.appendChild(cancelBtn);
  editForm.appendChild(authorLabel);
  editForm.appendChild(authorInput);
  editForm.appendChild(bodyLabel);
  editForm.appendChild(bodyTextarea);
  editForm.appendChild(editActions);
  li.appendChild(editForm);
  ol.appendChild(li);
}

export function initAdminComments() {
  if (typeof document === 'undefined') return;
  var STORAGE_KEY = 'comments_admin_secret';
  var secretForm = document.getElementById('admin-secret-form');
  var secretInput = document.getElementById('admin-secret-input');
  var secretSubmit = document.getElementById('admin-secret-submit');
  var secretError = document.getElementById('admin-secret-error');
  var adminContent = document.getElementById('admin-content');
  var adminLoading = document.getElementById('admin-loading');
  var adminList = document.getElementById('admin-list');
  var adminListError = document.getElementById('admin-list-error');
  var authorFilter = document.getElementById('admin-author-filter');
  if (!secretForm || !secretInput || !secretSubmit || !secretError || !adminContent || !adminLoading || !adminList || !adminListError) return;

  var postIndex = readJson('admin-post-index', {});
  var cachedComments = [];
  var listReady = false;

  function getSecret() { return sessionStorage.getItem(STORAGE_KEY); }
  function setSecret(s) { sessionStorage.setItem(STORAGE_KEY, s); }
  function clearSecret() { sessionStorage.removeItem(STORAGE_KEY); }

  function showSecretForm(msg) {
    clearSecret();
    secretForm.hidden = false;
    adminContent.hidden = true;
    secretError.textContent = msg || '';
    secretError.hidden = !msg;
    secretInput.focus();
  }

  function showContent() {
    secretForm.hidden = true;
    adminContent.hidden = false;
    secretError.hidden = true;
    adminContent.focus();
  }

  function renderComments(comments) {
    cachedComments = comments || [];
    adminList.innerHTML = '';
    adminListError.hidden = true;
    var grouped = organizeAdminComments(cachedComments, postIndex, selectedAuthorSlug());
    if (!cachedComments.length) {
      adminList.textContent = 'No comments yet.';
      return;
    }
    if (!grouped.length) {
      adminList.textContent = 'No comments for this writer.';
      return;
    }
    for (var a = 0; a < grouped.length; a++) {
      var author = grouped[a];
      var authorSection = document.createElement('section');
      authorSection.className = 'admin-author-group';
      authorSection.setAttribute('aria-labelledby', 'admin-author-' + a);
      var h3 = document.createElement('h3');
      h3.id = 'admin-author-' + a;
      h3.className = 'admin-author-heading';
      h3.textContent = author.name + ' (' + author.count + ')';
      authorSection.appendChild(h3);
      for (var p = 0; p < author.posts.length; p++) {
        var post = author.posts[p];
        var section = document.createElement('section');
        section.className = 'admin-url-group';
        var headingId = 'admin-url-' + a + '-' + p;
        section.setAttribute('aria-labelledby', headingId);
        var h4 = document.createElement('h4');
        h4.id = headingId;
        h4.className = 'admin-url-heading';
        var link = document.createElement('a');
        link.href = relocateCommentUrl(post.url) || post.url;
        link.textContent = post.title || post.url || '(no url)';
        link.rel = 'noopener noreferrer';
        h4.appendChild(link);
        section.appendChild(h4);
        var ol = document.createElement('ol');
        ol.className = 'admin-comment-list';
        for (var j = 0; j < post.comments.length; j++) appendCommentItem(ol, post.comments[j]);
        section.appendChild(ol);
        authorSection.appendChild(section);
      }
      adminList.appendChild(authorSection);
    }
  }

  function loadComments() {
    var secret = getSecret();
    if (!secret) { showSecretForm('Session expired.'); return; }
    adminLoading.hidden = false;
    adminList.innerHTML = '';
    adminListError.hidden = true;
    fetch('/api/comments', { headers: { Authorization: 'Bearer ' + secret } })
      .then(function (res) {
        if (!res.ok) {
          if (res.status === 403 || res.status === 401) {
            return res.json().then(function (b) {
              showSecretForm(b.error || 'Invalid or expired secret.');
              return null;
            }).catch(function () {
              showSecretForm('Invalid or expired secret.');
              return null;
            });
          }
          return res.json().then(function (b) { throw new Error(b.error || res.statusText); });
        }
        return res.json();
      })
      .then(function (data) {
        adminLoading.hidden = true;
        if (data) {
          listReady = true;
          renderComments(data);
        }
      })
      .catch(function (err) {
        adminLoading.hidden = true;
        adminListError.textContent = err.message || 'Failed to load comments.';
        adminListError.hidden = false;
      });
  }

  function toggleEdit(li) {
    var view = li.querySelector('.admin-comment-view');
    var form = li.querySelector('.admin-comment-edit-form');
    if (!view || !form) return;
    if (form.hidden) {
      view.hidden = true;
      form.hidden = false;
      var bodyInput = form.querySelector('.admin-edit-body');
      if (bodyInput) bodyInput.focus();
    } else {
      view.hidden = false;
      form.hidden = true;
    }
  }

  function doSave(id) {
    var secret = getSecret();
    if (!secret) { showSecretForm('Session expired.'); return; }
    var li = adminList.querySelector('.admin-comment-item[data-id="' + id + '"]');
    if (!li) return;
    var form = li.querySelector('.admin-comment-edit-form');
    if (!form) return;
    var authorInput = form.querySelector('.admin-edit-author');
    var bodyInput = form.querySelector('.admin-edit-body');
    var author = authorInput && authorInput.value ? authorInput.value.trim() : '';
    var text = bodyInput && bodyInput.value ? bodyInput.value.trim() : '';
    if (!text) {
      adminListError.textContent = 'Comment text is required.';
      adminListError.hidden = false;
      return;
    }
    fetch('/api/comments', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + secret },
      body: JSON.stringify({ id: parseInt(id, 10), author: author, text: text })
    })
      .then(function (res) {
        if (res.status === 403 || res.status === 401) {
          showSecretForm('Invalid or expired secret.');
          return;
        }
        if (!res.ok) {
          return res.json().then(function (b) { throw new Error(b.error || res.statusText); });
        }
        loadComments();
      })
      .catch(function (err) {
        adminListError.textContent = err.message || 'Failed to update comment.';
        adminListError.hidden = false;
      });
  }

  function doDelete(id) {
    var secret = getSecret();
    if (!secret) { showSecretForm('Session expired.'); return; }
    if (!confirm('Delete this comment? Replies (if any) will also be deleted.')) return;
    fetch('/api/comments', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + secret },
      body: JSON.stringify({ id: parseInt(id, 10) })
    })
      .then(function (res) {
        if (res.status === 403 || res.status === 401) {
          showSecretForm('Invalid or expired secret.');
          return;
        }
        if (res.status !== 204) {
          return res.json().then(function (b) { throw new Error(b.error || res.statusText); });
        }
        loadComments();
      })
      .catch(function (err) {
        adminListError.textContent = err.message || 'Failed to delete.';
        adminListError.hidden = false;
      });
  }

  secretSubmit.addEventListener('click', function () {
    var s = (secretInput.value || '').trim();
    if (!s) {
      secretError.textContent = 'Enter the password.';
      secretError.hidden = false;
      return;
    }
    setSecret(s);
    showContent();
    loadComments();
  });

  secretInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') secretSubmit.click();
  });

  if (authorFilter) {
    authorFilter.addEventListener('change', function () {
      if (!listReady) return;
      renderComments(cachedComments);
    });
  }

  adminList.addEventListener('click', function (e) {
    var editBtn = e.target.closest('.admin-comment-edit');
    if (editBtn && editBtn.dataset.id) {
      var li = editBtn.closest('.admin-comment-item');
      if (li) toggleEdit(li);
      return;
    }
    var saveBtn = e.target.closest('.admin-comment-save');
    if (saveBtn && saveBtn.dataset.id) { doSave(saveBtn.dataset.id); return; }
    var cancelBtn = e.target.closest('.admin-comment-cancel');
    if (cancelBtn && cancelBtn.dataset.id) {
      var li = cancelBtn.closest('.admin-comment-item');
      if (li) toggleEdit(li);
      return;
    }
    var delBtn = e.target.closest('.admin-comment-delete');
    if (delBtn && delBtn.dataset.id) doDelete(delBtn.dataset.id);
  });

  if (getSecret()) {
    showContent();
    loadComments();
  }
}

initAdminComments();
