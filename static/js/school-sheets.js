export function rowMatchesQuery(text, values, query) {
  var q = String(query || '').trim().toLowerCase();
  if (!q) return true;
  if (String(text || '').toLowerCase().indexOf(q) !== -1) return true;
  var list = values || [];
  for (var i = 0; i < list.length; i++) {
    if (String(list[i] || '').toLowerCase().indexOf(q) !== -1) return true;
  }
  return false;
}

(function () {
  if (typeof document === 'undefined') return;
  var table = document.getElementById('school-sheets-table');
  var searchInput = document.getElementById('school-sheets-search');
  var countEl = document.getElementById('school-sheets-count');
  if (!table || !searchInput) return;

  var tbody = table.querySelector('tbody');
  var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr.school-sheets-row'));
  var headerCells = table.querySelectorAll('thead th[data-sortable]');

  function updateCount(visible, total) {
    if (!countEl) return;
    countEl.textContent = total === 0 ? '' : visible + ' of ' + total + ' schools';
  }

  function filterRows() {
    var q = searchInput.value || '';
    var visible = 0;
    rows.forEach(function (row) {
      var values = Array.prototype.map.call(row.querySelectorAll('td[data-value]'), function (td) {
        return td.getAttribute('data-value') || '';
      });
      var show = rowMatchesQuery(row.textContent, values, q);
      row.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    updateCount(visible, rows.length);
  }

  function getCellValue(row, colIndex) {
    var td = row.querySelector('td[data-col="' + colIndex + '"]');
    return td ? (td.getAttribute('data-value') || td.textContent).trim() : '';
  }

  /** Letter grade to numeric value (4.0 scale, + = +0.3, - = -0.3). Used for Arena, Fan Base, Campus sort. */
  var gradeToNumber = (function () {
    var map = { 'A+': 4.3, 'A': 4, 'A-': 3.7, 'B+': 3.3, 'B': 3, 'B-': 2.7, 'C+': 2.3, 'C': 2, 'C-': 1.7, 'D+': 1.3, 'D': 1, 'D-': 0.7, 'F+': 0.3, 'F': 0, 'F-': 0 };
    return function (str) {
      if (!str || !str.length) return -Infinity;
      var s = str.trim();
      if (/^N\/A\s*\(A\+\)$/i.test(s)) return 4.3;
      var n = map[s];
      return n !== undefined ? n : -Infinity;
    };
  })();

  var gradeCols = {};
  Array.prototype.forEach.call(headerCells, function (th) {
    if (th.getAttribute('data-grade') === 'true') gradeCols[th.getAttribute('data-col')] = true;
  });

  function isNumericColumn(colIndex) {
    if (gradeCols[colIndex] || rows.length === 0) return false;
    var val = getCellValue(rows[0], colIndex);
    return val !== '' && !isNaN(Number(val));
  }

  function sortBy(colIndex, direction) {
    var byGrade = gradeCols[colIndex];
    var numeric = !byGrade && isNumericColumn(colIndex);
    rows.sort(function (a, b) {
      var va = getCellValue(a, colIndex);
      var vb = getCellValue(b, colIndex);
      if (byGrade) {
        var na = gradeToNumber(va);
        var nb = gradeToNumber(vb);
        return direction === 'asc' ? na - nb : nb - na;
      }
      if (numeric) {
        var na = Number(va);
        var nb = Number(vb);
        if (isNaN(na)) na = -Infinity;
        if (isNaN(nb)) nb = -Infinity;
        return direction === 'asc' ? na - nb : nb - na;
      }
      va = (va || '').toLowerCase();
      vb = (vb || '').toLowerCase();
      return direction === 'asc' ? (va < vb ? -1 : va > vb ? 1 : 0) : (vb < va ? -1 : vb > va ? 1 : 0);
    });
    rows.forEach(function (row) { tbody.appendChild(row); });
  }

  function setSortState(activeTh, direction) {
    Array.prototype.forEach.call(headerCells, function (th) {
      th.setAttribute('aria-sort', th === activeTh ? (direction === 'asc' ? 'ascending' : 'descending') : 'none');
      th.classList.remove('sort-asc', 'sort-desc');
      if (th === activeTh) th.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');
    });
  }

  searchInput.addEventListener('input', filterRows);
  searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { searchInput.value = ''; filterRows(); searchInput.blur(); }
  });

  var currentSort = { col: null, dir: 'asc' };
  Array.prototype.forEach.call(headerCells, function (th) {
    var colIndex = th.getAttribute('data-col');
    function handleSort() {
      var dir = currentSort.col === colIndex && currentSort.dir === 'asc' ? 'desc' : 'asc';
      currentSort = { col: colIndex, dir: dir };
      sortBy(colIndex, dir);
      setSortState(th, dir);
    }
    th.addEventListener('click', handleSort);
    th.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort(); }
    });
  });

  updateCount(rows.length, rows.length);
})();
