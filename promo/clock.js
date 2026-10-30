// Injected before the game loads: the page lives on a clock of our own, PROMO.step(ms) moves it. Every frame of the video
// is then exactly the same step of game time, however slowly the screenshots are taken. Nothing in index.html changes.
(() => {
  const P = window.PROMO = { rec: null, left: 0, gen: 0, sounds: [], frame: 0, errors: [] };
  let now = 0, seq = 0;
  const base = 1793000000000;
  const timers = new Map(), rafs = new Map();

  const addTimer = (fn, ms, a, every) => { const id = ++seq; timers.set(id, { id, at: now + Math.max(0, +ms || 0), fn, a, every }); return id; };
  window.setTimeout = (fn, ms, ...a) => addTimer(fn, ms, a, 0);
  window.setInterval = (fn, ms, ...a) => addTimer(fn, ms, a, Math.max(1, +ms || 1));
  window.clearTimeout = window.clearInterval = id => { timers.delete(id); };
  window.requestAnimationFrame = fn => { const id = ++seq; rafs.set(id, fn); return id; };
  window.cancelAnimationFrame = id => { rafs.delete(id); };
  performance.now = () => now;
  Date.now = () => base + now;

  // the same "random" on every run, so a retake gives the same picture
  let r = 20261030;
  Math.random = () => { r |= 0; r = r + 0x6D2B79F5 | 0; let t = Math.imul(r ^ r >>> 15, 1 | r); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };

  // the voice: no sound here, only its length, so the game waits as long as it does on a phone
  class Utterance { constructor(text) { this.text = text; } }
  window.SpeechSynthesisUtterance = Utterance;
  let speaking = 0;
  const synth = {
    getVoices: () => [{ lang: 'ru-RU', name: 'Pavel', localService: true }],
    cancel() { clearTimeout(speaking); },
    speak(u) { speaking = setTimeout(() => u.onend && u.onend(), Math.max(350, u.text.length * 62)); },
  };
  Object.defineProperty(window, 'speechSynthesis', { value: synth, configurable: true });

  // the saved game: everything is bought, so every screen is full
  try {
    localStorage.setItem('leonChess1', JSON.stringify({
      coins: 148, stars: {}, pets: ['malon', 'hedge', 'turtle', 'parrot', 'axo'], guest: '', buddy: 'axo', color: 0, board: 0, sound: true, noVoiceOff: true,
      gifts: ['balloons', 'cake', 'cup', 'chest', 'medal', 'garland', 'drum', 'rocket', 'confetti', 'flowers', 'house', 'hammock', 'nightlight', 'bubbles', 'wand'],
      shown: ['balloons', 'cake', 'cup', 'medal', 'garland', 'drum', 'rocket', 'confetti', 'flowers', 'house', 'hammock', 'nightlight'],
    }));
  } catch (e) {}

  const channel = new MessageChannel();
  const tick = () => new Promise(res => { channel.port1.onmessage = res; channel.port2.postMessage(0); });

  // CSS animations and transitions and element.animate(): held still and moved by hand
  const seen = new WeakSet();
  function moveAnimations(dt) {
    for (const a of document.getAnimations()) {
      try {
        if (!seen.has(a)) { seen.add(a); a.pause(); a.currentTime = a.currentTime || 0; continue; }
        const t = (a.currentTime || 0) + dt, end = a.effect ? a.effect.getComputedTiming().endTime : Infinity;
        if (end !== Infinity && t >= end) { if (a.playState !== 'finished') a.finish(); }
        else a.currentTime = t;
      } catch (e) {}
    }
  }

  P.step = async dt => {
    const target = now + dt;
    for (;;) {
      let next = null;
      for (const t of timers.values()) if (t.at <= target && (!next || t.at < next.at || (t.at === next.at && t.id < next.id))) next = t;
      if (!next) break;
      now = Math.max(now, next.at);
      if (next.every) next.at += next.every; else timers.delete(next.id);
      try { next.fn(...next.a); } catch (e) { P.errors.push(String(e)); }
      await tick();
    }
    now = target;
    const list = [...rafs.values()]; rafs.clear();
    for (const fn of list) try { fn(now); } catch (e) { P.errors.push(String(e)); }
    await tick();
    moveAnimations(dt);
    await tick();
    const name = P.rec;
    if (name) { P.frame++; if (--P.left <= 0) { P.rec = null; if (P.onDone) P.onDone(); } }
    return { rec: name, frame: P.frame, done: !!P.done, err: P.errors.length ? P.errors.splice(0) : null };
  };
  P.time = () => now;
})();
