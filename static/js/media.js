export var PAGE_SIZE = 8;

export function pageSizeFrom(value) {
  var n = Number(value);
  if (!isFinite(n) || n < 1) return PAGE_SIZE;
  return Math.floor(n);
}

export function nextShownCount(shown, total, pageSize) {
  var size = pageSizeFrom(pageSize);
  var have = Number(shown);
  var all = Number(total);
  if (!isFinite(have) || have < 0) have = 0;
  if (!isFinite(all) || all < 0) all = 0;
  return Math.min(all, have + size);
}

export function remainingCount(shown, total) {
  var have = Number(shown);
  var all = Number(total);
  if (!isFinite(have) || have < 0) have = 0;
  if (!isFinite(all) || all < 0) all = 0;
  return Math.max(0, all - have);
}

export function moreLabel(remaining) {
  var n = Number(remaining);
  if (!isFinite(n) || n < 1) return 'Show more posts';
  if (n === 1) return 'Show 1 more post';
  return 'Show ' + n + ' more posts';
}

export function applyPostListPage(items, shown) {
  var list = items || [];
  var total = list.length;
  var n = Number(shown);
  if (!isFinite(n) || n < 0) n = 0;
  n = Math.min(n, total);
  var i;
  for (i = 0; i < total; i++) {
    var item = list[i];
    if (item && item.classList && typeof item.classList.toggle === 'function') {
      item.classList.toggle('is-paged-out', i >= n);
    }
  }
  return { shown: n, total: total, remaining: remainingCount(n, total) };
}

export function mediaFrameLoaded(img) {
  return !!(img && img.complete && img.naturalWidth);
}

export function setMediaFrameState(frame, img) {
  if (!frame || !frame.classList) return 'empty';
  var broken = !!(img && img.complete && !img.naturalWidth);
  if (broken) {
    frame.classList.add('is-error');
    frame.classList.remove('is-loaded');
    return 'error';
  }
  if (mediaFrameLoaded(img)) {
    frame.classList.add('is-loaded');
    frame.classList.remove('is-error');
    return 'loaded';
  }
  frame.classList.remove('is-loaded');
  frame.classList.remove('is-error');
  return 'loading';
}

function bindMediaFrame(frame) {
  if (!frame || frame.getAttribute('data-media-bound')) return;
  var img = frame.querySelector('img');
  if (!img) return;
  frame.setAttribute('data-media-bound', '1');
  var sync = function () {
    setMediaFrameState(frame, img);
  };
  if (img.complete) {
    sync();
    return;
  }
  img.addEventListener('load', sync, { once: true });
  img.addEventListener('error', sync, { once: true });
}

export function bindMediaFrames(root) {
  var scope = root || (typeof document === 'undefined' ? null : document);
  if (!scope || typeof scope.querySelectorAll !== 'function') return 0;
  var frames = scope.querySelectorAll('.media-frame');
  var i;
  for (i = 0; i < frames.length; i++) bindMediaFrame(frames[i]);
  return frames.length;
}

export function initPostListMore(button) {
  if (!button) return null;
  var box = button.parentElement;
  var list = box && box.previousElementSibling;
  if (!list || typeof list.querySelectorAll !== 'function') return null;
  var items = list.querySelectorAll('.post-list-item');
  var size = pageSizeFrom(button.getAttribute('data-page-size'));
  var shown = Math.min(size, items.length);

  function render() {
    var state = applyPostListPage(items, shown);
    button.textContent = moreLabel(state.remaining);
    if (box) box.hidden = state.remaining === 0;
    return state;
  }

  button.addEventListener('click', function () {
    shown = nextShownCount(shown, items.length, size);
    render();
  });
  return render();
}

function init() {
  if (typeof document === 'undefined') return;
  bindMediaFrames(document);
  var buttons = document.querySelectorAll('[data-post-list-more]');
  var i;
  for (i = 0; i < buttons.length; i++) initPostListMore(buttons[i]);
}

init();
