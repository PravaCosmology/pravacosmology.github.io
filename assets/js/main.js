/* =========================================================================
   Cosmology & Statistical Physics Group — site behaviour
   No dependencies. Sections:
     1. helpers   2. theme   3. navigation   4. reveal + counters
     5. starfield 6. CMB globe   7. publications filter   8. news filter
     9. highlights toggle   10. gallery lightbox   11. maths (KaTeX, loaded only if needed)
   ========================================================================= */
(function () {
  'use strict';

  /* ---------- 1. helpers ---------- */
  var doc = document, root = doc.documentElement;
  var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  function $(s, c) { return (c || doc).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); }
  function on(el, ev, fn, opt) { if (el) el.addEventListener(ev, fn, opt || false); }

  /* ---------- 2. theme ---------- */
  var KEY = 'csp-theme';
  function applyTheme(t, save) {
    root.setAttribute('data-theme', t);
    if (save) { try { localStorage.setItem(KEY, t); } catch (e) {} }
    doc.dispatchEvent(new Event('themechange'));
  }
  on($('#theme'), 'click', function () {
    applyTheme(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light', true);
  });

  /* ---------- 3. navigation ---------- */
  var nav = $('#nav');
  function onScroll() { if (nav) nav.classList.toggle('scrolled', window.scrollY > 8); }
  on(window, 'scroll', onScroll, { passive: true }); onScroll();
  var burger = $('#burger');
  on(burger, 'click', function () {
    var open = nav.classList.toggle('open');
    burger.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  $$('.dd > button').forEach(function (b) {
    on(b, 'click', function (e) {
      e.stopPropagation();
      var dd = b.parentNode, o = dd.classList.toggle('open');
      b.setAttribute('aria-expanded', o ? 'true' : 'false');
    });
  });
  on(doc, 'click', function () { $$('.dd.open').forEach(function (d) { d.classList.remove('open'); }); });
  on(doc, 'keydown', function (e) {
    if (e.key === 'Escape') {
      $$('.dd.open').forEach(function (d) { d.classList.remove('open'); });
      if (nav) nav.classList.remove('open');
    }
  });

  /* ---------- 4. reveal + counters ---------- */
  function reveal() {
    var els = $$('.reveal');
    if (!('IntersectionObserver' in window) || reduce) { els.forEach(function (e) { e.classList.add('in'); }); return; }
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    els.forEach(function (e) { io.observe(e); });
  }
  function counters() {
    var els = $$('[data-count]');
    if (!els.length) return;
    function run(el) {
      var end = parseFloat(el.getAttribute('data-count')) || 0, t0 = null, dur = 1500;
      var suffix = el.getAttribute('data-suffix') || '';
      function step(t) {
        if (t0 === null) t0 = t;
        var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(end * e).toLocaleString('en-US') + suffix;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }
    if (!('IntersectionObserver' in window) || reduce) return;
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) { if (en.isIntersecting) { run(en.target); io.unobserve(en.target); } });
    }, { threshold: 0.6 });
    els.forEach(function (e) { e.textContent = '0' + (e.getAttribute('data-suffix') || ''); io.observe(e); });
  }

  /* ---------- 5. starfield ---------- */
  function starfield() {
    var c = $('#stars'); if (!c || !c.getContext) return;
    var ctx = c.getContext('2d'), W = 0, H = 0, dpr = 1, S = [], raf = 0, visible = true;
    function seed() {
      var n = Math.min(260, Math.round(W * H / 8500)); S = [];
      for (var i = 0; i < n; i++) {
        var z = Math.random();
        S.push({ x: Math.random() * W, y: Math.random() * H, z: z, r: 0.25 + Math.pow(Math.random(), 3) * 1.25,
                 a: 0.25 + Math.random() * 0.75, p: Math.random() * 6.283, s: 0.4 + Math.random() * 1.4,
                 c: Math.random() < 0.14 ? '#ffd9a0' : (Math.random() < 0.25 ? '#a9c8ff' : '#e6eeff') });
      }
    }
    function size() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth; H = window.innerHeight;
      c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); seed(); draw(0);
    }
    function draw(t) {
      ctx.clearRect(0, 0, W, H);
      if (root.getAttribute('data-theme') === 'light') return;
      var sy = window.scrollY || 0;
      for (var i = 0; i < S.length; i++) {
        var s = S[i], tw = 0.55 + 0.45 * Math.sin(t * 0.001 * s.s + s.p);
        var y = (s.y - sy * (0.03 + s.z * 0.12)) % H; if (y < 0) y += H;
        ctx.globalAlpha = s.a * tw; ctx.fillStyle = s.c;
        ctx.beginPath(); ctx.arc(s.x, y, s.r, 0, 6.2832); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    function loop(t) { draw(t); raf = visible ? requestAnimationFrame(loop) : 0; }
    size();
    on(window, 'resize', size);
    on(doc, 'themechange', function () { draw(0); });
    if (reduce) { on(window, 'scroll', function () { draw(0); }, { passive: true }); return; }
    on(doc, 'visibilitychange', function () {
      visible = !doc.hidden; if (visible && !raf) raf = requestAnimationFrame(loop);
    });
    raf = requestAnimationFrame(loop);
  }

  /* ---------- 6. CMB globe ----------
     A synthetic Gaussian random field on the sphere (sum of random plane waves
     restricted to the unit sphere — statistically isotropic), coloured with a
     CMB-style palette and drawn as a rotating, draggable orthographic globe.
     Purely illustrative: it is NOT real data. ------------------------------ */
  function globe() {
    var cv = $('#globe'); if (!cv || !cv.getContext) return;
    var GW = 512, GH = 256, TAU = 6.283185307179586, PI = Math.PI;
    var field = new Uint8Array(GW * GH), ready = false;
    var ctx = cv.getContext('2d'), N = 0, img, buf, lon, row, sh, rm;
    var spin = 0.6, tilt = 0.32, vel = 0, dirty = true, dragging = false, lastX = 0, lastY = 0;
    var running = false, inView = true, frameSkip = 0, slow = 0;

    /* seeded random numbers: same sky every visit */
    var seed = 20261108;
    function rnd() {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    }
    function gauss() { return Math.sqrt(-2 * Math.log(1 - rnd())) * Math.cos(TAU * rnd()); }

    /* palette: deep blue -> blue -> pale cyan -> cream -> amber -> red */
    var stops = [[0, 7, 10, 46], [.17, 20, 51, 143], [.35, 42, 127, 214], [.5, 138, 211, 236],
                 [.62, 246, 236, 190], [.77, 255, 179, 71], [.9, 240, 86, 60], [1, 138, 18, 48]];
    var LR = new Uint8Array(256), LG = new Uint8Array(256), LB = new Uint8Array(256);
    (function () {
      for (var i = 0; i < 256; i++) {
        var t = i / 255, k = 0; while (k < stops.length - 2 && t > stops[k + 1][0]) k++;
        var a = stops[k], b = stops[k + 1], u = (t - a[0]) / (b[0] - a[0]);
        LR[i] = a[1] + (b[1] - a[1]) * u; LG[i] = a[2] + (b[2] - a[2]) * u; LB[i] = a[3] + (b[3] - a[3]) * u;
      }
    })();

    /* modes */
    var M = 280, kx = new Float32Array(M), ky = new Float32Array(M), kz = new Float32Array(M),
        am = new Float32Array(M), ph = new Float32Array(M);
    for (var i = 0; i < M; i++) {
      var z = 2 * rnd() - 1, a = TAU * rnd(), r = Math.sqrt(1 - z * z);
      var k = Math.exp(Math.log(30) + 0.5 * gauss()); k = k < 3 ? 3 : k > 130 ? 130 : k;   /* band-limited: blobs of a few degrees */
      kx[i] = k * r * Math.cos(a); ky[i] = k * z; kz[i] = k * r * Math.sin(a);
      am[i] = gauss(); ph[i] = TAU * rnd();
    }
    var raw = new Float32Array(GW * GH), jrow = 0, sum = 0, sum2 = 0;
    function computeChunk() {
      var end = Math.min(GH, jrow + 8);
      for (; jrow < end; jrow++) {
        var lat = PI / 2 - (jrow + 0.5) / GH * PI, cl = Math.cos(lat), sl = Math.sin(lat);
        for (var ii = 0; ii < GW; ii++) {
          var lo = (ii + 0.5) / GW * TAU - PI, x = cl * Math.sin(lo), z = cl * Math.cos(lo), v = 0;
          for (var m = 0; m < M; m++) v += am[m] * Math.cos(kx[m] * x + ky[m] * sl + kz[m] * z + ph[m]);
          raw[jrow * GW + ii] = v; sum += v; sum2 += v * v;
        }
      }
      if (jrow < GH) { setTimeout(computeChunk, 0); return; }
      var n = GW * GH, mean = sum / n, sd = Math.sqrt(sum2 / n - mean * mean) || 1;
      for (var q = 0; q < n; q++) {
        var t = (raw[q] - mean) / sd * 0.28 + 0.5;
        field[q] = t < 0 ? 0 : t > 1 ? 255 : (t * 255) | 0;
      }
      ready = true; cv.classList.add('ready');
      var ph0 = $('.globe-ph'); if (ph0) ph0.style.opacity = 0;
      start();
    }

    /* per-pixel projection (recomputed only on resize or when the tilt changes) */
    function setup() {
      var w = cv.clientWidth || 440, d = Math.min(window.devicePixelRatio || 1, 1.5);
      var n = Math.max(280, Math.min(480, Math.round(w * d)));
      if (n === N && img) return;
      N = n; cv.width = N; cv.height = N; img = ctx.createImageData(N, N); buf = img.data;
      lon = new Float32Array(N * N); row = new Int32Array(N * N); sh = new Float32Array(N * N); rm = new Float32Array(N * N);
      dirty = true;
    }
    function project() {
      var ct = Math.cos(tilt), st = Math.sin(tilt), R = N / 2 - 1, c0 = N / 2;
      var Lx = -0.45, Ly = 0.55, Lz = 0.70, ln = Math.sqrt(Lx * Lx + Ly * Ly + Lz * Lz); Lx /= ln; Ly /= ln; Lz /= ln;
      for (var py = 0, i = 0; py < N; py++) {
        var y = -(py + 0.5 - c0) / R;
        for (var px = 0; px < N; px++, i++) {
          var x = (px + 0.5 - c0) / R, d2 = x * x + y * y;
          if (d2 >= 1) { buf[i * 4 + 3] = 0; sh[i] = -1; continue; }
          var zv = Math.sqrt(1 - d2), yy = y * ct - zv * st, zz = y * st + zv * ct;
          lon[i] = Math.atan2(x, zz);
          var j = ((PI / 2 - Math.asin(yy)) / PI * GH) | 0; row[i] = (j < 0 ? 0 : j >= GH ? GH - 1 : j) * GW;
          var lam = x * Lx + y * Ly + zv * Lz; lam = lam > 0 ? lam : 0;
          sh[i] = 0.6 + 0.58 * lam;
          rm[i] = Math.pow(1 - zv, 3) * 110;
          var e = (1 - Math.sqrt(d2)) * R; buf[i * 4 + 3] = e >= 1 ? 255 : (e * 255) | 0;
        }
      }
      dirty = false;
    }
    function render() {
      if (dirty) project();
      var off = spin / TAU + 0.5, n = N * N, G = GW;
      for (var i = 0; i < n; i++) {
        var s = sh[i]; if (s < 0) continue;
        var u = lon[i] / TAU + off; u -= Math.floor(u);
        var c = field[row[i] + ((u * G) | 0)], o = i << 2, rr = rm[i];
        var r = LR[c] * s + rr * 0.55, g = LG[c] * s + rr * 0.8, b = LB[c] * s + rr * 1.4;
        buf[o] = r > 255 ? 255 : r; buf[o + 1] = g > 255 ? 255 : g; buf[o + 2] = b > 255 ? 255 : b;
      }
      ctx.putImageData(img, 0, 0);
    }

    /* animation loop */
    var last = 0;
    function loop(t) {
      if (!running) return;
      var dt = Math.min(64, t - last || 16); last = t;
      if (!dragging) { vel *= 0.94; spin += (reduce ? 0 : 0.00011 * dt) + vel; }
      if (dt > 28) slow++; else if (slow > 0) slow--;
      frameSkip = slow > 12 ? 1 : 0;                         /* weak device: halve frame rate */
      if (!frameSkip || (t | 0) % 2 === 0) { var t0 = performance.now(); render(); if (performance.now() - t0 > 24) slow += 2; }
      requestAnimationFrame(loop);
    }
    function start() {
      if (!ready || running) return;
      if (reduce) { render(); return; }
      running = inView && !doc.hidden; if (running) { last = 0; requestAnimationFrame(loop); }
    }
    function stop() { running = false; }

    /* interaction */
    on(cv, 'pointerdown', function (e) { dragging = true; lastX = e.clientX; lastY = e.clientY; vel = 0; try { cv.setPointerCapture(e.pointerId); } catch (x) {} });
    on(cv, 'pointermove', function (e) {
      if (!dragging) return;
      var dx = e.clientX - lastX, dy = e.clientY - lastY; lastX = e.clientX; lastY = e.clientY;
      spin -= dx * 0.008; vel = -dx * 0.0006;
      if (dy) { tilt = Math.max(-1.0, Math.min(1.0, tilt + dy * 0.006)); dirty = true; }
      if (reduce) render();
    });
    function up() { dragging = false; }
    on(cv, 'pointerup', up); on(cv, 'pointercancel', up);

    setup();
    on(window, 'resize', function () { var o = N; setup(); if (N !== o && ready) { if (reduce) render(); } });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (en) { inView = en[0].isIntersecting; inView ? start() : stop(); }).observe(cv);
    }
    on(doc, 'visibilitychange', function () { doc.hidden ? stop() : start(); });
    setTimeout(computeChunk, 30);
  }

  /* ---------- 7. publications: search, filter, sort ---------- */
  function pubs() {
    var list = $('#pub-list'); if (!list) return;
    var items = $$('.pub', list), q = $('#pub-q'), yr = $('#pub-year'), so = $('#pub-sort');
    var chips = $$('[data-person]'), bars = $$('.bar'), cnt = $('#pub-count'), emp = $('#pub-empty');
    var st = { q: '', y: '', p: '', s: 'new' };
    function cmp(a, b, k, dir) { return a.getAttribute(k) < b.getAttribute(k) ? -dir : a.getAttribute(k) > b.getAttribute(k) ? dir : 0; }
    function apply() {
      var toks = st.q.toLowerCase().split(/\s+/).filter(Boolean), shown = 0;
      items.forEach(function (it) {
        var hay = it.getAttribute('data-q') || '', ok = true;
        for (var i = 0; i < toks.length; i++) if (hay.indexOf(toks[i]) < 0) { ok = false; break; }
        if (ok && st.y && it.getAttribute('data-year') !== st.y) ok = false;
        if (ok && st.p && (' ' + it.getAttribute('data-people') + ' ').indexOf(' ' + st.p + ' ') < 0) ok = false;
        it.hidden = !ok; if (ok) shown++;
      });
      var sorted = items.slice().sort(function (a, b) {
        if (st.s === 'old') return cmp(a, b, 'data-date', 1);
        if (st.s === 'cites') {
          var d = (+b.getAttribute('data-cites')) - (+a.getAttribute('data-cites')); return d || cmp(a, b, 'data-date', -1);
        }
        return cmp(a, b, 'data-date', -1);
      });
      sorted.forEach(function (it) { list.appendChild(it); });
      if (cnt) cnt.textContent = shown + ' of ' + items.length + ' papers';
      if (emp) emp.hidden = shown !== 0;
      chips.forEach(function (c) { c.classList.toggle('on', (c.getAttribute('data-person') || '') === st.p); });
      bars.forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-year') === st.y); });
    }
    on(q, 'input', function () { st.q = q.value; apply(); });
    on(yr, 'change', function () { st.y = yr.value; apply(); });
    on(so, 'change', function () { st.s = so.value; apply(); });
    chips.forEach(function (c) { on(c, 'click', function () { st.p = c.getAttribute('data-person') || ''; apply(); }); });
    bars.forEach(function (b) {
      on(b, 'click', function () {
        var y = b.getAttribute('data-year'); st.y = st.y === y ? '' : y; if (yr) yr.value = st.y; apply();
        var t = $('#pub-q'); if (t && t.scrollIntoView) t.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
      });
    });
    on(list, 'click', function (e) {
      var t = e.target; if (t && t.classList && t.classList.contains('more-btn')) t.parentNode.classList.add('all');
    });
    try { var p = new URLSearchParams(location.search).get('q'); if (p && q) { q.value = p; st.q = p; } } catch (x) {}
    apply();
  }

  /* ---------- 8. news filter ---------- */
  function newsFilter() {
    var btns = $$('[data-kind]'); if (!btns.length) return;
    var items = $$('.tl[data-kind]');
    btns.forEach(function (b) {
      on(b, 'click', function () {
        var k = b.getAttribute('data-kind');
        btns.forEach(function (x) { x.classList.toggle('on', x === b); });
        items.forEach(function (it) { it.hidden = !!k && it.getAttribute('data-kind') !== k; });
      });
    });
  }

  /* ---------- 9. highlight abstract toggle ---------- */
  function highlights() {
    $$('.hl .toggle').forEach(function (b) {
      on(b, 'click', function () {
        var card = b.closest('.hl'), o = card.classList.toggle('open');
        b.textContent = o ? 'Show less' : 'Read abstract';
      });
    });
  }

  /* ---------- 10. gallery lightbox ---------- */
  function lightbox() {
    var shots = $$('.shot'); if (!shots.length) return;
    var lb = doc.createElement('div'); lb.className = 'lb'; lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-modal', 'true');
    lb.innerHTML = '<button class="x" aria-label="Close">&times;</button><button class="p" aria-label="Previous">&#8249;</button>' +
      '<figure><img alt=""><figcaption></figcaption></figure><button class="n" aria-label="Next">&#8250;</button>';
    doc.body.appendChild(lb);
    var im = $('img', lb), cap = $('figcaption', lb), idx = 0;
    function show(i) {
      idx = (i + shots.length) % shots.length; var s = shots[idx];
      im.src = s.getAttribute('data-src'); cap.textContent = s.getAttribute('data-cap') || '';
      lb.classList.add('open'); doc.body.style.overflow = 'hidden';
    }
    function close() { lb.classList.remove('open'); doc.body.style.overflow = ''; }
    shots.forEach(function (s, i) { on(s, 'click', function () { if (!s.classList.contains('missing')) show(i); }); });
    on($('.x', lb), 'click', close); on($('.p', lb), 'click', function () { show(idx - 1); }); on($('.n', lb), 'click', function () { show(idx + 1); });
    on(lb, 'click', function (e) { if (e.target === lb) close(); });
    on(doc, 'keydown', function (e) {
      if (!lb.classList.contains('open')) return;
      if (e.key === 'Escape') close(); if (e.key === 'ArrowLeft') show(idx - 1); if (e.key === 'ArrowRight') show(idx + 1);
    });
  }

  /* ---------- 11. maths: load KaTeX only when a title contains $...$ ---------- */
  function maths() {
    var els = $$('[data-tex]').filter(function (e) { return e.textContent.indexOf('$') > -1; });
    if (!els.length) return;
    var css = doc.createElement('link'); css.rel = 'stylesheet';
    css.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css'; doc.head.appendChild(css);
    var s = doc.createElement('script'); s.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js';
    s.onload = function () {
      var a = doc.createElement('script'); a.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js';
      a.onload = function () {
        els.forEach(function (e) {
          try { window.renderMathInElement(e, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }], throwOnError: false }); } catch (x) {}
        });
      };
      doc.head.appendChild(a);
    };
    doc.head.appendChild(s);
  }

  /* ---------- go ---------- */
  function init() {
    reveal(); counters(); starfield(); globe(); pubs(); newsFilter(); highlights(); lightbox(); maths();
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', init); else init();
})();
