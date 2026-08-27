export function scrollFadeState(scrollLeft, clientWidth, scrollWidth) {
  var left = Number(scrollLeft);
  var view = Number(clientWidth);
  var total = Number(scrollWidth);
  if (!isFinite(left) || !isFinite(view) || !isFinite(total) || view <= 0) {
    return { start: false, end: false };
  }
  var maxScroll = total - view;
  if (maxScroll <= 1) {
    return { start: false, end: false };
  }
  return {
    start: left > 1,
    end: left < maxScroll - 1
  };
}

export function applyScrollFade(nav, scroller) {
  var state = scrollFadeState(
    scroller && scroller.scrollLeft,
    scroller && scroller.clientWidth,
    scroller && scroller.scrollWidth
  );
  if (nav && nav.classList && typeof nav.classList.toggle === 'function') {
    nav.classList.toggle('site-nav--fade-start', state.start);
    nav.classList.toggle('site-nav--fade-end', state.end);
  }
  return state;
}

function bindNavScroll(nav) {
  var scroller = nav.querySelector('ul');
  if (!scroller) return;

  function update() {
    applyScrollFade(nav, scroller);
  }

  scroller.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update);
  if (typeof ResizeObserver === 'function') {
    new ResizeObserver(update).observe(scroller);
  }
  if (document.fonts && document.fonts.ready && typeof document.fonts.ready.then === 'function') {
    document.fonts.ready.then(update);
  }
  update();
}

function initNavScroll() {
  if (typeof document === 'undefined') return;
  var nav = document.querySelector('.site-header .site-nav');
  if (!nav) return;
  bindNavScroll(nav);
}

initNavScroll();
