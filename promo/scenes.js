// What happens in the video: the same buttons a child presses, in the order of the storyboard.
// Runs in the page after the game has loaded; PROMO.step() in clock.js moves the time.
(() => {
  const P = window.PROMO;
  const FPS = 30, MARGIN = 450;                       // each take runs this much longer: the crossfade into the next one

  const sleep = ms => { const g = P.gen; return new Promise((res, rej) => setTimeout(() => (g === P.gen ? res() : rej(new Error('take over'))), ms)); };
  const until = async (cond, what) => { for (let i = 0; i < 4000; i++) { if (cond()) return; await sleep(33); } throw new Error('never happened: ' + what); };

  // --- the finger ---
  const finger = document.createElement('div');
  finger.textContent = '👆';
  finger.style.cssText = 'position:fixed;left:0;top:0;z-index:99999;font:60px "Segoe UI Emoji";line-height:1;pointer-events:none;' +
    'opacity:0;filter:drop-shadow(0 3px 5px #2a205055);transform-origin:50% 0;will-change:transform';
  document.documentElement.appendChild(finger);
  let fx = 300, fy = 760;
  const place = (x, y, k = 1) => { fx = x; fy = y; finger.style.transform = `translate(${x - 30}px, ${y - 4}px) scale(${k})`; };
  const hide = () => { finger.style.opacity = 0; };
  const centre = el => { const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };

  // the finger comes to the element and presses it, exactly as a press would go: pointerdown, then click
  async function tap(el, { move = 420, hold = 120, at } = {}) {
    if (!el) throw new Error('nothing to tap');
    const [x, y] = at || centre(el), x0 = fx, y0 = fy;
    finger.style.opacity = 1;
    await tween(move, t => place(x0 + (x - x0) * t, y0 + (y - y0) * t));
    place(x, y, .84);
    const under = document.elementFromPoint(x, y) || el;
    under.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: x, clientY: y }));
    if (typeof el.click === 'function') el.click();
    await sleep(hold);
    place(x, y, 1);
  }
  const sq = name => sqEl(sqIdx(name));
  const pieceOn = n => G.els.get(G.st.b[typeof n === 'string' ? sqIdx(n) : n].id);
  const nextBtn = () => document.querySelector('#act .next');
  const pressNext = async () => { await until(nextBtn, 'button Next'); nextBtn().click(); await sleep(40); };

  // --- takes ---
  function rec(name, ms) {
    return new Promise(res => {
      P.gen++;
      P.frame = 0; P.rec = name; P.left = Math.round((ms + MARGIN) / 1000 * FPS); P.t0 = P.time();
      P.onDone = () => { P.onDone = null; P.gen++; res(); };
    });
  }
  async function take(name, ms, body) {
    const done = rec(name, ms);
    body().catch(e => { if (!/take over/.test(e.message)) P.errors.push(name + ': ' + e.message); });
    await done;
    hide();
  }

  // sounds: which one and when, the mix is done afterwards (make_video.py)
  for (const [fn, kind] of [['sfx', 'sfx'], ['bugSfx', 'bug']]) {
    const orig = window[fn];
    window[fn] = a => { if (P.rec) P.sounds.push({ take: P.rec, t: (P.time() - P.t0) / 1000, k: kind + ':' + a }); };
    P['orig_' + fn] = orig;
  }
  const origDrum = window.drumRoll;
  window.drumRoll = () => { if (P.rec) P.sounds.push({ take: P.rec, t: (P.time() - P.t0) / 1000, k: 'drum:' }); return 1300; };

  // every sound the game can make, drawn in an offline context by the game's own code: [{k, rate, data(base64 float32)}]
  P.renderSound = async k => {
    const [kind, arg] = k.split(':');
    const ctx = new OfflineAudioContext(1, 44100 * 3, 44100);
    AC = ctx; NB = null;
    if (kind === 'sfx') P.orig_sfx(arg);
    else if (kind === 'bug') P.orig_bugSfx(arg);
    else origDrum();
    const buf = await ctx.startRendering();
    const bytes = new Uint8Array(buf.getChannelData(0).buffer);
    let s = ''; for (let i = 0; i < bytes.length; i += 8192) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
    return btoa(s);
  };

  function seed() {
    LESSONS.forEach((l, i) => { if (i < 37) S.stars[l.id] = i % 9 === 4 ? 2 : 3; });
    S.coins = 148; save();
  }

  // a lesson up to the moment the child is asked to move: everything before it is pressed through off camera
  async function lessonUpTo(id, ready) {
    runLesson(LESSONS.find(l => l.id === id));
    await until(ready, id);
  }

  async function tMenu(ms) {
    menu(); say('Привет! Я Леон. Выбирай урок!');
    await take('menu', ms, async () => {
      await sleep(1100);
      const max = document.documentElement.scrollHeight - innerHeight;
      await tween(ms - 1500, t => window.scrollTo(0, max * t));
    });
    window.scrollTo(0, 0);
  }

  async function tRook(ms) {
    const flyTask = () => G.fly && MOVE;
    runLesson(LESSONS.find(l => l.id === 'rook'));
    await pressNext();                                // «Это ладья»
    await until(() => TAP, 'square task'); onTap(sqIdx('d5'));
    await pressNext();                                // «Ладья умеет ловить мух»
    await until(flyTask, 'first fly');
    await sleep(100);
    await take('rook', ms, async () => {
      for (;;) {
        await sleep(350);
        const white = G.st.b.findIndex(p => p && p.c === 'w');
        await tap(pieceOn(white), { at: centre(sqEl(white)) });
        await sleep(450);
        await tap(G.fly, { at: centre(G.fly) });
        await until(() => !flyTask(), 'fly caught');
        await until(flyTask, 'next fly');
      }
    });
  }

  async function tMini(ms) {
    runLesson(LESSONS.find(l => l.id === 'miniQ'));
    await pressNext();
    await until(() => MOVE, 'mini game');
    await sleep(100);
    await take('mini', ms, async () => {
      for (;;) {
        await sleep(300);
        // the queen goes for a pawn she can take safely, whatever the engine says the rest of the time
        const best = miniBest(G.st, PVP, 3);
        await tap(pieceOn(best.from), { at: centre(sqEl(best.from)) });
        await sleep(380);
        await tap(sqEl(best.to), { at: centre(sqEl(best.to)) });
        await until(() => !MOVE, 'our move');
        await until(() => MOVE, 'their move');
      }
    });
  }

  async function tResult(ms) {
    abortAll(); TAP = MOVE = null; actions([]);
    const def = LESSONS.find(l => l.id === 'rook');
    L = { def, errors: 0, earned: 13, pet: 'hedge' };
    show('lesson'); $('#lTitle').textContent = def.name;
    setPos('8/8/8/8/3R4/8/8/8 w - -'); say('Ладья — сильная фигура!');
    await sleep(100);
    await take('result', ms, async () => { await finishLesson(); });
    $('#result').classList.remove('on');
    abortAll();
  }

  async function tFeed(ms) {
    S.guest = ''; S.coins = 148; save();
    terra();
    await sleep(100);
    await take('feed', ms, async () => {
      await sleep(500);
      const food = k => document.querySelector(`#foods .fd[data-f="${k}"]`);
      for (const k of ['fly', 'butter', 'frog']) {
        const el = food(k);
        el.scrollIntoView({ block: 'nearest', inline: 'center' });
        await tap(el);
        await until(() => !TB.busy, 'eaten');
        await sleep(200);
      }
    });
    await until(() => !TB.busy, 'terrarium is free');
  }

  async function tFriends(ms) {
    S.guest = 'malon'; save(); terra();
    await sleep(100);
    await take('friends', ms, async () => {
      for (const id of ['hedge', 'parrot', 'axo', 'turtle']) {
        await sleep(280);
        await tap(document.querySelector(`#friends .fr[data-p="${id}"]`), { move: 340 });
        await sleep(650);
      }
    });
  }

  async function tShop(ms) {
    shop(); say('Это мои подарки! Купленный можно показать или спрятать — нажми на него.');
    await take('shop', ms, async () => {
      await sleep(500);
      const max = document.documentElement.scrollHeight - innerHeight;
      await tween(ms - 700, t => window.scrollTo(0, Math.min(max, 620) * t));
    });
    window.scrollTo(0, 0);
  }

  async function tDrum(ms) {
    menu(); say('Нажми на барабан — я постучу!');
    await sleep(100);
    await take('drum', ms, async () => {
      await sleep(250);
      await tap(document.querySelector('#menu .stage .g-drum'));
    });
  }

  async function tNight(ms) {
    S.guest = 'turtle'; save(); terra(); await sleep(100);
    await take('night', ms, async () => {
      await sleep(200);
      await tap(document.querySelector('#tbox .tg-nightlight'), { move: 380 });
    });
  }

  P.stills = async () => {
    seed();
    P.gen++;
    menu(); say('Привет! Я Леон. Выбирай урок!'); await sleep(600); await P.shot('menu');
    runLesson(LESSONS.find(l => l.id === 'rook')); await pressNext(); await until(() => TAP, 'square'); onTap(sqIdx('d5'));
    await pressNext(); await until(() => G.fly && MOVE, 'fly'); await sleep(300);
    select(G.st.b.findIndex(p => p && p.c === 'w')); await sleep(300); await P.shot('lesson');
    L.earned = 13; await sleep(10); finishLessonForStill(); await sleep(1100); await P.shot('result');
    $('#result').classList.remove('on');
    S.guest = 'malon'; save(); terra(); await sleep(700); await P.shot('terra');
    shop(); await sleep(600); await P.shot('shop');
    P.done = true;
  };
  function finishLessonForStill() { finishLesson().catch(() => {}); }
  P.shot = name => { P.want = name; return until(() => !P.want, 'still ' + name); };

  P.run = async only => {
    seed();
    P.gen++;
    const list = [['menu', tMenu, 6000], ['rook', tRook, 7800], ['mini', tMini, 5500], ['result', tResult, 4200],
      ['feed', tFeed, 9000], ['friends', tFriends, 5000], ['shop', tShop, 2500], ['drum', tDrum, 3800], ['night', tNight, 2500]];
    for (const [name, fn, ms] of list) {
      if (only && !only.includes(name)) continue;
      await fn(ms);
    }
    P.done = true;
  };
})();
