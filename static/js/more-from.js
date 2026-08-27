export function moreFromTargetScrollLeft(nextLeft, scrollerLeft, scrollLeft, maxScroll) {
  var max = Number(maxScroll);
  if (!isFinite(max) || max < 0) max = 0;
  if (nextLeft == null || nextLeft === false) return max;
  var left = Number(nextLeft) - Number(scrollerLeft || 0) + Number(scrollLeft || 0);
  if (!isFinite(left) || left < 0) return 0;
  return Math.min(left, max);
}

export function scrollMoreFrom(scroller) {
  if (!scroller || typeof scroller.querySelector !== 'function') return 0;
  var next = scroller.querySelector('[rel="next"]');
  var max = scroller.scrollWidth - scroller.clientWidth;
  var left;
  if (!next || typeof next.getBoundingClientRect !== 'function' || typeof scroller.getBoundingClientRect !== 'function') {
    left = moreFromTargetScrollLeft(null, 0, 0, max);
  } else {
    var s = scroller.getBoundingClientRect();
    var c = next.getBoundingClientRect();
    left = moreFromTargetScrollLeft(c.left, s.left, scroller.scrollLeft, max);
  }
  scroller.scrollLeft = left;
  return left;
}

function initMoreFrom() {
  if (typeof document === 'undefined') return;
  var rows = document.querySelectorAll('.more-from-scroller');
  for (var i = 0; i < rows.length; i++) scrollMoreFrom(rows[i]);
}

initMoreFrom();
