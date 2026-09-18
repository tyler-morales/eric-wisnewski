export var COUNTRY_SLUG_ALIASES = {
  'united-states-of-america': 'united-states',
  'bosnia-and-herz': 'bosnia-and-herzegovina',
  'central-african-rep': 'central-african-republic',
  'dem-rep-congo': 'democratic-republic-of-the-congo',
  'dominican-rep': 'dominican-republic',
  'eq-guinea': 'equatorial-guinea',
  'falkland-is': 'falkland-islands',
  'solomon-is': 'solomon-islands',
  's-sudan': 'south-sudan',
  'macedonia': 'north-macedonia',
};

var WORLD_SRC_DEFAULT = '/maps/countries-110m.json';
var D3_GEO_SRC = 'https://cdn.jsdelivr.net/npm/d3-geo@3.1.1/+esm';
var TOPOJSON_SRC = 'https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/+esm';
export var GLOBE_SIZE = 640;
export var GLOBE_SCALE_MIN = GLOBE_SIZE / 2.15;
export var GLOBE_SCALE_MAX = GLOBE_SCALE_MIN * 10;
export var GLOBE_ZOOM_STEP = 1.4;
export var GLOBE_FIT_PADDING = 0.82;

export function countrySlug(value) {
  return String(value || '')
    .trim()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/['’]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function featureCountrySlug(name) {
  var slug = countrySlug(name);
  return COUNTRY_SLUG_ALIASES[slug] || slug;
}

export function countryName(value) {
  var slug = countrySlug(value);
  if (!slug) return '';
  return slug
    .split('-')
    .map(function (part) {
      return part.charAt(0).toUpperCase() + part.slice(1);
    })
    .join(' ');
}

export function countryFromSearch(search) {
  var raw = String(search || '');
  if (raw.charAt(0) === '?') raw = raw.slice(1);
  try {
    return countrySlug(new URLSearchParams(raw).get('country'));
  } catch (e) {
    return '';
  }
}

export function tourListUrl(country, base) {
  var root = String(base || '/gradys-tour/');
  if (/^https?:\/\//i.test(root)) {
    try {
      root = new URL(root).pathname;
    } catch (err) {
      root = '/gradys-tour/';
    }
  }
  if (root.charAt(root.length - 1) !== '/') root += '/';
  var slug = countrySlug(country);
  if (!slug) return root;
  return root + '?country=' + encodeURIComponent(slug);
}

export function itemCountries(value) {
  return String(value || '')
    .split(/[\s,]+/)
    .map(countrySlug)
    .filter(Boolean);
}

export function postCountries(post) {
  if (!post) return [];
  var raw = post.countries != null ? post.countries : post.country;
  if (Array.isArray(raw)) {
    var out = [];
    for (var i = 0; i < raw.length; i++) {
      var slug = countrySlug(raw[i]);
      if (slug && out.indexOf(slug) === -1) out.push(slug);
    }
    return out;
  }
  return itemCountries(raw);
}

export function itemVisible(itemCountry, selected) {
  var want = countrySlug(selected);
  if (!want) return true;
  return itemCountries(itemCountry).indexOf(want) !== -1;
}

export function titleForCountry(country) {
  var name = countryName(country);
  if (!name) return "Grady's Tour";
  return "Grady's Tour · " + name;
}

export function withSiteTitle(pageTitle, documentTitle) {
  var page = String(pageTitle || '');
  var current = String(documentTitle || '');
  var pipe = current.indexOf(' | ');
  if (pipe === -1) return page;
  return page + current.slice(pipe);
}

export function countByCountry(posts) {
  var counts = {};
  var list = posts || [];
  for (var i = 0; i < list.length; i++) {
    var slugs = postCountries(list[i]);
    for (var j = 0; j < slugs.length; j++) {
      counts[slugs[j]] = (counts[slugs[j]] || 0) + 1;
    }
  }
  return counts;
}

export function optionLabel(country, count) {
  var name = countryName(country);
  var n = Number(count) || 0;
  if (!name) return 'All countries';
  return name + ' (' + n + ')';
}

export function countLabel(country, count) {
  var name = countryName(country);
  var n = Number(count) || 0;
  if (!name) return '';
  if (n === 1) return '1 post in ' + name;
  return n + ' posts in ' + name;
}

export function parseCatalogJson(raw) {
  try {
    var data = JSON.parse(raw || '{}');
    if (typeof data === 'string') data = JSON.parse(data);
    if (!data || typeof data !== 'object' || Array.isArray(data)) data = {};
    if (!Array.isArray(data.posts)) data.posts = [];
    return data;
  } catch (e) {
    return { posts: [] };
  }
}

export function clampGlobeScale(scale) {
  var n = Number(scale);
  if (!isFinite(n)) return GLOBE_SCALE_MIN;
  return Math.max(GLOBE_SCALE_MIN, Math.min(GLOBE_SCALE_MAX, n));
}

export function scaleToFit(bounds, currentScale, size, padding) {
  var current = Number(currentScale);
  if (!isFinite(current)) current = GLOBE_SCALE_MIN;
  if (!bounds || !Array.isArray(bounds) || bounds.length < 2) {
    return clampGlobeScale(current);
  }
  var a = bounds[0];
  var b = bounds[1];
  if (!a || !b || a.length < 2 || b.length < 2) return clampGlobeScale(current);
  var dx = Number(b[0]) - Number(a[0]);
  var dy = Number(b[1]) - Number(a[1]);
  var span = Math.max(dx, dy);
  var w = Number(size);
  if (!isFinite(w) || w <= 0) w = GLOBE_SIZE;
  var pad = Number(padding);
  if (!isFinite(pad) || pad <= 0) pad = GLOBE_FIT_PADDING;
  if (!isFinite(span) || span <= 0) return clampGlobeScale(current);
  return clampGlobeScale(current * ((pad * w) / span));
}

export function pointOnGlobe(pt, cx, cy, radius) {
  if (!pt || pt.length < 2) return false;
  var dx = Number(pt[0]) - Number(cx);
  var dy = Number(pt[1]) - Number(cy);
  var r = Number(radius);
  if (!isFinite(dx) || !isFinite(dy) || !isFinite(r) || r <= 0) return false;
  return dx * dx + dy * dy <= r * r;
}

function readCatalog(nav) {
  var empty = { posts: [], base: '/gradys-tour/', listPage: true };
  var node = nav.querySelector('[data-tour-catalog]');
  if (!node) return empty;
  var data = parseCatalogJson(node.textContent || '{}');
  if (!data.base) data.base = empty.base;
  return data;
}

function applyIndexFilter(selected) {
  var items = document.querySelectorAll('.post-list-item');
  var visible = 0;
  for (var i = 0; i < items.length; i++) {
    var show = itemVisible(items[i].getAttribute('data-country'), selected);
    items[i].hidden = !show;
    if (show) visible += 1;
  }
  var pageTitle = titleForCountry(selected);
  var titleEl = document.querySelector('[data-tour-title]');
  if (titleEl) titleEl.textContent = pageTitle;
  document.title = withSiteTitle(pageTitle, document.title);
  var empty = document.querySelector('[data-tour-empty]');
  if (empty) empty.hidden = visible !== 0;
  var list = document.querySelector('.post-list');
  if (list) list.hidden = selected !== '' && visible === 0;
  return visible;
}

/* Versor rotation (Jason Davies / Mike Bostock, MIT). */
var RAD = Math.PI / 180;
var DEG = 180 / Math.PI;

function versorFromAngles(e) {
  var l = (e[0] / 2) * RAD;
  var p = (e[1] / 2) * RAD;
  var g = ((e[2] || 0) / 2) * RAD;
  var sl = Math.sin(l);
  var cl = Math.cos(l);
  var sp = Math.sin(p);
  var cp = Math.cos(p);
  var sg = Math.sin(g);
  var cg = Math.cos(g);
  return [
    cl * cp * cg + sl * sp * sg,
    sl * cp * cg - cl * sp * sg,
    cl * sp * cg + sl * cp * sg,
    cl * cp * sg - sl * sp * cg,
  ];
}

function versorToAngles(q) {
  return [
    Math.atan2(2 * (q[0] * q[1] + q[2] * q[3]), 1 - 2 * (q[1] * q[1] + q[2] * q[2])) * DEG,
    Math.asin(Math.max(-1, Math.min(1, 2 * (q[0] * q[2] - q[3] * q[1])))) * DEG,
    Math.atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] * q[2] + q[3] * q[3])) * DEG,
  ];
}

function versorMultiply(a, b) {
  return [
    a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
    a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
    a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
    a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
  ];
}

function versorCartesian(e) {
  var l = e[0] * RAD;
  var p = e[1] * RAD;
  var cp = Math.cos(p);
  return [cp * Math.cos(l), cp * Math.sin(l), Math.sin(p)];
}

function versorDelta(v0, v1) {
  var w = [
    v0[1] * v1[2] - v0[2] * v1[1],
    v0[2] * v1[0] - v0[0] * v1[2],
    v0[0] * v1[1] - v0[1] * v1[0],
  ];
  var l = Math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2]);
  if (!l) return [1, 0, 0, 0];
  var t = Math.acos(Math.max(-1, Math.min(1, v0[0] * v1[0] + v0[1] * v1[1] + v0[2] * v1[2]))) / 2;
  var s = Math.sin(t);
  return [Math.cos(t), (w[2] / l) * s, (-w[1] / l) * s, (w[0] / l) * s];
}

function svgEl(name, attrs) {
  var node = document.createElementNS('http://www.w3.org/2000/svg', name);
  var key;
  for (key in attrs) node.setAttribute(key, attrs[key]);
  return node;
}

function svgPointer(event, svg) {
  var ctm = svg.getScreenCTM();
  if (!ctm) return null;
  var pt = svg.createSVGPoint();
  pt.x = event.clientX;
  pt.y = event.clientY;
  var p = pt.matrixTransform(ctm.inverse());
  return [p.x, p.y];
}

function mountGlobe(nav, opts) {
  var svg = nav.querySelector('[data-tour-globe]');
  if (!svg || typeof fetch === 'undefined') return Promise.resolve(null);
  var worldSrc = (opts && opts.worldSrc) || nav.getAttribute('data-world-src') || WORLD_SRC_DEFAULT;
  return Promise.all([import(D3_GEO_SRC), import(TOPOJSON_SRC), fetch(worldSrc).then(function (res) {
    if (!res.ok) throw new Error('world map');
    return res.json();
  })]).then(function (loaded) {
    var d3geo = loaded[0];
    var topojson = loaded[1];
    var world = loaded[2];
    var projection = d3geo.geoOrthographic()
      .scale(GLOBE_SCALE_MIN)
      .translate([GLOBE_SIZE / 2, GLOBE_SIZE / 2])
      .clipAngle(90)
      .precision(0.3);
    var path = d3geo.geoPath(projection);
    var features = topojson.feature(world, world.objects.countries).features;
    var bySlug = {};
    var cx = GLOBE_SIZE / 2;
    var cy = GLOBE_SIZE / 2;
    var radius = GLOBE_SCALE_MIN;
    var defs = svgEl('defs', {});
    var clip = svgEl('clipPath', { id: 'tour-globe-clip' });
    clip.appendChild(svgEl('circle', { cx: String(cx), cy: String(cy), r: String(radius) }));
    defs.appendChild(clip);
    var disk = svgEl('circle', {
      class: 'tour-country-ocean',
      cx: String(cx),
      cy: String(cy),
      r: String(radius),
    });
    var stage = svgEl('g', { 'clip-path': 'url(#tour-globe-clip)' });
    var graticule = svgEl('path', { class: 'tour-country-graticule' });
    var land = svgEl('g', { class: 'tour-country-land' });
    var badges = svgEl('g', { class: 'tour-country-badges' });
    var outline = svgEl('circle', {
      class: 'tour-country-sphere',
      cx: String(cx),
      cy: String(cy),
      r: String(radius),
    });
    var i;
    svg.appendChild(defs);
    svg.appendChild(disk);
    stage.appendChild(graticule);
    stage.appendChild(land);
    for (i = 0; i < features.length; i++) {
      var feat = features[i];
      var slug = featureCountrySlug(feat.properties && feat.properties.name);
      var node = svgEl('path', { 'data-slug': slug });
      node._feat = feat;
      land.appendChild(node);
      if (slug) bySlug[slug] = feat;
    }
    stage.appendChild(badges);
    svg.appendChild(stage);
    svg.appendChild(outline);

    var selected = '';
    var counts = {};
    var dragging = false;
    var moved = 0;
    var pressedSlug = '';
    var v0;
    var r0;
    var q0;

    function postedFeatures() {
      var list = [];
      var key;
      for (key in counts) {
        if (counts[key] && bySlug[key]) list.push(bySlug[key]);
      }
      return list;
    }

    function aim(slug) {
      var feat = slug ? bySlug[slug] : null;
      if (feat) {
        var c = d3geo.geoCentroid(feat);
        projection.rotate([-c[0], -c[1]]);
        return;
      }
      var feats = postedFeatures();
      if (!feats.length) return;
      var center = d3geo.geoCentroid({ type: 'FeatureCollection', features: feats });
      projection.rotate([-center[0], -center[1]]);
    }

    function render() {
      graticule.setAttribute('d', path(d3geo.geoGraticule10()) || '');
      var nodes = land.querySelectorAll('[data-slug]');
      var n;
      for (n = 0; n < nodes.length; n++) {
        var countryPath = nodes[n];
        var countrySlugValue = countryPath.getAttribute('data-slug');
        var count = countrySlugValue ? counts[countrySlugValue] || 0 : 0;
        var on = countrySlugValue !== '' && countrySlugValue === selected;
        countryPath.setAttribute('d', path(countryPath._feat) || '');
        countryPath.classList.toggle('has-posts', count > 0);
        countryPath.classList.toggle('is-current', on);
      }
      while (badges.firstChild) badges.removeChild(badges.firstChild);
      var key;
      for (key in counts) {
        if (!counts[key] || !bySlug[key]) continue;
        var xy = projection(d3geo.geoCentroid(bySlug[key]));
        if (!xy || !isFinite(xy[0]) || !isFinite(xy[1])) continue;
        var g = svgEl('g', {
          class: 'tour-country-badge' + (key === selected ? ' is-current' : ''),
          transform: 'translate(' + xy[0] + ' ' + xy[1] + ')',
          'pointer-events': 'none',
        });
        g.appendChild(svgEl('circle', { r: '16' }));
        var text = svgEl('text', { 'text-anchor': 'middle', 'dominant-baseline': 'central' });
        text.textContent = String(counts[key]);
        g.appendChild(text);
        badges.appendChild(g);
      }
    }

    function pickCountry(target) {
      var node = target && target.closest ? target.closest('[data-slug]') : null;
      if (!node || !node.classList.contains('has-posts')) return '';
      return node.getAttribute('data-slug') || '';
    }

    svg.addEventListener('pointerdown', function (event) {
      if (event.button != null && event.button !== 0) return;
      var pt = svgPointer(event, svg);
      if (!pointOnGlobe(pt, cx, cy, radius)) return;
      var inv = pt && projection.invert(pt);
      if (!inv) return;
      dragging = true;
      moved = 0;
      pressedSlug = pickCountry(event.target);
      svg.setPointerCapture(event.pointerId);
      v0 = versorCartesian(inv);
      r0 = projection.rotate();
      q0 = versorFromAngles(r0);
      svg.classList.add('is-dragging');
    });
    svg.addEventListener('pointermove', function (event) {
      if (!dragging) return;
      moved += Math.abs(event.movementX) + Math.abs(event.movementY);
      var pt = svgPointer(event, svg);
      var inv = pt && projection.rotate(r0).invert(pt);
      if (!inv) return;
      var v1 = versorCartesian(inv);
      projection.rotate(versorToAngles(versorMultiply(q0, versorDelta(v0, v1))));
      render();
    });
    function endDrag(event) {
      if (!dragging) return;
      dragging = false;
      svg.classList.remove('is-dragging');
      if (event && svg.hasPointerCapture && svg.hasPointerCapture(event.pointerId)) {
        svg.releasePointerCapture(event.pointerId);
      }
    }
    svg.addEventListener('pointerup', function (event) {
      var slug = moved < 6 ? pressedSlug : '';
      pressedSlug = '';
      endDrag(event);
      if (slug && opts && opts.onSelect) opts.onSelect(slug);
    });
    svg.addEventListener('pointercancel', endDrag);
    svg.addEventListener('wheel', function (event) {
      var pt = svgPointer(event, svg);
      if (!pointOnGlobe(pt, cx, cy, radius)) return;
      event.preventDefault();
      var factor = event.deltaY > 0 ? 1 / GLOBE_ZOOM_STEP : GLOBE_ZOOM_STEP;
      projection.scale(clampGlobeScale(projection.scale() * factor));
      render();
    }, { passive: false });

    render();
    return {
      sync: function (nextSelected, nextCounts, syncOpts) {
        selected = countrySlug(nextSelected);
        counts = nextCounts || {};
        if (!syncOpts || syncOpts.aim !== false) aim(selected);
        render();
      },
      zoomBy: function (factor) {
        var n = Number(factor);
        if (!isFinite(n) || n <= 0) return;
        projection.scale(clampGlobeScale(projection.scale() * n));
        render();
      },
    };
  }).catch(function () {
    return null;
  });
}

function initTourCountry(root) {
  var doc = root || (typeof document === 'undefined' ? null : document);
  if (!doc) return;
  var nav = doc.querySelector('[data-tour-country-nav]');
  if (!nav) return;
  var catalog = readCatalog(nav);
  var counts = countByCountry(catalog.posts);
  var select = nav.querySelector('[data-tour-country-select]');
  var countEl = nav.querySelector('[data-tour-count]');
  var zoomIn = nav.querySelector('[data-tour-zoom-in]');
  var zoomOut = nav.querySelector('[data-tour-zoom-out]');
  var isIndex = nav.hasAttribute('data-tour-index') || catalog.listPage;
  var selected = countryFromSearch((typeof location !== 'undefined' && location.search) || '');
  var globe = null;

  function setCountry(next, opts) {
    selected = countrySlug(next);
    var n = counts[selected] || 0;
    if (select) select.value = selected;
    if (countEl) {
      countEl.hidden = !selected;
      countEl.textContent = countLabel(selected, n);
    }
    if (globe) globe.sync(selected, counts, { aim: !opts || opts.aim !== false });
    if (isIndex) {
      applyIndexFilter(selected);
      var url = tourListUrl(selected, catalog.base);
      if (opts && opts.push !== false && typeof history !== 'undefined' && history.pushState) {
        var here = location.pathname + location.search;
        if (here !== url) history.pushState({ country: selected }, '', url);
      }
    }
  }

  if (select) {
    var options = select.options;
    for (var i = 0; i < options.length; i++) {
      var value = options[i].value;
      if (!value) continue;
      options[i].textContent = optionLabel(value, counts[value] || 0);
    }
    select.addEventListener('change', function () {
      setCountry(select.value);
    });
  }

  function bumpZoom(factor) {
    if (globe && globe.zoomBy) globe.zoomBy(factor);
  }
  if (zoomIn) {
    zoomIn.addEventListener('click', function () {
      bumpZoom(GLOBE_ZOOM_STEP);
    });
  }
  if (zoomOut) {
    zoomOut.addEventListener('click', function () {
      bumpZoom(1 / GLOBE_ZOOM_STEP);
    });
  }

  if (isIndex && typeof window !== 'undefined') {
    window.addEventListener('popstate', function () {
      setCountry(countryFromSearch(location.search), { push: false });
    });
  }

  setCountry(selected, { push: false, aim: false });
  mountGlobe(nav, {
    onSelect: function (slug) {
      setCountry(slug);
    },
  }).then(function (api) {
    globe = api;
    if (globe) globe.sync(selected, counts, { aim: true });
  });
}

initTourCountry();
