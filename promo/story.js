// The cartoon. Everything on screen is a function of the time t: render.py asks for a frame and takes a screenshot.
// Characters are the game's own pictures (art/), the phone shows the real game filmed by capture.py (frames/).
'use strict';
const stage = document.getElementById('stage');
const INK = '#3a2a80', TITLE_COLORS = ['#6d4ee8', '#3faf4a', '#f08a1d', '#e8456f', '#2f9bdc', '#6d4ee8', '#3faf4a'];
const LEN = 64;                                         // seconds; 120 beats a minute, a bar is 2 s, cuts fall on bars

// ---------------------------------------------------------------- time helpers
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const eOut = x => 1 - (1 - clamp(x)) ** 3;
const eIn = x => clamp(x) ** 2;
const eIO = x => { x = clamp(x); return x < .5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2; };
const back = x => { x = clamp(x) - 1; return 1 + 2.7 * x ** 3 + 1.7 * x ** 2; };
const rnd = i => { const s = Math.sin(i * 127.1 + 11.7) * 43758.5453; return s - Math.floor(s); };
function key(t, pts, ease = eIO) {
  if (t <= pts[0][0]) return pts[0][1];
  for (let i = 1; i < pts.length; i++) if (t <= pts[i][0]) { const [a, va] = pts[i - 1], [b, vb] = pts[i]; return lerp(va, vb, ease((t - a) / (b - a))); }
  return pts[pts.length - 1][1];
}
// a hop at each of the times: how high it is now and how the body squashes
function hops(t, times, height = 90, dur = .42) {
  let y = 0, sx = 1, sy = 1;
  for (const t0 of times) {
    const u = (t - t0) / dur;
    if (u > -.14 && u < 0) { const q = 1 - Math.abs(u / .07 + 1); sy *= 1 - .1 * q; sx *= 1 + .08 * q; }
    if (u >= 0 && u <= 1) { y = Math.max(y, height * 4 * u * (1 - u)); const s = Math.sin(u * Math.PI); sy *= 1 + .07 * s; sx *= 1 - .05 * s; }
    if (u > 1 && u < 1.35) { const q = Math.sin((u - 1) / .35 * Math.PI); sy *= 1 - .09 * q; sx *= 1 + .08 * q; }
  }
  return { y, sx, sy };
}
const beats = (a, b, step = .5) => { const r = []; for (let x = a; x < b - 1e-6; x += step) r.push(x); return r; };

// ---------------------------------------------------------------- the pool of things on stage
const pool = new Map(); let used, pending;
function el(id, make) {
  let e = pool.get(id);
  if (!e) { e = make(); stage.appendChild(e); pool.set(id, e); }
  used.add(id); e.style.display = e.dataset.disp || 'block';
  return e;
}
function setSrc(img, src) { if (img.dataset.src !== src) { img.dataset.src = src; img.src = src; pending.push(img.decode().catch(() => {})); } }
const aspect = k => SIZES[k][0] / SIZES[k][1];
function spr(id, k, p) {
  if (!(p.h >= 1) || (p.sx !== undefined && Math.abs(p.sx) < .01)) return;
  const e = el(id, () => { const i = new Image(); i.className = 'a'; return i; });
  setSrc(e, `art/${k}.png`);
  const h = p.h, w = h * aspect(k), ox = p.ox ?? .5, oy = p.oy ?? 1;
  e.style.width = w + 'px'; e.style.height = h + 'px';
  e.style.transformOrigin = `${ox * 100}% ${oy * 100}%`;
  e.style.transform = `translate(${p.x - w * ox}px, ${p.y - h * oy}px) rotate(${p.r || 0}deg) scale(${(p.flip ? -1 : 1) * (p.sx ?? 1)}, ${p.sy ?? 1})`;
  e.style.opacity = p.o ?? 1; e.style.zIndex = p.z ?? Math.round(12 + p.y / 100);
  e.style.clipPath = p.clip ? `inset(0 0 ${p.clip * 100}% 0)` : '';
}
function svgSpr(id, svg, p) {
  if (!(p.h >= 1) || (p.sx !== undefined && Math.abs(p.sx) < .01 && !svg.includes('r="10.5"'))) return;
  const e = el(id, () => { const d = document.createElement('div'); d.className = 'a'; d.innerHTML = svg; d.firstChild.style.cssText = 'width:100%;height:100%;display:block'; return d; });
  const h = p.h, w = p.w ?? h, ox = p.ox ?? .5, oy = p.oy ?? 1;
  e.style.width = w + 'px'; e.style.height = h + 'px';
  e.style.transformOrigin = `${ox * 100}% ${oy * 100}%`;
  e.style.transform = `translate(${p.x - w * ox}px, ${p.y - h * oy}px) rotate(${p.r || 0}deg) scale(${(p.flip ? -1 : 1) * (p.sx ?? 1)}, ${p.sy ?? 1})`;
  e.style.opacity = p.o ?? 1; e.style.zIndex = p.z ?? Math.round(12 + p.y / 100);
}

// a flying thing with flapping wings, as in the game (FLAP is its table); x, y — the middle of the body
const FLAP = {
  moth: { hz: 6, amp: 28, base: -6, s: [-1, 1] }, butter: { hz: 5, amp: 30, base: -8, s: [-1, 1] },
  fly: { hz: 12, amp: 22, base: 4, s: [.8, 1], front: [1] }, mosquito: { hz: 14, amp: 24, base: -4, s: [-1, 1] },
  dragon: { hz: 10, amp: 16, base: 0, s: [-1, -1, 1, 1], ph: [0, 1.6, 0, 1.6] }, bee: { hz: 14, amp: 24, base: 0, s: [-1, 1] },
  firefly: { hz: 8, amp: 20, base: 0, s: [-1, -1, 1, 1], ph: [0, 1.2, 0, 1.2] }, bug: { hz: 12, amp: 20, base: 0, s: [.8, 1], front: [1] },
};
const FACE_L = new Set(['fly', 'bug', 'snail', 'fish']);
function flyer(id, type, t, p) {
  const roots = ROOTS[type], F = FLAP[type];
  const e = el(id, () => {
    const d = document.createElement('div'); d.className = 'flyer';
    roots.forEach((r, i) => { const im = new Image(); setSrc(im, `art/${type}_w${i + 1}.png`); im.style.transformOrigin = `${r[0] * 100}% ${r[1] * 100}%`; im.dataset.w = i; if ((F.front || []).includes(i)) im.style.zIndex = 2; d.appendChild(im); });
    const b = new Image(); setSrc(b, `art/${type}_b.png`); b.style.zIndex = 1; d.appendChild(b);
    return d;
  });
  const h = p.h, w = h * aspect(type + '_b');
  e.style.width = w + 'px'; e.style.height = h + 'px';
  e.style.transform = `translate(${p.x - w / 2}px, ${p.y - h / 2}px) rotate(${p.r || 0}deg) scale(${(p.flip ? -1 : 1) * (p.k ?? 1)}, ${p.k ?? 1})`;
  e.style.opacity = p.o ?? 1; e.style.zIndex = p.z ?? 28;
  [...e.children].forEach(im => { if (im.dataset.w !== undefined) { const i = +im.dataset.w; im.style.transform = `rotate(${F.s[i] * (F.base + F.amp * Math.sin(t * F.hz * 6.283 + (F.ph ? F.ph[i] : i * .25)))}deg)`; } });
}
// looks to the right by default; fly and bug are drawn looking left
const facing = (type, goingRight) => FACE_L.has(type) ? goingRight : !goingRight;

function text(id, str, p) {
  const e = el(id, () => { const d = document.createElement('div'); d.className = 'tx'; d.innerHTML = '<div class="st"></div><div class="fi"></div>'; return d; });
  if (e.dataset.s !== str) {
    e.dataset.s = str;
    const html = [...str].map(c => `<span>${c === ' ' ? '&nbsp;' : c}</span>`).join('');
    e.children[0].innerHTML = html; e.children[1].innerHTML = html;
  }
  e.style.fontSize = p.size + 'px';
  const st = e.children[0].children, fi = e.children[1].children, n = fi.length;
  for (let i = 0; i < n; i++) {
    const L = p.letter ? p.letter(i, n) : null;
    const tf = L ? `translateY(${L.dy || 0}px) rotate(${L.r || 0}deg) scale(${L.s ?? 1})` : '';
    st[i].style.transform = fi[i].style.transform = tf;
    st[i].style.opacity = fi[i].style.opacity = L && L.o !== undefined ? L.o : 1;
    fi[i].style.color = p.colors ? p.colors[i % p.colors.length] : (p.color || INK);
  }
  e.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -50%) rotate(${p.r || 0}deg) scale(${p.k ?? 1})`;
  e.style.opacity = p.o ?? 1; e.style.zIndex = p.z ?? 40;
}
// x, y — the tip of the tail; tail — where along the bubble it hangs
function bubble(id, t, t0, t1, str, x, y, { tail = .5, size = 50, z = 50 } = {}) {
  if (t < t0 || t > t1) return;
  const e = el(id, () => { const d = document.createElement('div'); d.className = 'bub'; d.innerHTML = '<span></span><svg viewBox="0 0 42 30"><path d="M0 0 H42 L21 30Z" fill="#fff"/></svg>'; return d; });
  if (e.dataset.s !== str) { e.dataset.s = str; e.firstChild.textContent = str; }
  e.style.fontSize = size + 'px';
  const w = e.offsetWidth, h = e.offsetHeight, left = clamp(x - w * tail, 18, 1062 - w), top = y - h - 27;
  const tip = clamp(x - left, 40, w - 40);
  e.lastChild.style.left = tip - 21 + 'px';
  const k = back((t - t0) / .24) * (1 - eIn((t - (t1 - .16)) / .16));
  e.style.transformOrigin = `${tip}px ${h + 27}px`;
  e.style.transform = `translate(${left}px, ${top}px) scale(${k})`;
  e.style.zIndex = z;
}
function caption(t, t0, t1, l1, l2, { y1 = 118, y2 = 232, s1 = 100, s2 = 56, letter } = {}) {
  if (t < t0 || t > t1) return;
  const out = eIn((t - (t1 - .25)) / .25);
  const lt = (i, n, d) => { const u = (t - t0 - d - i * .018) / .34; return { dy: (1 - back(u)) * 60 - out * 200, s: lerp(.4, 1, back(u)), o: clamp(u * 3) * (1 - out) }; };
  const id = 'cap' + t0;
  text(id + 'a', l1, { x: 540, y: y1, size: s1, letter: (i, n) => { const a = lt(i, n, 0); if (letter) { const b = letter(i, n); a.dy += b.dy || 0; a.r = b.r || 0; } return a; } });
  if (l2) text(id + 'b', l2, { x: 540, y: y2, size: s2, color: '#5b49a8', letter: (i, n) => lt(i, n, .22) });
}

// ---------------------------------------------------------------- bits of comedy
const LEON = { h: 512, w: 377 };
function mouth(x, y, h, flip) { const w = h * aspect('leon'); return [x + (flip ? -1 : 1) * w * (.708 - .5), y - h * (1 - .623)]; }
function tongue(from, to) {
  const e = document.getElementById('tongue'); e.style.display = 'block'; used.add('#tongue');
  const [l, c] = e.children;
  l.setAttribute('x1', from[0]); l.setAttribute('y1', from[1]); l.setAttribute('x2', to[0]); l.setAttribute('y2', to[1]);
  c.setAttribute('cx', to[0]); c.setAttribute('cy', to[1]);
}
// Leon's tongue at a moment t0: .17 s out, .26 s back with the prey. Returns where the prey is, null if not yet touched,
// 'gone' once it is eaten
function zap(t, t0, m, prey) {
  const u = t - t0;
  if (u < 0) return null;
  if (u < .17) { tongue(m, [lerp(m[0], prey[0], u / .17), lerp(m[1], prey[1], u / .17)]); return null; }
  if (u < .43) { const k = eIO((u - .17) / .26), p = [lerp(prey[0], m[0], k), lerp(prey[1], m[1], k)]; tongue(m, p); return { p, k: 1 - .6 * k }; }
  return 'gone';
}
function confetti(id, t, t0, x, y, n = 40, power = 700) {
  const u = t - t0;
  if (u < 0 || u > 2.2) return;
  const cols = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff', '#b06bff', '#ff8fd8'];
  for (let i = 0; i < n; i++) {
    const e = el(`${id}${i}`, () => { const d = document.createElement('div'); d.className = 'fx'; return d; });
    const a = rnd(i * 3 + 1) * 6.283, v = power * (.35 + .65 * rnd(i * 7 + 2));
    const px = x + Math.cos(a) * v * u, py = y + (Math.sin(a) * v - 240) * u + 620 * u * u;
    e.style.width = 14 + 'px'; e.style.height = 24 + 'px'; e.style.background = cols[i % cols.length]; e.style.borderRadius = '4px';
    e.style.transform = `translate(${px}px, ${py}px) rotate(${u * 500 * (rnd(i) - .5) * 2}deg) scaleX(${Math.cos(u * 9 + i)})`;
    e.style.opacity = 1 - eIn((u - 1.5) / .7); e.style.zIndex = 46;
  }
}
function firework(id, t, t0, x, y) {
  const u = (t - t0) / 1.25;
  if (u < 0 || u > 1) return;
  const cols = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff', '#b06bff', '#ff8fd8'];
  for (let i = 0; i < 26; i++) {
    const e = el(`${id}${i}`, () => { const d = document.createElement('div'); d.className = 'fx'; return d; });
    const a = i / 26 * 6.283, r = 230 * eOut(u) * (.75 + .25 * rnd(i));
    e.style.width = e.style.height = 22 + 'px'; e.style.borderRadius = '50%'; e.style.background = cols[i % 6];
    e.style.transform = `translate(${x + Math.cos(a) * r}px, ${y + Math.sin(a) * r + 90 * u * u}px) scale(${1 - .5 * u})`;
    e.style.opacity = 1 - eIn((u - .55) / .45); e.style.zIndex = 46;
  }
}
const COIN = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#ffc93c" stroke="#d99a00" stroke-width="2"/><circle cx="12" cy="12" r="7" fill="none" stroke="#ffe08a" stroke-width="1.5"/><path d="M12 7.2 L13.4 10.4 L16.8 10.6 L14.2 12.8 L15 16.2 L12 14.4 L9 16.2 L9.8 12.8 L7.2 10.6 L10.6 10.4Z" fill="#e3a000"/></svg>';
function coinRain(t, t0, t1, n = 40) {
  for (let i = 0; i < n; i++) {
    const s = t0 + i * (t1 - t0 - 1) / n, u = t - s;
    if (u < 0 || t > t1 + .3) continue;
    const x0 = 40 + rnd(i * 5 + 3) * 1000, g = 1900, floor = 1760 + rnd(i) * 130;
    let y = -60 + 240 * u + g * u * u / 2, x = x0 + (rnd(i * 2) - .5) * 160 * u;
    const hit = (-240 + Math.sqrt(240 * 240 + 2 * g * (floor + 60))) / g;
    if (u > hit) { const v = (240 + g * hit) * .42, q = u - hit, b = 2 * v / g, q2 = q % b; y = floor - (v * q2 - g * q2 * q2 / 2) * Math.max(0, 1 - Math.floor(q / b) * .6); }
    svgSpr('coin' + i, COIN, { x, y, h: 90, ox: .5, oy: .5, sx: Math.cos(t * 7 + i), z: 38, o: 1 - eIn((t - t1) / .3) });
  }
}
const PIECE = (t, c) => {
  const F = c === 'w' ? '#ffffff' : '#463c6e', S = c === 'w' ? '#2d2550' : '#140f2b';
  const a = `fill="${F}" stroke="${S}" stroke-width="2" stroke-linejoin="round"`;
  const base = `<rect x="10" y="32" width="25" height="7" rx="3" ${a}/>`;
  const g = {
    P: `<circle cx="22.5" cy="13" r="6.5" ${a}/><path d="M15.5 32 C15.5 25 18.5 21 22.5 21 C26.5 21 29.5 25 29.5 32Z" ${a}/>${base}`,
    R: `<path d="M12 8 h5 v4 h3.5 v-4 h4 v4 h3.5 v-4 h5 v9 h-21 z" ${a}/><path d="M15 17 h15 l1.5 15 h-18 z" ${a}/>${base}`,
    Q: `<path d="M9 15 L14 31 H31 L36 15 L28.5 23 L22.5 11 L16.5 23 Z" ${a}/><circle cx="9" cy="13" r="2.8" ${a}/><circle cx="22.5" cy="9" r="2.8" ${a}/><circle cx="36" cy="13" r="2.8" ${a}/>${base}`,
    K: `<path d="M22.5 3.5 v9 M18.5 7.5 h8" stroke="${S}" stroke-width="3.2" stroke-linecap="round"/><path d="M22.5 3.5 v9 M18.5 7.5 h8" stroke="${F}" stroke-width="1.2" stroke-linecap="round"/><path d="M12 20 C12 13 22.5 13 22.5 19 C22.5 13 33 13 33 20 C33 25 29 28 29 32 H16 C16 28 12 25 12 20Z" ${a}/>${base}`,
    N: `<path d="M14 39 L14 31 C14 26 18 23 21 20 C17 21.5 13 23.5 10.5 21.5 C8.5 19.5 10.5 15 15 12 L17.5 6.5 L21 10 C28.5 9.5 33.5 15.5 33.5 24 L33.5 39Z" ${a}/><circle cx="18.5" cy="14.5" r="1.8" fill="${c === 'w' ? '#2d2550' : '#efeaff'}"/>${base}`,
    B: `<circle cx="22.5" cy="7" r="3" ${a}/><path d="M22.5 10 C30.5 15 31.5 22 27.5 27.5 L17.5 27.5 C13.5 22 14.5 15 22.5 10Z" ${a}/><path d="M16 27.5 h13 l1.5 4.5 h-16z" ${a}/>${base}`,
  }[t];
  return `<svg viewBox="0 0 45 45" xmlns="http://www.w3.org/2000/svg">${g}</svg>`;
};
const JAR = '<svg viewBox="0 0 300 400"><defs><linearGradient id="gl" x1="0" x2="1"><stop offset="0" stop-color="#e3f6ff" stop-opacity=".78"/><stop offset=".5" stop-color="#ffffff" stop-opacity=".3"/><stop offset="1" stop-color="#cdeaff" stop-opacity=".78"/></linearGradient></defs><path d="M62 60 C14 86 14 118 14 150 V340 C14 378 44 396 80 396 H220 C256 396 286 378 286 340 V150 C286 118 286 86 238 60 Z" fill="url(#gl)" stroke="#9fd2ee" stroke-width="7"/><path d="M50 140 C40 190 40 280 52 340" stroke="#fff" stroke-width="16" stroke-linecap="round" fill="none" opacity=".85"/><rect x="50" y="28" width="200" height="38" rx="14" fill="#d8efff" stroke="#9fd2ee" stroke-width="6"/></svg>';
const LID = '<svg viewBox="0 0 230 70"><rect x="6" y="6" width="218" height="58" rx="20" fill="#ff9f43" stroke="#d97a1a" stroke-width="6"/><rect x="24" y="16" width="120" height="12" rx="6" fill="#ffd9a8"/></svg>';

// ---------------------------------------------------------------- the phone
const PHONE_TOP = 492;
const FILMS = [                                         // take, from, to (video time), offset in the take
  ['rook', 12.3, 20.2, 0], ['menu', 20, 26.2, 0], ['mini', 26, 30.2, 0], ['result', 30, 34.4, 0],
  ['feed', 42.2, 46.2, 3.2], ['shop', 46, 48.7, 0], ['drum', 48.5, 52.4, 0],
];
const pad5 = n => String(n).padStart(5, '0');
function phone(t) {
  const e = document.getElementById('phone');
  const y = key(t, [[12, 2100], [12.5, PHONE_TOP], [34, PHONE_TOP], [34.45, 2100], [42, 2100], [42.45, PHONE_TOP], [52, PHONE_TOP], [52.45, 2100]],
    x => x < .5 ? eIO(x) : back(x));
  if (y >= 2000) { e.style.display = 'none'; return; }
  e.style.display = 'block'; used.add('#phone');
  e.style.transform = `translateY(${y}px) rotate(${key(t, [[12, -4], [12.5, 0]])}deg)`;
  const live = FILMS.filter(f => t >= f[1] && t <= f[2]);
  const [a, b] = [document.getElementById('f1'), document.getElementById('f2')];
  const frame = f => `frames/${f[0]}/${pad5(Math.min(TAKES[f[0]] - 1, Math.round((t - f[1] + f[3]) * 30)))}.jpg`;
  if (live.length) { setSrc(a, frame(live[0])); a.style.opacity = 1; }
  if (live.length > 1) { setSrc(b, frame(live[1])); b.style.display = 'block'; b.style.opacity = clamp((t - live[1][1]) / .2); } else b.style.display = 'none';
}

// ---------------------------------------------------------------- the actors
const TURTLE_X = t => lerp(-130, 705, clamp((t - 10) / 51.5));   // she crawls through the whole film and is just in time
function turtle(t) {
  if (t < 10) return;
  spr('turtle', 'turtle', { x: TURTLE_X(t), y: 1905, h: 178, flip: false, sx: 1 + .02 * Math.sin(t * 5), sy: 1 - .02 * Math.sin(t * 5), r: 1.5 * Math.sin(t * 2.5), z: 37 });
}

function leonPose(t) {
  const x = key(t, [[0, 430], [4.1, 430], [4.7, 540], [11.8, 540], [12.4, 128], [34, 128], [34.4, 165], [42, 165], [42.4, 128], [52, 128], [52.5, 420]]);
  const y = key(t, [[0, 2790], [1.9, 2790], [2.55, 2300], [3.0, 2300], [3.12, 2120], [4.0, 2120], [4.6, 1875], [11.8, 1875], [12.4, 1905], [52, 1905], [52.5, 1890], [58, 1890], [58.5, 1880]]);
  const h = key(t, [[0, 780], [4, 780], [4.6, 780], [11.8, 780], [12.4, 400], [34, 400], [34.4, 470], [42, 470], [42.4, 400], [52, 400], [52.5, 560], [58, 560], [58.5, 700]]);
  return { x, y, h };
}
const ZAPS = [                                           // tongue: when, and what it catches (a function of time)
  { t0: 3.18, to: t => FLY1(t) },
  { t0: 18.55, to: t => FLY2(t) },
  { t0: 36.5, to: t => FLYR('fly', t) },
  { t0: 38.2, to: t => FLYR('butter', t) },
  { t0: 39.8, to: t => FLYR('mosquito', t) },
  { t0: 62.75, to: t => FLY3(t) },
];
function leon(t) {
  const P = leonPose(t);
  const H = hops(t, [4.05, 7.5, 8.75, 21, 23, 30.2, 31, 32, 33, 34.1, 37.1, 38.8, 40.4, 49.9, ...beats(58.5, 61, 1), 61.7, 62.2, 62.25], 70 + P.h * .08);
  const zapNow = ZAPS.find(z => t >= z.t0 - .22 && t <= z.t0 + .5);
  const m = mouth(P.x, P.y - H.y, P.h, false);
  const eat = !!zapNow && t <= zapNow.t0 + .46;
  let r = 0;
  if (t >= 46.4 && t < 49.8) r = 3 * Math.sin((t - 46.4) * 6.283 * 2);    // drums
  spr('leon', eat ? 'leonEat' : 'leon', { x: P.x, y: P.y - H.y, h: P.h, sx: H.sx * (1 + .012 * Math.sin(t * 3.2)), sy: H.sy * (1 - .012 * Math.sin(t * 3.2)), r, z: t < 4 ? 30 : 32 });
  return { m, P, H };
}

// the fly of the beginning
const FLY1 = t => { const c = eIO((t - 2.2) / 1); return [lerp(lerp(-120, 690, eOut((t - .7) / 1.5)) + 90 * Math.sin(t * 3.1), 935, c), lerp(760 + 140 * Math.sin(t * 2.3), 1245, c) + 26 * Math.sin(t * 11) * (1 - c * .6)]; };
// the fly that gets out of the phone
const FLY2 = t => { const u = clamp((t - 17.55) / 1); return [lerp(560, 420, eIO(u)) + 26 * Math.sin(t * 7) * (1 - u * .7), lerp(1010, 1470, eIO(u)) + 30 * Math.sin(t * 9) * (1 - u * .7)]; };
// the last fly
const FLY3 = t => { const u = clamp((t - 61.6) / 1.1); return [lerp(1180, 885, eOut(u)) + 26 * Math.sin(t * 5), 1255 + 36 * Math.sin(t * 7)]; };

function s1(t, L) {                                      // 0–4: «it's boring»; Leon eats the fly and everything gets colour
  const out = t >= 4 ? (t - 4) : 0;
  if (t < 5.3) {
    const k = 1 - eIn(out / .6), y = 1035 + 1500 * eIn(out / 1.1);
    const e = el('board', () => {
      const d = document.createElement('div'); d.className = 'a'; d.style.borderRadius = '22px'; d.style.overflow = 'hidden'; d.style.boxShadow = '0 18px 40px #3a2a8033';
      d.style.display = 'grid'; d.dataset.disp = 'grid'; d.style.gridTemplateColumns = 'repeat(8,1fr)';
      for (let i = 0; i < 64; i++) { const s = document.createElement('div'); s.style.background = (i + (i >> 3)) % 2 ? '#a99be0' : '#f3efff'; d.appendChild(s); }
      return d;
    });
    e.style.width = e.style.height = '780px';
    e.style.transformOrigin = '50% 50%'; e.style.transform = `translate(150px, ${y - 390}px) rotate(${-3 + 18 * eIn(out / 1)}deg)`; e.style.opacity = k; e.style.zIndex = 12;
    const P = [['K', 'w', 4, 7], ['Q', 'w', 3, 7], ['R', 'w', 0, 7], ['N', 'w', 6, 7], ['B', 'w', 2, 7], ['P', 'w', 2, 6], ['P', 'w', 3, 6], ['P', 'w', 5, 6],
      ['K', 'b', 4, 0], ['R', 'b', 7, 0], ['N', 'b', 1, 0], ['B', 'b', 5, 0], ['P', 'b', 1, 1], ['P', 'b', 4, 1], ['P', 'b', 6, 1]];
    P.forEach(([n, c, f, r], i) => {
      const u = t < 4 ? 0 : (t - 4 - rnd(i) * .1), dx = (rnd(i + 20) - .5) * 1500 * u, dy = -1150 * u + 2100 * u * u;
      const bob = t > 1.2 && t < 4 ? 2 * Math.sin(t * 1.4 + i) : 0;
      svgSpr('p' + i, PIECE(n, c), { x: 150 + (f + .5) * 97.5 + dx, y: y - 390 + (r + 1) * 97.5 - 6 + dy + bob, h: 92, r: u * 500 * (rnd(i + 5) - .5), z: 14 });
    });
    // the white king is asleep
    if (t < 4) [0, 1, 2].forEach(i => {
      const u = ((t + i * .75) % 2.25) / 2.25;
      text('z' + i, 'z', { x: 150 + 4.5 * 97.5 + 42 + 60 * u + 10 * Math.sin(u * 8), y: 1035 - 390 + 7 * 97.5 - 60 - 170 * u, size: 34 + 46 * u, o: Math.sin(u * Math.PI), color: '#8c84ad', z: 16 });
    });
  }
  // the opening line
  if (t < 4.05) {
    const o = eOut((t - .2) / .5) * (1 - eIn((t - 3.8) / .2));
    text('dull1', 'Шахматы — это…', { x: 540, y: 200, size: 92, color: '#6a6780', o });
    text('dull2', 'скучно?', { x: 540, y: 330, size: 124, color: '#6a6780', o: eOut((t - 1.2) / .4) * (1 - eIn((t - 3.8) / .2)), letter: (i, n) => ({ dy: 10 * Math.sin(t * 1.5 + i * .5) }) });
  }
  // the fly
  if (t > .6 && t < 3.75) {
    const r = zap(t, 3.18, L.m, FLY1(3.35));
    const p = r && r !== 'gone' ? r.p : FLY1(t);
    if (r !== 'gone') flyer('fly1', 'fly', t, { x: p[0], y: p[1], h: 150, k: r ? r.k : 1, flip: facing('fly', Math.cos(t * 3.1) > 0 && t > .7), z: 31 });
  }
  bubble('am', t, 3.62, 4.4, 'Ам!', L.m[0] + 60, L.m[1] - 170, { tail: .25, size: 74 });
  confetti('c0', t, 4, 540, 980, 70, 1050);
  // the title falls in, letter after letter
  if (t >= 4 && t < 12.2) {
    const out2 = eIn((t - 11.9) / .3);
    const letter = (i, n, d) => { const u = (t - 4.05 - d - i * .045) / .38; return { dy: (1 - back(u)) * -420 - out2 * 480 + 5 * Math.sin(t * 3 + i * .7), r: (1 - clamp(u)) * 40, o: clamp(u * 4) }; };
    text('t1', 'Шахматы', { x: 540, y: 205, size: 176, colors: TITLE_COLORS, letter: (i, n) => letter(i, n, 0) });
    text('t2', 'с Леоном', { x: 540, y: 385, size: 148, colors: ['#3faf4a', '#3faf4a', '#3faf4a', '#2f9bdc', '#e8456f', '#f08a1d', '#6d4ee8', '#3faf4a'], letter: (i, n) => letter(i, n, .3) });
  }
  bubble('nb', t, 4.6, 6.6, 'Со мной —\nне скучно!', L.m[0] + 40, L.m[1] - 260, { tail: .3, size: 60 });
}

function friends(t, L) {                                 // everybody: where they are, whom they peek at
  if (t > 4.3 && t < 12.3) {
    const a = eOut((t - 4.3) / 1.2), o = 1 - eIn((t - 11.9) / .4);
    flyer('air_b', 'butter', t, { x: lerp(-100, 250, a) + 130 * Math.sin(t * .9), y: 720 + 150 * Math.sin(t * 1.3), h: 170, flip: facing('butter', Math.cos(t * .9) > 0), o, z: 20 });
    flyer('air_e', 'bee', t, { x: lerp(1180, 850, a) + 110 * Math.sin(t * 1.5 + 1), y: 880 + 110 * Math.sin(t * 2.2), h: 130, flip: facing('bee', Math.cos(t * 1.5 + 1) > 0), o, z: 20 });
    const d = (t - 5) % 6;
    if (d < 1.3) flyer('air_d', 'dragon', t, { x: lerp(-180, 1260, d / 1.3), y: 600 - 120 * Math.sin(d * 2.4), h: 170, flip: facing('dragon', true), z: 20 });
  }
  // Malon: comes out from behind Leon, then lives behind the phone and looks out
  const peekR = [[12.7, 15.0], [16.6, 19.5], [22.2, 25.3], [27.2, 29.4], [31, 33.6], [43, 45.2], [47, 50]];
  const peekOut = peekR.reduce((a, [p, q]) => Math.max(a, eOut((t - p) / .3) * (1 - eIO((t - q) / .3))), 0);
  let mx, my, mh = 300, mz, flip = false;
  if (t < 11.8) { const k = back((t - 6.2) / .4); mx = lerp(430, 180, k); my = 1720; mz = 31; }
  else if (t < 34) { mx = lerp(770, 934, peekOut); my = 1170 + 22 * Math.sin(t * 2.2); mz = 8; flip = true; mh = 310; }
  else if (t < 42.42) { const k = eOut((t - 34.1) / .5), q = eIn((t - 41.95) / .4); mx = lerp(934, 905, k) + q * 420; my = lerp(1170, 1700, k) - 160 * Math.sin(q * Math.PI); mz = 26; flip = true; mh = 290; }
  else if (t < 52) { mx = lerp(770, 934, peekOut); my = 1170 + 22 * Math.sin(t * 2.2); mz = 8; flip = true; mh = 310; }
  else { const k = eOut((t - 52.1) / .5); mx = lerp(934, 130, k); my = lerp(1170, 1740, k); mz = 26; }
  if (t >= 6.2) {
    const H = hops(t, [6.2, 6.8, 38.3, ...(t > 58 ? beats(58.5, 61, 1).map(x => x + .25) : []), 61.75], 90);
    spr('malon', 'malon', { x: mx, y: my - H.y, h: mh, flip, sx: H.sx, sy: H.sy, z: mz, r: 2 * Math.sin(t * 2.4) });
  }

  // Hedgehog: rolls in, then looks over the top of the phone
  const peekT = [[14.8, 17], [20.8, 23.2], [26.3, 28.6], [32, 33.8], [42.8, 45.5]];
  const over = peekT.reduce((a, [p, q]) => Math.max(a, eOut((t - p) / .28) * (1 - eIO((t - q) / .28))), 0);
  if (t >= 7.2 && t < 12.2) {
    const k = eOut((t - 7.2) / .6), x = lerp(1240, 985, k);
    spr('hedge', 'hedge', { x, y: 1640, h: 210, ox: .5, oy: .55, r: (1 - k) * 1080, z: 26, sx: 1 + .012 * Math.sin(t * 4), o: 1 - eIn((t - 11.9) / .25) });
  } else if (t >= 34 && t < 42.1) {
    const k = eIn((t - 34) / .42), land = t > 34.42 ? 34 * Math.abs(Math.sin((t - 34.42) * 9)) * Math.exp(-(t - 34.42) * 4.5) : 0;
    spr('hedge', 'hedge', { x: lerp(640, 1000, eIO((t - 34) / .42)), y: lerp(620, 1770, k) - land, h: 190, z: 27, flip: true, x_: 0, r: t < 34.42 ? (t - 34) * 700 : 0 });
  } else if (t >= 12.2 && t < 46 && (t < 34 || t >= 42.45)) {
    spr('hedge', 'hedge', { x: 640, y: lerp(650, 560, over) + 6 * Math.sin(t * 5), h: 200, z: 8, flip: true });
  } else if (t >= 46 && t < 52.5) {
    // the balloons lift him up, his needles pop them
    const up = eIO((t - 46.7) / 2.7), fall = eIn((t - 49.5) / .45), base = 1800, top = 1120, y0 = lerp(base, top, up);
    const y = t < 49.5 ? y0 : lerp(top, base, fall), bounce = t > 49.95 ? 40 * Math.abs(Math.sin((t - 49.95) * 8)) * Math.exp(-(t - 49.95) * 4) : 0;
    const x = 950 + (t < 49.5 ? 14 * Math.sin(t * 3) : 0);
    spr('hedge', 'hedge', { x, y: y - bounce, h: 200, z: 26, flip: true, r: t < 49.5 ? 5 * Math.sin(t * 4) : (t < 49.95 ? (t - 49.5) * 500 : 0) });
    if (t < 49.5) spr('balls', 'g_balloons', { x: x + 2, y: y - 175, h: 330, z: 25, sx: back((t - 46.2) / .3), sy: back((t - 46.2) / .3) });
    confetti('c2', t, 49.5, x, top - 320, 46, 640);
    bubble('oi', t, 47.6, 49.5, 'Ой-ой-ой!', x - 50, y - 490, { tail: .75, size: 54 });
    bubble('puf', t, 49.6, 51.0, 'Пуф!', x - 60, 1560, { tail: .7, size: 60 });
  } else if (t >= 52.5) {
    const k = eOut((t - 52.6) / .5), H = hops(t, t > 58 ? [...beats(58.5, 61, 1).map(x => x + .5), 61.8] : [], 80);
    spr('hedge', 'hedge', { x: lerp(1240, 960, k), y: 1750 - H.y, h: 230, z: 26, flip: true, ox: .5, oy: 1, sx: H.sx, sy: H.sy });
  }

  // Parrot: lands on Leon's head, moves to the phone, comes back
  if (t >= 8.2) {
    const head = [L.P.x + L.P.h * .05, L.P.y - L.H.y - L.P.h * .92];
    let x, y, h = 210, fl = false;
    if (t < 12.3) { const k = eOut((t - 8.2) / .7); x = lerp(1150, head[0], k); y = lerp(420, head[1], k) - 110 * Math.sin(clamp((t - 8.2) / .7) * Math.PI); }
    else if (t < 34.2) { const k = eIO((t - 12.3) / .5); x = lerp(head[0], 296, k); y = lerp(head[1], PHONE_TOP + 18, k) - 120 * Math.sin(k * Math.PI); }
    else if (t < 41.85) { const k = eIO((t - 34.2) / .5); x = lerp(296, 905, k); y = lerp(PHONE_TOP + 18, 1430, k) - 90 * Math.sin(k * Math.PI); }
    else if (t < 52.3) { const k = eIO((t - 41.85) / .55); x = lerp(905, 296, k); y = lerp(1430, PHONE_TOP + 18, k) - 90 * Math.sin(k * Math.PI); }
    else { const k = eIO((t - 52.3) / .5); x = lerp(296, head[0], k); y = lerp(PHONE_TOP + 18, head[1], k) - 90 * Math.sin(k * Math.PI); }
    const flying = (t < 8.9) || (t > 12.3 && t < 12.8) || (t > 34.2 && t < 34.7) || (t > 41.85 && t < 42.4) || (t > 52.3 && t < 52.8);
    const nod = flying ? 8 * Math.sin(t * 24) : 5 * Math.sin((t % .5) / .5 * 6.283);
    spr('parrot', 'parrot', { x, y, h, flip: fl, r: nod, z: 34, sy: 1 + (flying ? .05 * Math.sin(t * 24) : .02 * Math.sin((t % .5) / .5 * 6.283)) });
  }

  // Axolotl: dives and looks out of its puddle in the corner
  if (t >= 9) {
    const pk = eOut((t - 9) / .35);
    const e = el('pool', () => { const d = document.createElement('div'); d.className = 'a'; d.style.borderRadius = '50%'; d.style.background = 'radial-gradient(ellipse at 40% 35%, #cdeeff 0 18%, #7cc9f3 40%, #4aa8e4 100%)'; d.style.boxShadow = '0 0 0 12px #bfe9fa'; return d; });
    e.style.width = '260px'; e.style.height = '74px'; e.style.transform = `translate(${840 - 130}px, ${1860 - 37}px) scale(${pk})`; e.style.transformOrigin = '50% 50%'; e.style.zIndex = 24;
    const up = [[9.2, 12], [13, 15.5], [19, 21.6], [24, 26.4], [29, 30.8], [36.2, 40], [44, 46], [50.2, 53], [53.2, 64]].reduce((a, [p, q]) => Math.max(a, back((t - p) / .3) * (1 - eIO((t - q) / .25))), 0);
    if (up > .02) spr('axo', 'axo', { x: 840, y: 1868 + (1 - up) * 150 + 5 * Math.sin(t * 3), h: 190, z: 25, clip: clamp((1 - up) * 150 / 190 + .05), flip: false });
    // a ripple on the water when it comes up
  }
  bubble('b_malon', t, 6.45, 7.7, 'Я Малон!', 190, 1395, { tail: .3 });
  bubble('b_hedge', t, 7.75, 8.85, 'Фыр-фыр!', 975, 1480, { tail: .7 });
  bubble('b_parrot', t, 8.95, 10.05, 'Пр-р-ривет!', L.P.x + 110, 840, { tail: .2 });
  bubble('b_axo', t, 9.6, 10.8, 'Буль!', 800, 1660, { tail: .7 });
  if (TURTLE_X(t) > -90) bubble('b_turtle', t, 10.5, 12.2, 'Подождите меня!', TURTLE_X(t) + 60, 1750, { tail: .2, size: 48 });
}

// ---------------------------------------------------------------- scenes with the phone
function s3(t, L) {                                      // 12–20: the rook catches flies; one gets away
  caption(t, 12.2, 20, 'Ладья ловит мух', 'и ребёнок запоминает, как она ходит', { s1: 96, s2: 50 });
  if (t > 17.5 && t < 19.05) {
    const r = zap(t, 18.55, L.m, FLY2(18.72));
    const p = r && r !== 'gone' ? r.p : FLY2(t);
    if (r !== 'gone') flyer('fly2', 'fly', t, { x: p[0], y: p[1], h: 120 + 40 * clamp((t - 17.55) / .4), k: r ? r.k : 1, flip: facing('fly', false), z: 35 });
  }
  bubble('b_fly', t, 19.0, 20, 'Эта — моя!', L.m[0] + 70, L.m[1] - 170, { tail: .3, size: 52 });
}

const FROG_LAND = [[20.5, 150, 0], [21.1, 330, 2], [21.7, 510, 5], [22.3, 700, 7], [22.9, 900, 9]];
function s4(t, L) {                                      // 20–26: a frog on the words; a hundred lessons
  const letter = (i, n) => {
    let dy = 0, r = 0;
    for (const [lt, , li] of FROG_LAND) { const u = t - (lt + .42), d = i - li; if (u > 0 && u < .55 && Math.abs(d) <= 2) { const w = (1 - Math.abs(d) / 3); dy += 46 * w * Math.exp(-u * 6) * Math.cos(u * 26); r += d * 6 * Math.exp(-u * 6); } }
    return { dy, r };
  };
  caption(t, 20, 26, '100 уроков', 'от первого хода до мата', { s1: 118, y1: 150, y2: 288, s2: 58, letter });
  if (t >= 20 && t < 26) {
    // from the left on the grass — up on the words — along them — down by the corner of the phone
    let x, y, r = 0, flip = false, sx = 1, sy = 1;
    const pts = [[20, -90, 1600], ...FROG_LAND.map(f => [f[0] + .42, f[1], 96]), [23.75, 1006, 1360], [24.4, 1006, 1360]];
    let i = 1; while (i < pts.length - 1 && t > pts[i][0]) i++;
    const [a, xa, ya] = pts[i - 1], [b, xb, yb] = pts[i], u = clamp((t - a) / (b - a));
    x = lerp(xa, xb, u); y = lerp(ya, yb, u) - 4 * u * (1 - u) * (i === 1 ? 700 : i === pts.length - 2 ? 150 : 130);
    sy = 1 + .1 * Math.sin(u * Math.PI); sx = 1 - .07 * Math.sin(u * Math.PI);
    if (u < .02 || u > .98) { sy = .9; sx = 1.08; }
    if (t > 24.4) { const v = (t - 24.4) / 1.3; x = 1006 + 300 * v; y = 1360 - 240 * Math.sin(Math.min(1, v) * Math.PI) + 800 * v * v; }
    spr('frog', 'frog', { x, y, h: 150, sx, sy, z: 42, flip });
  }
}

function s5(t, L) {                                      // 26–30: mini games; black pawns run away from a white queen
  caption(t, 26, 30, 'Мини-игры и задачки', 'ферзь против шести пешек', { s1: 76, y1: 130, y2: 236, s2: 52 });
  if (t >= 26.2 && t < 30.2) {
    const run = (t - 26.2) / 3.8;
    [0, 1, 2, 3].forEach(i => {
      const x = lerp(-120, 1260, run + .24 - i * .055), H = 34 * Math.abs(Math.sin((t + i * .13) * 9));
      svgSpr('pw' + i, PIECE('P', 'b'), { x, y: 1780 - H, h: 118, flip: true, r: 6 * Math.sin((t + i) * 9), z: 36 });
    });
    const x = lerp(-280, 1100, run), H = 30 * Math.abs(Math.sin(t * 7));
    svgSpr('qn', PIECE('Q', 'w'), { x, y: 1800 - H, h: 170, r: 8 + 4 * Math.sin(t * 7), z: 36 });
  }
  bubble('b_q', t, 27.5, 29.6, 'Догоню!', lerp(-280, 1100, (t - 26.2) / 3.8) + 40, 1590, { tail: .25, size: 50 });
}

function s6(t, L) {                                      // 30–34: coins from the sky
  caption(t, 30, 34, 'Верный ответ — монетка', 'а за урок — звёзды', { s1: 72, y1: 130, y2: 236, s2: 58 });
  coinRain(t, 30.2, 34, 42);
}

// ---------------------------------------------------------------- 34–42: the jar opens
const JAR_X = 560, JAR_Y = 1790, JAR_H = 470, MOUTH_Y = JAR_Y - JAR_H * .88;
const SKY = {                                             // flying things: who, when out of the jar, where they circle
  fly: [35.05, 300, 980, 240, 180, 1.1, 0, 130], butter: [35.2, 760, 900, 220, 190, .8, 1, 180], mosquito: [35.35, 440, 720, 280, 140, 1.3, 2, 130],
  bee: [35.5, 840, 640, 180, 150, 1.5, 3, 130], moth: [35.65, 260, 620, 170, 180, .9, 4, 150], dragon: [35.8, 620, 500, 340, 110, 1.9, 5, 170],
  bug: [35.95, 940, 1040, 110, 120, 1.2, 6, 110], firefly: [36.1, 180, 1180, 130, 120, 1, 7, 120],
};
const orbit = (k, t) => { const [, cx, cy, ax, ay, w, ph] = SKY[k]; return [cx + ax * Math.sin(t * w + ph * 1.7), cy + ay * Math.sin(t * w * 1.4 + ph) + 8 * Math.sin(t * 9 + ph)]; };
const LURE = { fly: [520, 1430], butter: [560, 1385], mosquito: [500, 1475] };   // the prey comes down here before it is caught
const FLYR = (k, t) => {
  const s = SKY[k], u = clamp((t - s[0]) / .9), o = orbit(k, t), p = [lerp(JAR_X, o[0], eOut(u)), lerp(MOUTH_Y, o[1], eOut(u))];
  if (!LURE[k]) return p;
  const c = eIO((t - (CAUGHT[k] - .75)) / .75);
  return [lerp(p[0], LURE[k][0], c), lerp(p[1], LURE[k][1], c)];
};
const CAUGHT = { fly: 36.5, butter: 38.2, mosquito: 39.8 };
const GROUND = [                                          // walkers: who, out of the jar, goes to, strip, height, frames
  ['ant', 35.1, 1240, 1700, 100], ['beetle', 35.3, -160, 1745, 104, ['beetle', 'beetle2', 'beetle', 'beetle3']], ['spider', 35.5, 1260, 1790, 112], ['louse', 35.75, -160, 1660, 86],
  ['centi', 35.95, 1300, 1860, 120, ['centi', 'centi2', 'centi', 'centi3']], ['stag', 36.2, -180, 1840, 118], ['cater', 36.5, 1240, 1640, 100], ['worm', 36.8, -150, 1890, 94],
];
const HOPS = [['frog', 35.2, 1000, 1760, 170, 5, 240], ['hopper', 35.6, 80, 1600, 118, 6, 200], ['cricket', 36.1, 1010, 1600, 100, 7, 160]];
function s7(t, L) {
  if (t < 34 || t >= 42.3) return;
  caption(t, 34.2, 38, 'Монетки — на угощение', '', { s1: 74, y1: 136 });
  caption(t, 38, 42.1, 'В банке — 21 букашка', 'и каждая бегает по-своему', { s1: 74, y1: 120, y2: 226, s2: 54 });
  // the jar: comes up, shakes, the lid flies off
  const inK = back((t - 34.15) / .4), leave = eIO((t - 41.6) / .5);
  const shake = t < 35 ? 4 * Math.sin(t * 40) * clamp((t - 34.5) / .3) : 0;
  const lidT = t - 35;
  svgSpr('jar', JAR, { x: JAR_X + shake, y: JAR_Y + leave * 700, h: JAR_H, w: JAR_H * .75, sx: inK, sy: inK, z: 29 });
  if (t < 35) { // who is inside
    [['ant', -70, 120, 100], ['frog', 50, 150, 130], ['snail', -30, 40, 90]].forEach(([k, dx, dy, h], i) => spr('in' + i, k, { x: JAR_X + dx + shake, y: JAR_Y - 30 - dy * .2 - 6 * Math.abs(Math.sin(t * 12 + i)), h: h * inK, z: 28 }));
  }
  const lidX = JAR_X + 300 * clamp(lidT) , lidY = t < 35 ? MOUTH_Y + 5 : MOUTH_Y + 5 - 1200 * lidT + 1500 * lidT * lidT;
  if (t < 36.3) svgSpr('lid', LID, { x: lidX + shake, y: lidY, h: 70, w: 230, ox: .5, oy: .5, r: Math.max(0, lidT) * 560, z: 33, sx: inK, sy: inK });
  confetti('c3', t, 35, JAR_X, MOUTH_Y, 30, 620);
  // flying
  for (const k of Object.keys(SKY)) {
    const s = SKY[k];
    if (t < s[0]) continue;
    const c = CAUGHT[k];
    let p = FLYR(k, t), kk = 1;
    if (c !== undefined) {
      const r = zap(t, c, L.m, FLYR(k, c + .17));
      if (r === 'gone') continue;
      if (r) { p = r.p; kk = r.k; }
    }
    const pv = FLYR(k, t - .03), g = p[0] > pv[0];
    flyer('sky_' + k, k, t, { x: p[0], y: p[1], h: s[7], k: kk * clamp((t - s[0]) / .3 + .2), flip: facing(k, g), z: 36, o: 1 - eIn((t - 41.7) / .4) });
  }
  // on foot
  GROUND.forEach(([k, t0, x1, y, h, frames], i) => {
    const u = (t - t0) / 3.6;
    if (u < 0 || u > 1) return;
    const hop = u < .1 ? (u / .1) : 1;
    const x = lerp(JAR_X, x1, u), yy = lerp(MOUTH_Y + 40, y, eIn(hop)) - (u < .1 ? 130 * Math.sin(hop * Math.PI) : 0);
    const img = frames ? frames[Math.floor(t * 14) % 4] : k;
    spr('g_' + k, img, { x, y: yy - (frames ? 0 : 3 * Math.abs(Math.sin(t * 22 + i))), h, flip: facing(k, x1 > JAR_X), r: frames ? 0 : 3 * Math.sin(t * 20 + i), z: 30 });
  });
  HOPS.forEach(([k, t0, x1, y, h, n, jump], i) => {
    const u = (t - t0) / 3.5;
    if (u < 0 || u > 1) return;
    const v = u * n, f = v % 1;
    const x = lerp(JAR_X, x1, u), base = lerp(MOUTH_Y + 30, y, clamp(v));
    spr('h_' + k, k, { x, y: base - jump * 4 * f * (1 - f), h, flip: x1 < JAR_X, sy: f < .08 || f > .92 ? .88 : 1.05, sx: f < .08 || f > .92 ? 1.1 : .96, z: 35 });
  });
  // the fish goes straight into the axolotl's puddle
  if (t > 36.2 && t < 37.5) {
    const u = (t - 36.2) / 1.1;
    if (u < 1) spr('fish', 'fish', { x: lerp(JAR_X, 870, u), y: lerp(MOUTH_Y, 1860, u) - 560 * Math.sin(u * Math.PI), h: 96, r: u * 180 - 60, flip: true, z: 36 });
    confetti('splash', t, 37.3, 870, 1850, 14, 340);
  }
  bubble('b_nyam', t, 36.95, 37.8, 'Ням!', L.m[0] + 50, L.m[1] - 150, { tail: .3, size: 56 });
  bubble('b_kak', t, 38.65, 39.5, 'Как вкусно!', L.m[0] + 50, L.m[1] - 150, { tail: .2, size: 50 });
  bubble('b_hrum', t, 40.25, 41.1, 'Хрум-хрум!', L.m[0] + 50, L.m[1] - 150, { tail: .2, size: 50 });
  // a snail in a hurry overtakes the turtle, to her great surprise
  if (t > 37.9 && t < 42.2) {
    const x = lerp(-120, 1160, (t - 37.9) / 4);
    spr('snail', 'snail', { x, y: 1912, h: 104, flip: facing('snail', true), sy: 1 + .05 * Math.sin(t * 16), sx: 1 - .05 * Math.sin(t * 16), z: 38 });
    [0, 1, 2].forEach(i => { const e = el('speed' + i, () => { const d = document.createElement('div'); d.className = 'fx'; d.style.background = '#fff'; d.style.borderRadius = '6px'; return d; }); e.style.width = 70 + 'px'; e.style.height = 9 + 'px'; e.style.transform = `translate(${x - 150 - i * 34}px, ${1838 + i * 25}px)`; e.style.opacity = .85; e.style.zIndex = 38; });
  }
  bubble('b_snail', t, 40.1, 41.95, 'Улитка меня обогнала?!', TURTLE_X(t) + 60, 1745, { tail: .22, size: 44, z: 52 });
}

function s8(t, L) {                                      // 42–46: the real feeding in the real game
  caption(t, 42.25, 46, 'Леон ловит их языком', 'прямо на экране телефона', { s1: 80, y1: 130, y2: 236, s2: 52 });
  if (t >= 42 && t < 46.3) {
    flyer('fly_b', 'butter', t, { x: 80 + 30 * Math.sin(t * 1.3), y: 800 + 120 * Math.sin(t * 1.7), h: 150, flip: facing('butter', Math.cos(t * 1.3) > 0), z: 12 });
    flyer('fly_c', 'firefly', t, { x: 1000 + 30 * Math.sin(t * 1.5 + 1), y: 620 + 100 * Math.sin(t * 2), h: 110, flip: facing('firefly', Math.cos(t * 1.5 + 1) > 0), z: 12 });
    flyer('fly_d', 'bee', t, { x: 80 + 40 * Math.sin(t * 2.1 + 1), y: 1230 + 60 * Math.sin(t * 2.7), h: 110, flip: facing('bee', Math.cos(t * 2.1 + 1) > 0), z: 12 });
  }
}

function s9(t, L) {                                      // 46–52: gifts
  caption(t, 46.1, 52, '18 подарков', 'заслужил — выбирай!', { s1: 110, y1: 136, y2: 256, s2: 58 });
  if (t < 46 || t >= 52.3) return;
  const gone = eIO((t - 51.8) / .4);
  [['g_cup', 96, 760, 150, 46.5], ['g_medal', 990, 710, 150, 46.8], ['g_cake', 104, 1120, 150, 47.1], ['g_chest', 985, 1060, 140, 47.4]].forEach(([k, x, y, h, t0], i) => {
    const K = back((t - t0) / .3) * (1 - gone);
    if (K > .01) spr('gift' + i, k, { x, y: y + 8 * Math.sin(t * 2.3 + i), h, sx: K, sy: K, r: 4 * Math.sin(t * 2 + i), z: 13 });
  });
  // Leon on a drum, on the beat
  const K = back((t - 46.2) / .3) * (1 - gone);
  const beat = (t - 46) % .5, hit = Math.exp(-beat * 16);
  if (t >= 46.2 && K > .01) spr('drum', 'g_drum', { x: 300, y: 1915, h: 170, sx: K * (1 + .05 * hit), sy: K * (1 - .07 * hit), z: 39 });
  // a rocket: salute over the meadow
  if (t > 50.1 && t < 50.95) {
    const u = (t - 50.1) / .85;
    spr('rocket', 'g_rocket', { x: lerp(100, 110, u), y: lerp(1500, 450, eIn(u)), h: 190, r: 4 * Math.sin(t * 24), z: 13 });
  }
  firework('fw1', t, 50.95, 120, 500);
  firework('fw2', t, 51.15, 960, 430);
}

// ---------------------------------------------------------------- 52–58: what the child gets
const CHIPS = [
  ['L', 'Леон всё говорит вслух —\nчитать не обязательно', 52.7],
  ['♞', 'Настоящие правила,\nтактика и маты', 54.1],
  ['💛', 'Ошибаться не страшно:\nмонетки не отнимаются', 55.5],
];
function s10(t, L) {
  caption(t, 52.3, 58, 'Играет — и учится', '', { s1: 92, y1: 165 });
  if (t < 52.5 || t >= 58.4) return;
  CHIPS.forEach(([ic, str, t0], i) => {
    const e = el('chip' + i, () => {
      const d = document.createElement('div'); d.className = 'chip'; d.dataset.disp = 'flex';
      d.innerHTML = (ic === '♞' ? `<i>${PIECE('N', 'w')}</i>` : ic === 'L' ? '<i><img src="art/leon.png" alt=""></i>' : `<i>${ic}</i>`) + `<span style="white-space:pre">${str}</span>`;
      return d;
    });
    const k = back((t - t0) / .32), out = eIO((t - 58 - i * .05) / .3);
    const land = FROG_CHIP.findIndex(f => f[3] === i), sag = land >= 0 ? 16 * Math.exp(-Math.max(0, t - FROG_CHIP[land][0]) * 6) * (t > FROG_CHIP[land][0] ? 1 : 0) : 0;
    e.style.transform = `translate(90px, ${360 + i * 215 + sag - out * 900}px) scale(${k}) rotate(${(1 - clamp((t - t0) / .32)) * (i % 2 ? 7 : -7)}deg)`;
    e.style.opacity = clamp((t - t0) * 8); e.style.zIndex = 41;
  });
  // the frog tries every card
  if (t > 53) {
    const pts = [[53, -100, 1500], ...FROG_CHIP.map(f => [f[0], f[1], f[2]]), [57.9, 1180, 1400]];
    let i = 1; while (i < pts.length - 1 && t > pts[i][0]) i++;
    const [a, xa, ya] = pts[i - 1], [b, xb, yb] = pts[i], u = clamp((t - a) / (b - a)), w = clamp((u - .55) / .45);
    spr('frog', 'frog', { x: lerp(xa, xb, w), y: lerp(ya, yb, w) - 4 * w * (1 - w) * 170, h: 130, z: 45, sy: w > 0 && w < 1 ? 1.08 : .94, sx: w > 0 && w < 1 ? .95 : 1.05 });
  }
  flyer('fly_b', 'butter', t, { x: 170 + 90 * Math.sin(t * 1.2), y: 1110 + 60 * Math.sin(t * 2), h: 120, flip: facing('butter', Math.cos(t * 1.2) > 0), z: 43 });
  flyer('fly_d', 'bee', t, { x: 900 + 70 * Math.sin(t * 2 + 2), y: 1140 + 40 * Math.sin(t * 3), h: 96, flip: facing('bee', Math.cos(t * 2 + 2) > 0), z: 43 });
}
const FROG_CHIP = [[53.7, 860, 366, 0], [55.1, 210, 581, 1], [56.5, 850, 796, 2]];

// ---------------------------------------------------------------- 58–64: all together
function s11(t, L) {
  if (t < 58) return;
  const lt = (i, d) => { const u = (t - 58.1 - d - i * .04) / .38; return { dy: (1 - back(u)) * -420 + 5 * Math.sin(t * 3 + i * .7), r: (1 - clamp(u)) * 40, o: clamp(u * 4) }; };
  text('t1b', 'Шахматы', { x: 540, y: 205, size: 176, colors: TITLE_COLORS, letter: i => lt(i, 0) });
  text('t2b', 'с Леоном', { x: 540, y: 385, size: 148, colors: ['#3faf4a', '#3faf4a', '#3faf4a', '#2f9bdc', '#e8456f', '#f08a1d', '#6d4ee8', '#3faf4a'], letter: i => lt(i, .3) });
  const k1 = back((t - 58.9) / .3), k2 = back((t - 59.3) / .3);
  text('f1', 'Бесплатно. В браузере. Без установки.', { x: 540, y: 545, size: 50, color: '#5b49a8', k: k1, o: clamp((t - 58.9) * 6) });
  const e = el('url', () => { const d = document.createElement('div'); d.className = 'chip'; d.dataset.disp = 'block'; d.style.width = 'auto'; d.style.background = '#6d4ee8'; d.style.color = '#fff'; d.style.padding = '26px 46px'; d.style.fontSize = '56px'; d.style.whiteSpace = 'nowrap'; d.textContent = 'xitromu.github.io/chess-leon'; return d; });
  e.style.transform = `translate(540px, 660px) translate(-50%, -50%) scale(${k2 * (1 + .012 * Math.sin((t % .5) / .5 * 6.283))})`; e.style.opacity = clamp((t - 59.3) * 6); e.style.zIndex = 41;
  // the frog in the line
  const H = hops(t, [...beats(58.8, 61, 1), 61.7], 90);
  spr('frog', 'frog', { x: 790, y: 1690 - H.y, h: 150, sx: H.sx, sy: H.sy, z: 24 });
  confetti('c9', t, 61.55, 540, 900, 70, 1000);
  flyer('end_b', 'butter', t, { x: 170 + 80 * Math.sin(t * 1.1), y: 930 + 90 * Math.sin(t * 1.7), h: 150, flip: facing('butter', Math.cos(t * 1.1) > 0), z: 22 });
  flyer('end_e', 'bee', t, { x: 860 + 90 * Math.sin(t * 1.9 + 2), y: 900 + 70 * Math.sin(t * 2.6), h: 110, flip: facing('bee', Math.cos(t * 1.9 + 2) > 0), z: 22 });
  flyer('end_f', 'firefly', t, { x: 660 + 60 * Math.sin(t * 1.3 + 4), y: 1040 + 50 * Math.sin(t * 2.1), h: 100, flip: facing('firefly', Math.cos(t * 1.3 + 4) > 0), z: 22 });
  // everybody jumps when she finally arrives
  bubble('b_done', t, 61.55, 63.3, 'Я успела!', TURTLE_X(t) + 70, 1745, { tail: .2, size: 62, z: 55 });
  if (t > 61.6) {
    const r = zap(t, 62.75, L.m, FLY3(62.92));
    const p = r && r !== 'gone' ? r.p : FLY3(t);
    if (r !== 'gone') flyer('fly3', 'fly', t, { x: p[0], y: p[1], h: 130, k: r ? r.k : 1, flip: facing('fly', false), z: 36 });
  }
  bubble('b_last', t, 63.2, 63.95, 'Ам!', L.m[0] + 60, L.m[1] - 150, { tail: .25, size: 74, z: 55 });
}

// ---------------------------------------------------------------- one frame
const clouds = [['c1', 90, 470, 7], ['c2', 620, 330, 5], ['c3', 330, 760, 9]];
function draw(t) {
  used = new Set(); pending = [];
  document.getElementById('tongue').style.display = 'none';
  // the world: dull until the fly is eaten
  const sat = t < 4 ? .08 : lerp(.08, 1, eOut((t - 4) / .4));
  stage.style.filter = sat < .995 ? `saturate(${sat}) brightness(${lerp(1.03, 1, clamp((t - 4) * 3))})` : '';
  const sun = document.getElementById('sun');
  if (!sun.dataset.ok) {
    sun.dataset.ok = 1;
    let rays = ''; for (let i = 0; i < 12; i++) rays += `<rect x="-9" y="-112" width="18" height="44" rx="9" fill="#ffd34d" transform="rotate(${i * 30})"/>`;
    sun.innerHTML = `<g id="rays">${rays}</g><circle r="58" fill="#ffe27a"/><circle r="44" fill="#ffd34d"/>`;
  }
  sun.firstChild.setAttribute('transform', `rotate(${t * 12})`);
  for (const [id, x, y, v] of clouds) document.getElementById(id).style.transform = `translate(${((x + t * v) % 1400) - 240}px, ${y}px)`;

  const L = leon(t);
  turtle(t);
  phone(t);
  if (t < 12.3) s1(t, L);
  friends(t, L);
  if (t >= 12.2 && t < 20.1) s3(t, L);
  if (t >= 20 && t < 26.1) s4(t, L);
  if (t >= 26 && t < 30.1) s5(t, L);
  if (t >= 30 && t < 34.1) s6(t, L);
  if (t >= 12.6 && t < 34.2) {
    const o = clamp((t - 12.6) * 2) * (1 - eIn((t - 33.8) / .4));
    flyer('near_b', 'butter', t, { x: 98 + 62 * Math.sin(t * 1.15), y: 900 + 230 * Math.sin(t * .8), h: 138, flip: facing('butter', Math.cos(t * 1.15) > 0), o, z: 12 });
    flyer('near_e', 'bee', t, { x: 980 + 58 * Math.sin(t * 2.1 + 1), y: 1370 + 80 * Math.sin(t * 2.9), h: 104, flip: facing('bee', Math.cos(t * 2.1 + 1) > 0), o, z: 12 });
    const d = (t - 14.5) % 7.5;
    if (d > 0 && d < 1.2) flyer('near_d', 'dragon', t, { x: lerp(1240, -160, d / 1.2), y: 400 + 40 * Math.sin(d * 5), h: 130, flip: facing('dragon', false), z: 12 });
  }
  s7(t, L);
  if (t >= 42.2 && t < 46.1) s8(t, L);
  if (t >= 46 && t < 52.4) s9(t, L);
  if (t >= 52.3 && t < 58.5) s10(t, L);
  s11(t, L);

  for (const [id, e] of pool) if (!used.has(id)) e.style.display = 'none';
  document.getElementById('flash').style.opacity = Math.max(t >= 4 ? 1 - clamp((t - 4) / .28) : 0, clamp((t - 63.55) / .45));
}
window.renderAt = async t => { draw(t); await Promise.all(pending); };

// the sounds of the cartoon: [time, what, loudness]. The real game's sounds come out of frames/sounds; fx: are made by render.py
window.CUES = [
  [.9, 'bug:fly', .5], [2.1, 'fx:bubbleup', .5], [3.12, 'fx:boing', .55], [3.18, 'fx:whip', .9], [3.62, 'sfx:chomp', 1], [4, 'fx:burst', .9], [4, 'sfx:win', .55],
  ...[0, 1, 2, 3, 4, 5, 6].map(i => [4.05 + i * .045, 'sfx:pop', .2]),
  [6.2, 'fx:boing', .6], [7.2, 'fx:roll', .7], [7.8, 'sfx:pop', .4], [8.2, 'fx:slideup', .4], [8.9, 'sfx:pop', .35], [9.2, 'fx:bubbleup', .7], [10.5, 'fx:plod', .6],
  [12, 'fx:whoosh', .8], [17.55, 'bug:fly', .5], [18.5, 'fx:boing', .4], [18.55, 'fx:whip', .9], [18.95, 'sfx:chomp', 1],
  [20, 'fx:whoosh', .3], ...FROG_LAND.map(f => [f[0], 'fx:boing', .55]), [20.1, 'bug:frog', .5], [23.2, 'fx:slidedown', .4],
  [26.2, 'fx:patter', .7], [27.5, 'sfx:capture', .5],
  ...beats(30.2, 33.4, .24).map(x => [x, 'sfx:coin', .28]),
  [34, 'fx:whoosh', .7], [34.5, 'fx:rattle', .6], [35, 'fx:pop_lid', 1], [35.05, 'bug:fly', .35], [35.2, 'bug:butter', .3], [35.35, 'bug:mosquito', .25], [35.5, 'bug:bee', .3], [35.8, 'bug:dragon', .25],
  [35.2, 'bug:frog', .4], [35.3, 'bug:beetle', .4], [35.5, 'bug:spider', .35], [35.95, 'bug:centi', .4], [36.2, 'bug:hopper', .3], [36.1, 'bug:cricket', .25],
  [36.5, 'fx:whip', .85], [36.93, 'sfx:chomp', 1], [37.25, 'fx:splash', .7], [38.2, 'fx:whip', .85], [38.3, 'fx:boing', .4], [38.63, 'sfx:chomp', 1], [39.8, 'fx:whip', .85], [40.23, 'sfx:chomp', 1],
  [38.6, 'fx:zoom', .55],
  [42, 'fx:whoosh', .7],
  ...[46.5, 46.8, 47.1, 47.4].map(x => [x, 'sfx:pop', .4]), [46.7, 'fx:slideup', .4], [49.5, 'sfx:pop', 1], [49.53, 'sfx:pop', .8], [49.58, 'sfx:pop', .8], [49.55, 'fx:slidedown', .7], [49.95, 'fx:boing', .6],
  [50.1, 'fx:rocket', .6], [50.95, 'fx:burst', .55], [51.15, 'fx:burst', .45],
  [52, 'fx:whoosh', .7], ...CHIPS.map(c => [c[2], 'sfx:right', .5]), ...FROG_CHIP.map(f => [f[0] - .35, 'fx:boing', .45]),
  ...[0, 1, 2, 3, 4, 5, 6].map(i => [58.1 + i * .04, 'sfx:pop', .2]), [59.3, 'sfx:right', .5],
  [61.55, 'sfx:win', .7], [61.55, 'fx:burst', .7], [62.7, 'fx:boing', .4], [62.75, 'fx:whip', .9], [63.17, 'sfx:chomp', 1],
];
window.FILM_LIST = FILMS;
window.VIDEO_LEN = LEN;
