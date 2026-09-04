export function clampScore(n) {
  var x = Number(n);
  if (!isFinite(x) || x < 0) return 0;
  return Math.min(999, Math.floor(x));
}

export function scoreWidth(home, away) {
  return clampScore(home) >= 100 || clampScore(away) >= 100 ? 3 : 2;
}

export function scoreDigits(score, width) {
  var w = Number(width);
  if (!isFinite(w) || w < 2) w = 2;
  if (w > 3) w = 3;
  var s = String(clampScore(score));
  while (s.length < w) s = '0' + s;
  return s.split('').map(function (ch) {
    return Number(ch);
  });
}

export function countUpFrames(homeTarget, awayTarget) {
  var homeGoal = clampScore(homeTarget);
  var awayGoal = clampScore(awayTarget);
  var home = 0;
  var away = 0;
  var frames = [];
  while (home < homeGoal || away < awayGoal) {
    if (home < homeGoal) home += 1;
    if (away < awayGoal) away += 1;
    frames.push({ home: home, away: away });
  }
  return frames;
}

export function shouldAnimate(reducedMotion) {
  return !reducedMotion;
}

export function digitStaggerMs(indexFromRight, step) {
  var gap = step == null ? 70 : Number(step);
  if (!isFinite(gap) || gap < 0) gap = 70;
  return (Number(indexFromRight) || 0) * gap;
}

export function digitHtml(value) {
  var n = String(clampScore(value) % 10);
  return (
    '<span class="scoreboard-digit" data-digit="' +
    n +
    '">' +
    '<span class="scoreboard-digit-base-top" aria-hidden="true"><span data-flip-text>' +
    n +
    '</span></span>' +
    '<span class="scoreboard-digit-base-bottom" aria-hidden="true"><span data-flip-text>' +
    n +
    '</span></span>' +
    '<span class="scoreboard-digit-leaf-top" aria-hidden="true"><span data-flip-text>' +
    n +
    '</span></span>' +
    '<span class="scoreboard-digit-leaf-bottom" aria-hidden="true"><span data-flip-text>' +
    n +
    '</span></span>' +
    '</span>'
  );
}

export function digitsHtml(digits) {
  return (digits || []).map(digitHtml).join('');
}

export var FLIP_MS = 150;
export var COUNT_TICK_MS = 24;

function wait(ms) {
  return new Promise(function (resolve) {
    setTimeout(resolve, ms);
  });
}

function boardSpec(root) {
  var homeScore = clampScore(root.dataset.homeScore);
  var awayScore = clampScore(root.dataset.awayScore);
  var width = Number(root.dataset.width);
  if (!isFinite(width) || width < 2) width = scoreWidth(homeScore, awayScore);
  return { homeScore: homeScore, awayScore: awayScore, width: width };
}

function setDigitTexts(el, value) {
  var n = String(clampScore(value) % 10);
  el.dataset.digit = n;
  var nodes = el.querySelectorAll('[data-flip-text]');
  for (var i = 0; i < nodes.length; i++) nodes[i].textContent = n;
}

export function flipDigitTo(el, next, waitFn) {
  var pause = waitFn || wait;
  var curr = el.dataset.digit || '0';
  var target = String(clampScore(next) % 10);
  if (curr === target) return Promise.resolve();
  var topLeaf = el.querySelector('.scoreboard-digit-leaf-top [data-flip-text]');
  var bottomLeaf = el.querySelector('.scoreboard-digit-leaf-bottom [data-flip-text]');
  var baseTop = el.querySelector('.scoreboard-digit-base-top [data-flip-text]');
  var baseBottom = el.querySelector('.scoreboard-digit-base-bottom [data-flip-text]');
  if (topLeaf) topLeaf.textContent = curr;
  if (baseBottom) baseBottom.textContent = curr;
  if (baseTop) baseTop.textContent = target;
  if (bottomLeaf) bottomLeaf.textContent = target;
  el.classList.add('is-flipping');
  return pause(FLIP_MS).then(function () {
    el.classList.remove('is-flipping');
    setDigitTexts(el, target);
  });
}

export function paintScore(root, spec, homeScore, awayScore, waitFn) {
  var pause = waitFn || wait;
  var homeEl = root.querySelector('[data-side="home"]');
  var awayEl = root.querySelector('[data-side="away"]');
  var homeCards =
    homeEl && typeof homeEl.querySelectorAll === 'function'
      ? homeEl.querySelectorAll('.scoreboard-digit')
      : [];
  var awayCards =
    awayEl && typeof awayEl.querySelectorAll === 'function'
      ? awayEl.querySelectorAll('.scoreboard-digit')
      : [];
  var changed = [];
  function queue(cards, digits) {
    for (var i = 0; i < cards.length; i++) {
      var next = String(digits[i]);
      var curr = cards[i].dataset ? cards[i].dataset.digit : '';
      setDigitTexts(cards[i], digits[i]);
      if (curr !== next && cards[i].classList && cards[i].classList.add) {
        cards[i].classList.add('is-flipping');
        changed.push(cards[i]);
      }
    }
  }
  queue(homeCards, scoreDigits(homeScore, spec.width));
  queue(awayCards, scoreDigits(awayScore, spec.width));
  return pause(COUNT_TICK_MS).then(function () {
    for (var j = 0; j < changed.length; j++) {
      if (changed[j].classList && changed[j].classList.remove) {
        changed[j].classList.remove('is-flipping');
      }
    }
  });
}

export function playScoreboard(root, spec, waitFn) {
  var pause = waitFn || wait;
  var frames = countUpFrames(spec.homeScore, spec.awayScore);
  if (root.dataset) root.dataset.busy = '1';
  if (root.classList && root.classList.add) root.classList.add('is-playing');
  var chain = Promise.resolve();
  frames.forEach(function (frame) {
    chain = chain.then(function () {
      return paintScore(root, spec, frame.home, frame.away, pause);
    });
  });
  return chain.then(function () {
    if (root.classList && root.classList.remove) root.classList.remove('is-playing');
    if (root.dataset) root.dataset.busy = '';
  });
}

export function mountScoreboard(root, opts) {
  if (!root || typeof root.querySelector !== 'function') return;
  var options = opts || {};
  var spec = boardSpec(root);
  var home = root.querySelector('[data-side="home"]');
  var away = root.querySelector('[data-side="away"]');
  var animate = options.animate;
  if (animate == null) animate = shouldAnimate(options.reducedMotion);
  if (home) home.innerHTML = digitsHtml(scoreDigits(animate ? 0 : spec.homeScore, spec.width));
  if (away) away.innerHTML = digitsHtml(scoreDigits(animate ? 0 : spec.awayScore, spec.width));
  if (animate && options.play !== false) {
    return playScoreboard(root, spec, options.wait);
  }
}

export function replayScoreboard(root, opts) {
  if (!root) return false;
  if (root.dataset && root.dataset.busy === '1') return false;
  var options = opts || {};
  var animate = options.animate;
  if (animate == null) animate = shouldAnimate(options.reducedMotion);
  if (root.dataset) root.dataset.busy = '1';
  if (!animate) {
    mountScoreboard(root, { animate: false, play: false });
    if (root.dataset) root.dataset.busy = '';
    return true;
  }
  mountScoreboard(root, { animate: true, play: false });
  return Promise.resolve(playScoreboard(root, boardSpec(root), options.wait)).then(function () {
    return true;
  });
}

export function bindScoreboardClick(root, opts) {
  if (!root || typeof root.addEventListener !== 'function') return;
  root.addEventListener('click', function () {
    replayScoreboard(root, opts);
  });
}

export function isBoardInView(el, viewportHeight) {
  if (!el || typeof el.getBoundingClientRect !== 'function') return false;
  var r = el.getBoundingClientRect();
  var vh = Number(viewportHeight);
  if (!isFinite(vh) || vh <= 0) return false;
  return r.bottom > 0 && r.top < vh;
}

function prefersReducedMotion() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function initScoreboards(doc, observerFactory, opts) {
  if (!doc || typeof doc.querySelectorAll !== 'function') return;
  var options = opts || {};
  var motion = options.reducedMotion;
  if (motion == null) motion = prefersReducedMotion();
  var animate = shouldAnimate(motion);
  var boards = doc.querySelectorAll('.scoreboard');
  for (var i = 0; i < boards.length; i++) {
    (function (board) {
      mountScoreboard(board, { animate: animate, play: false });
      bindScoreboardClick(board, options);
      var play = function () {
        if (board.dataset.played) return;
        board.dataset.played = '1';
        if (animate) playScoreboard(board, boardSpec(board), options.wait);
      };
      if (!animate || typeof observerFactory !== 'function') {
        play();
        return;
      }
      var io = observerFactory(function (entries) {
        for (var k = 0; k < entries.length; k++) {
          if (entries[k].isIntersecting) {
            play();
            io.disconnect();
            break;
          }
        }
      });
      io.observe(board);
      if (typeof window !== 'undefined' && isBoardInView(board, window.innerHeight)) play();
    })(boards[i]);
  }
}

function boot() {
  if (typeof document === 'undefined') return;
  var factory =
    typeof IntersectionObserver === 'function'
      ? function (cb) {
          return new IntersectionObserver(cb, { threshold: 0.01 });
        }
      : null;
  initScoreboards(document, factory);
}

boot();
