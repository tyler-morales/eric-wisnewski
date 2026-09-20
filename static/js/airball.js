export function clamp(n, lo, hi) {
  var x = Number(n);
  if (!isFinite(x)) return lo;
  if (x < lo) return lo;
  if (x > hi) return hi;
  return x;
}

export function courtLayout(width, height) {
  var w = Number(width);
  var h = Number(height);
  if (!isFinite(w) || w <= 0) w = 320;
  if (!isFinite(h) || h <= 0) h = 240;
  var ballR = clamp(Math.round(Math.min(w, h) * 0.05), 13, 18);
  var floorH = 22;
  var floorTop = h - floorH;
  var gap = Math.max(ballR * 4.6, 56);
  var rimR = 4;
  var hoopY = clamp(h * 0.46, ballR * 7, h * 0.52);
  var backboardW = 8;
  var backboardH = Math.max(64, h * 0.26);
  var hoopRight = w * 0.7;
  var rimBackX = hoopRight - 8;
  var rimFrontX = rimBackX - gap;
  return {
    width: w,
    height: h,
    ballR: ballR,
    ballX: Math.max(ballR + 28, w * 0.2),
    ballY: floorTop - ballR - 0.5,
    floorH: floorH,
    floorTop: floorTop,
    hoopY: hoopY,
    rimR: rimR,
    rimFrontX: rimFrontX,
    rimBackX: rimBackX,
    backboard: {
      x: hoopRight + backboardW / 2,
      y: hoopY - backboardH * 0.12,
      w: backboardW,
      h: backboardH
    },
    zone: {
      left: rimFrontX + rimR + 1,
      right: rimBackX - rimR - 1,
      top: hoopY,
      bottom: hoopY + ballR * 1.35
    }
  };
}

export function pointerInBall(px, py, ball, slop) {
  if (!ball) return false;
  var pad = slop == null ? 10 : Number(slop);
  if (!isFinite(pad) || pad < 0) pad = 10;
  var dx = px - ball.x;
  var dy = py - ball.y;
  var reach = ball.radius + pad;
  return dx * dx + dy * dy <= reach * reach;
}

export function flingVelocity(startX, startY, endX, endY, dtMs, opts) {
  opts = opts || {};
  var minDist = opts.minDist == null ? 14 : opts.minDist;
  var maxSpeed = opts.maxSpeed == null ? 16 : opts.maxSpeed;
  var capDist = opts.capDist == null ? 110 : opts.capDist;
  var dx = Number(startX) - Number(endX);
  var dy = Number(startY) - Number(endY);
  var dist = Math.hypot(dx, dy);
  if (!isFinite(dist) || dist < minDist) {
    return { vx: 0, vy: 0, dist: isFinite(dist) ? dist : 0 };
  }
  var t = Math.min(dist, capDist) / capDist;
  var power = t * maxSpeed;
  return { vx: (dx / dist) * power, vy: (dy / dist) * power, dist: dist };
}

export function swishVelocity(layout) {
  if (!layout) return { vx: 0, vy: 0 };
  var hoopX = (Number(layout.rimFrontX) + Number(layout.rimBackX)) / 2;
  var dx = hoopX - Number(layout.ballX);
  var h = Number(layout.height) || 420;
  return { vx: dx * 0.0172, vy: -8.2 - h * 0.01 };
}

export function mixShot(raw, swish, pullT) {
  if (!raw || (raw.vx === 0 && raw.vy === 0)) {
    return { vx: 0, vy: 0, dist: raw && raw.dist ? raw.dist : 0 };
  }
  var t = clamp(pullT, 0, 1);
  var aimX = swish && swish.vx ? swish.vx : 0;
  var aimY = swish && swish.vy ? swish.vy : 0;
  // ponytail: committed pulls use a known swish; true ballistic if we add a second rim collider.
  if (t < 0.5) {
    return { vx: aimX * t * 1.5, vy: aimY * t * 1.5, dist: raw.dist };
  }
  return { vx: aimX, vy: aimY, dist: raw.dist };
}

export function isMake(prev, next, zone) {
  if (!prev || !next || !zone) return false;
  if (!(next.vy > 0.15)) return false;
  var dy = next.y - prev.y;
  if (!(dy > 0) || !(prev.y < zone.top && next.y >= zone.top)) return false;
  var x = prev.x + (next.x - prev.x) * ((zone.top - prev.y) / dy);
  return x >= zone.left && x <= zone.right;
}

export function isOutOfPlay(ball, layout, margin) {
  if (!ball || !layout) return false;
  var pad = margin == null ? 56 : Number(margin);
  if (!isFinite(pad)) pad = 56;
  return (
    ball.x < -pad ||
    ball.x > layout.width + pad ||
    ball.y > layout.height + pad ||
    ball.y < -pad * 4
  );
}

export function isSettled(ball, floorTop, settledSpeed) {
  if (!ball) return false;
  var limit = settledSpeed == null ? 0.42 : Number(settledSpeed);
  if (!isFinite(limit) || limit < 0) limit = 0.42;
  var speed = Math.hypot(ball.vx || 0, ball.vy || 0);
  var onFloor = ball.y + ball.radius >= Number(floorTop) - 3;
  return onFloor && speed < limit;
}

export function shouldResetBall(ball, layout, state) {
  if (!state || !state.hasShot || state.aiming || state.made) return false;
  return isOutOfPlay(ball, layout) || isSettled(ball, layout && layout.floorTop);
}

function cssSize(canvas) {
  var rect = canvas.getBoundingClientRect();
  return { width: Math.max(1, rect.width), height: Math.max(1, rect.height), rect: rect };
}

function fitCanvas(canvas) {
  var size = cssSize(canvas);
  var dpr = window.devicePixelRatio || 1;
  var w = Math.round(size.width * dpr);
  var h = Math.round(size.height * dpr);
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  var ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx: ctx, layout: courtLayout(size.width, size.height), rect: size.rect };
}

function ballState(body) {
  return {
    x: body.position.x,
    y: body.position.y,
    radius: body.circleRadius,
    vx: body.velocity.x,
    vy: body.velocity.y
  };
}

function drawNet(ctx, layout) {
  var left = layout.rimFrontX;
  var right = layout.rimBackX;
  var top = layout.hoopY + 1;
  var bottom = top + layout.ballR * 2.1;
  var mid = (left + right) / 2;
  ctx.strokeStyle = 'rgba(0,0,0,0.5)';
  ctx.lineWidth = 1;
  var i;
  for (i = 0; i <= 5; i++) {
    var t = i / 5;
    var x0 = left + (right - left) * t;
    ctx.beginPath();
    ctx.moveTo(x0, top);
    ctx.quadraticCurveTo(mid, bottom + 6, left + (right - left) * (0.2 + t * 0.6), bottom);
    ctx.stroke();
  }
}

function drawBall(ctx, x, y, r, angle) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, Math.PI * 2);
  ctx.fillStyle = '#e36b1a';
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#111';
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(-r, 0);
  ctx.lineTo(r, 0);
  ctx.moveTo(0, -r);
  ctx.lineTo(0, r);
  ctx.arc(0, 0, r * 0.58, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function drawCourt(ctx, layout, ball, aim) {
  var w = layout.width;
  var h = layout.height;
  ctx.fillStyle = '#f3efe6';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(8, layout.floorTop);
  ctx.lineTo(w - 8, layout.floorTop);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(layout.rimFrontX - 8, layout.floorTop, Math.min(w * 0.42, h * 0.7), Math.PI, Math.PI * 1.5, true);
  ctx.strokeStyle = 'rgba(0,0,0,0.28)';
  ctx.stroke();
  var bb = layout.backboard;
  ctx.fillStyle = '#fff';
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 2;
  ctx.fillRect(bb.x - bb.w / 2, bb.y - bb.h / 2, bb.w, bb.h);
  ctx.strokeRect(bb.x - bb.w / 2, bb.y - bb.h / 2, bb.w, bb.h);
  ctx.fillStyle = '#111';
  ctx.fillRect(bb.x - bb.w / 2 - 4, layout.hoopY - 18, 4, 36);
  drawNet(ctx, layout);
  ctx.fillStyle = '#e36b1a';
  ctx.beginPath();
  ctx.arc(layout.rimFrontX, layout.hoopY, layout.rimR, 0, Math.PI * 2);
  ctx.arc(layout.rimBackX, layout.hoopY, layout.rimR, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = '#111';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(layout.rimFrontX, layout.hoopY);
  ctx.lineTo(layout.rimBackX, layout.hoopY);
  ctx.stroke();
  if (ball) drawBall(ctx, ball.x, ball.y, ball.radius, ball.angle || 0);
  if (aim && ball) {
    ctx.strokeStyle = '#000';
    ctx.setLineDash([6, 5]);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(ball.x, ball.y);
    ctx.lineTo(aim.x, aim.y);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(aim.x, aim.y, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#000';
    ctx.fill();
  }
}

function waitForMatter(done) {
  if (typeof globalThis !== 'undefined' && globalThis.Matter) {
    done(globalThis.Matter);
    return;
  }
  var n = 0;
  var t = setInterval(function () {
    n += 1;
    if (globalThis.Matter) {
      clearInterval(t);
      done(globalThis.Matter);
    } else if (n > 40) {
      clearInterval(t);
      done(null);
    }
  }, 50);
}

function showFallback(root) {
  var note = root.querySelector('.airball-fallback');
  var canvas = root.querySelector('canvas');
  if (note) note.hidden = false;
  if (canvas) canvas.hidden = true;
}

export function bootAirball(root, MatterLib) {
  if (!root || !MatterLib) return null;
  var canvas = root.querySelector('canvas');
  var makesEl = root.querySelector('[data-airball-makes]');
  if (!canvas) return null;
  var Engine = MatterLib.Engine;
  var Bodies = MatterLib.Bodies;
  var Body = MatterLib.Body;
  var Composite = MatterLib.Composite;
  var engine = Engine.create();
  engine.gravity.y = 0.9;
  var fitted = fitCanvas(canvas);
  var layout = fitted.layout;
  var ctx = fitted.ctx;
  var ball;
  var makes = 0;
  var prev = null;
  var aiming = false;
  var hasShot = false;
  var made = false;
  var pointer = null;
  var downAt = 0;
  var start = null;
  var settledMs = 0;
  var last = 0;
  var raf = 0;

  function setMakes(n) {
    makes = n;
    if (makesEl) makesEl.textContent = String(makes);
  }

  function addStatic(bodies) {
    Composite.add(engine.world, bodies);
  }

  function spawn() {
    Composite.clear(engine.world, false);
    var floor = Bodies.rectangle(
      layout.width / 2,
      layout.floorTop + layout.floorH / 2,
      layout.width + 120,
      layout.floorH,
      { isStatic: true, friction: 0.85, restitution: 0.32, label: 'floor' }
    );
    var left = Bodies.rectangle(-24, layout.height / 2, 48, layout.height * 3, {
      isStatic: true,
      label: 'wall'
    });
    var bb = layout.backboard;
    var backboard = Bodies.rectangle(bb.x, bb.y, bb.w, bb.h, {
      isStatic: true,
      restitution: 0.58,
      friction: 0.2,
      label: 'backboard'
    });
    var rim = Bodies.rectangle(
      (layout.rimFrontX + layout.rimBackX) / 2,
      layout.hoopY,
      layout.rimBackX - layout.rimFrontX,
      6,
      { isStatic: true, isSensor: true, label: 'rim' }
    );
    ball = Bodies.circle(layout.ballX, layout.ballY, layout.ballR, {
      restitution: 0.65,
      friction: 0.04,
      frictionAir: 0.002,
      density: 0.002,
      label: 'ball'
    });
    addStatic([floor, left, backboard, rim, ball]);
    prev = ballState(ball);
    aiming = false;
    hasShot = false;
    made = false;
    pointer = null;
    settledMs = 0;
  }

  function resetBall() {
    if (!ball) return;
    Body.setStatic(ball, false);
    Body.setPosition(ball, { x: layout.ballX, y: layout.ballY });
    Body.setVelocity(ball, { x: 0, y: 0 });
    Body.setAngularVelocity(ball, 0);
    prev = ballState(ball);
    aiming = false;
    hasShot = false;
    made = false;
    pointer = null;
    settledMs = 0;
  }

  function localPoint(event) {
    var rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  function onDown(event) {
    if (made) return;
    if (event.button != null && event.button !== 0) return;
    var p = localPoint(event);
    var b = ballState(ball);
    if (!pointerInBall(p.x, p.y, b, Math.max(14, b.radius))) return;
    event.preventDefault();
    aiming = true;
    hasShot = false;
    made = false;
    start = p;
    pointer = p;
    downAt = Date.now();
    Body.setStatic(ball, true);
    Body.setPosition(ball, { x: layout.ballX, y: layout.ballY });
    Body.setVelocity(ball, { x: 0, y: 0 });
    if (canvas.setPointerCapture) {
      try {
        canvas.setPointerCapture(event.pointerId);
      } catch (e) {}
    }
  }

  function onMove(event) {
    if (!aiming) return;
    pointer = localPoint(event);
  }

  function onUp(event) {
    if (!aiming) return;
    aiming = false;
    var end = event ? localPoint(event) : pointer;
    pointer = null;
    Body.setStatic(ball, false);
    if (!end || !start) return;
    var reach = 10 + layout.width / 140;
    var raw = flingVelocity(start.x, start.y, end.x, end.y, Date.now() - downAt, {
      maxSpeed: reach
    });
    if (raw.vx === 0 && raw.vy === 0) return;
    hasShot = true;
    var shot = mixShot(raw, swishVelocity(layout), Math.min(raw.dist, 110) / 110);
    Body.setVelocity(ball, { x: shot.vx, y: shot.vy });
    Body.setAngularVelocity(ball, shot.vx * 0.06);
  }

  canvas.addEventListener('pointerdown', onDown);
  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('pointercancel', onUp);
  canvas.addEventListener(
    'touchmove',
    function (event) {
      if (aiming) event.preventDefault();
    },
    { passive: false }
  );

  function rebuild() {
    fitted = fitCanvas(canvas);
    layout = fitted.layout;
    ctx = fitted.ctx;
    spawn();
  }

  if (typeof ResizeObserver === 'function') {
    new ResizeObserver(rebuild).observe(canvas);
  } else {
    window.addEventListener('resize', rebuild);
  }

  spawn();

  function tick(now) {
    var dt = last ? Math.min(32, now - last) : 16;
    last = now;
    Engine.update(engine, 1000 / 60);
    var next = ballState(ball);
    next.angle = ball.angle;
    if (!aiming && !made && isMake(prev, next, layout.zone)) {
      made = true;
      setMakes(makes + 1);
      setTimeout(resetBall, 700);
    } else if (shouldResetBall(next, layout, { hasShot: hasShot, aiming: aiming, made: made })) {
      settledMs += dt;
      if (isOutOfPlay(next, layout) || settledMs > 480) resetBall();
    } else {
      settledMs = 0;
    }
    prev = next;
    drawCourt(ctx, layout, aiming ? { x: layout.ballX, y: layout.ballY, radius: layout.ballR, angle: 0 } : next, aiming ? pointer : null);
    raf = requestAnimationFrame(tick);
  }

  raf = requestAnimationFrame(tick);
  return {
    stop: function () {
      cancelAnimationFrame(raf);
    }
  };
}

function autoBoot() {
  var root = document.querySelector('[data-airball]');
  if (!root) return;
  waitForMatter(function (MatterLib) {
    if (!MatterLib) {
      showFallback(root);
      return;
    }
    bootAirball(root, MatterLib);
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoBoot);
  } else {
    autoBoot();
  }
}
