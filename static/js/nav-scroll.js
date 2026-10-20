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

export function prefersReducedMotion() {
  try {
    var query = globalThis.matchMedia;
    return typeof query === 'function' && query('(prefers-reduced-motion: reduce)').matches;
  } catch (err) {
    return false;
  }
}

export function activeTabScrollLeft(scrollLeft, clientWidth, scrollWidth, activeLeft, activeWidth, scrollerLeft) {
  var left = Number(scrollLeft);
  var view = Number(clientWidth);
  var total = Number(scrollWidth);
  var itemLeft = Number(activeLeft);
  var itemWidth = Number(activeWidth);
  var origin = Number(scrollerLeft);
  if (!isFinite(left) || !isFinite(view) || !isFinite(total) || !isFinite(itemLeft) || !isFinite(itemWidth) || !isFinite(origin) || view <= 0) {
    return isFinite(left) ? left : 0;
  }
  var next = left + (itemLeft + itemWidth / 2) - (origin + view / 2);
  var maxScroll = total - view;
  if (maxScroll < 0) maxScroll = 0;
  if (next < 0) return 0;
  if (next > maxScroll) return maxScroll;
  return next;
}

export function centerActiveTab(scroller) {
  if (!scroller || typeof scroller.querySelector !== 'function') return null;
  var active = scroller.querySelector('[aria-current="page"]');
  if (!active || typeof active.getBoundingClientRect !== 'function' || typeof scroller.getBoundingClientRect !== 'function') {
    return null;
  }
  var item = active.getBoundingClientRect();
  var box = scroller.getBoundingClientRect();
  var left = activeTabScrollLeft(
    scroller.scrollLeft,
    scroller.clientWidth,
    scroller.scrollWidth,
    item.left,
    item.width,
    box.left
  );
  if (!isFinite(left) || Math.abs((Number(scroller.scrollLeft) || 0) - left) <= 1) return left;
  // Instant either way. A smooth scroll after paint is the jump, and reduced motion forbids it.
  if (prefersReducedMotion()) scroller.scrollLeft = left;
  else scroller.scrollLeft = left;
  return left;
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
  var userMoved = false;
  var centering = false;

  function update() {
    applyScrollFade(nav, scroller);
  }

  function center() {
    if (userMoved) return;
    centering = true;
    centerActiveTab(scroller);
    centering = false;
  }

  scroller.addEventListener('scroll', function () {
    if (!centering) userMoved = true;
    update();
  }, { passive: true });
  window.addEventListener('resize', function () {
    center();
    update();
  });
  if (typeof ResizeObserver === 'function') {
    new ResizeObserver(function () {
      center();
      update();
    }).observe(scroller);
  }
  if (document.fonts && document.fonts.ready && typeof document.fonts.ready.then === 'function') {
    document.fonts.ready.then(function () {
      center();
      update();
    });
  }
  center();
  update();
}

function initNavScroll() {
  if (typeof document === 'undefined') return;
  var nav = document.querySelector('.site-header .site-nav');
  if (!nav) return;
  bindNavScroll(nav);
}

initNavScroll();
