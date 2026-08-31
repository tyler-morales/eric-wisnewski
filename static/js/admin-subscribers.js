export const ADMIN_LIST_COLUMNS = [
  { id: 'posts', label: "Eric's blog" },
  { id: 'gradys-tour', label: "Grady's Tour" },
  { id: 'da-breakdown-w-tad', label: 'Da Breakdown w Tad' },
];

export function listStatusById(lists) {
  var byId = {};
  if (!Array.isArray(lists)) return byId;
  for (var i = 0; i < lists.length; i++) {
    var row = lists[i];
    if (row && typeof row.list === 'string' && row.list) {
      byId[row.list] = row.status || '';
    }
  }
  return byId;
}

export function subscriberTableRows(people, columns) {
  columns = columns || ADMIN_LIST_COLUMNS;
  if (!Array.isArray(people)) return [];
  var out = [];
  for (var i = 0; i < people.length; i++) {
    var person = people[i];
    if (!person || typeof person.email !== 'string' || !person.email) continue;
    var byId = listStatusById(person.lists);
    var cells = [];
    for (var j = 0; j < columns.length; j++) {
      var col = columns[j];
      cells.push({ id: col.id, label: col.label, status: byId[col.id] || '' });
    }
    out.push({ email: person.email, cells: cells });
  }
  return out;
}

export function summarizeSubscribers(people, columns) {
  columns = columns || ADMIN_LIST_COLUMNS;
  var rows = Array.isArray(people) ? people : [];
  var confirmed = {};
  var i;
  var j;
  for (i = 0; i < columns.length; i++) confirmed[columns[i].id] = 0;
  for (i = 0; i < rows.length; i++) {
    var byId = listStatusById(rows[i] && rows[i].lists);
    for (j = 0; j < columns.length; j++) {
      if (byId[columns[j].id] === 'confirmed') confirmed[columns[j].id] += 1;
    }
  }
  var who = rows.length === 1 ? '1 person' : rows.length + ' people';
  var parts = [];
  for (i = 0; i < columns.length; i++) {
    parts.push(columns[i].label + ' ' + confirmed[columns[i].id]);
  }
  return who + '. Confirmed: ' + parts.join(', ') + '.';
}

function statusClass(status) {
  if (status === 'confirmed') return 'admin-comment-status-confirmed';
  if (status === 'pending') return 'admin-comment-status-pending';
  if (status === 'unsubscribed') return 'admin-comment-status-unsubscribed';
  return '';
}

export function initAdminSubscribers() {
  if (typeof document === 'undefined') return;
  var STORAGE_KEY = 'comments_admin_secret';
  var secretForm = document.getElementById('admin-secret-form');
  var secretInput = document.getElementById('admin-secret-input');
  var secretSubmit = document.getElementById('admin-secret-submit');
  var secretError = document.getElementById('admin-secret-error');
  var adminContent = document.getElementById('admin-content');
  var adminLoading = document.getElementById('admin-loading');
  var adminSummary = document.getElementById('admin-summary');
  var adminList = document.getElementById('admin-list');
  var adminListError = document.getElementById('admin-list-error');
  if (!secretForm || !secretInput || !secretSubmit || !secretError || !adminContent || !adminLoading || !adminSummary || !adminList || !adminListError) return;

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

  function renderStatusCell(td, status) {
    if (!status) {
      var hidden = document.createElement('span');
      hidden.className = 'visually-hidden';
      hidden.textContent = 'Not subscribed';
      var dash = document.createElement('span');
      dash.className = 'admin-subscriber-empty';
      dash.setAttribute('aria-hidden', 'true');
      dash.textContent = '—';
      td.appendChild(hidden);
      td.appendChild(dash);
      return;
    }
    var badge = document.createElement('span');
    badge.className = 'admin-comment-status ' + statusClass(status);
    badge.textContent = status;
    td.appendChild(badge);
  }

  function renderSubscribers(people) {
    adminList.innerHTML = '';
    adminListError.hidden = true;
    adminSummary.hidden = true;
    var rows = subscriberTableRows(people);
    if (!rows.length) {
      adminList.textContent = 'No subscribers yet.';
      return;
    }
    adminSummary.textContent = summarizeSubscribers(people);
    adminSummary.hidden = false;
    var wrap = document.createElement('div');
    wrap.className = 'admin-subscriber-table-wrap';
    var table = document.createElement('table');
    table.className = 'admin-subscriber-table';
    var caption = document.createElement('caption');
    caption.className = 'visually-hidden';
    caption.textContent = 'Newsletter subscribers';
    table.appendChild(caption);
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    var emailTh = document.createElement('th');
    emailTh.scope = 'col';
    emailTh.textContent = 'Email';
    headRow.appendChild(emailTh);
    for (var c = 0; c < ADMIN_LIST_COLUMNS.length; c++) {
      var th = document.createElement('th');
      th.scope = 'col';
      th.textContent = ADMIN_LIST_COLUMNS[c].label;
      headRow.appendChild(th);
    }
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = document.createElement('tbody');
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var tr = document.createElement('tr');
      var emailTd = document.createElement('td');
      emailTd.className = 'admin-subscriber-email';
      var mail = document.createElement('a');
      mail.href = 'mailto:' + row.email;
      mail.textContent = row.email;
      emailTd.appendChild(mail);
      tr.appendChild(emailTd);
      for (var j = 0; j < row.cells.length; j++) {
        var td = document.createElement('td');
        renderStatusCell(td, row.cells[j].status);
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    wrap.appendChild(table);
    adminList.appendChild(wrap);
  }

  function loadSubscribers() {
    var secret = getSecret();
    if (!secret) { showSecretForm('Session expired.'); return; }
    adminLoading.hidden = false;
    adminList.innerHTML = '';
    adminListError.hidden = true;
    adminSummary.hidden = true;
    fetch('/api/subscribe', { headers: { Authorization: 'Bearer ' + secret } })
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
        if (data) renderSubscribers(data.subscribers || []);
      })
      .catch(function (err) {
        adminLoading.hidden = true;
        adminListError.textContent = err.message || 'Failed to load subscribers.';
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
    loadSubscribers();
  });

  secretInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') secretSubmit.click();
  });

  if (getSecret()) {
    showContent();
    loadSubscribers();
  }
}

initAdminSubscribers();
