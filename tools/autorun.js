// Автопрогон уроков в панели браузера (Node.js на ПК нет). Подменяет задания: бот сам находит верный ответ
// и проверяет, что он есть, что подсказка верна и что тексты ошибок собираются. Монетки и звёзды не трогает.
// Запуск в странице игры (сервер mockups, http://localhost:8765/index.html), панель браузера должна быть видна:
//   await import('/tools/autorun.js?' + Date.now()); BOT.run(['lines', 'things', ...]);  потом смотреть BOT.res
window.BOT = (() => {
  const res = {}, log = [];
  const fail = msg => { throw new Error(msg); };
  const wrongTry = (wrong, arg) => { if (typeof wrong === 'function') { const t = wrong(arg); if (t && /undefined|NaN/.test(t)) fail('текст ошибки: ' + t); } };
  window.tell = async text => { log.push('• ' + text); };
  window.askSquare = async ({ text, ok, hint, wrong }) => {
    const all = [...Array(64).keys()], good = all.filter(ok), bad = all.find(s => !ok(s));
    if (!good.length) fail('нет верной клетки: ' + text);
    if (hint && hint().map(x => typeof x === 'string' ? sqIdx(x) : x).some(s => !ok(s))) fail('подсказка неверна: ' + text);
    if (bad !== undefined) wrongTry(wrong, bad);
    log.push(`? ${text || ''} → ${sqName(good[0])}`);
    return good[0];
  };
  window.askChoice = async ({ text, options }) => {
    if (options.filter(o => o.ok).length !== 1) fail('верных ответов не один: ' + text);
    if (new Set(options.map(o => String(o.label))).size !== options.length) fail('одинаковые ответы: ' + text);
    log.push(`? ${text} → ${options.find(o => o.ok).label}`);
  };
  window.askMove = async ({ text, accept, hint }) => {
    let h = typeof hint === 'function' ? hint() : hint;
    if (typeof h === 'string') h = findMove(G.st, h);
    if (!h || !legal(G.st).some(m => m.from === h.from && m.to === h.to)) fail('подсказка — не ход: ' + text);
    const prev = G.st;
    await doMove(h);
    const r = accept(h, prev, G.st);
    if (r !== true) fail(`ход ${mstr(h)} не принят (${r}): ${text}`);
    log.push(`? ${text} → ${mstr(h)}`);
    return h;
  };
  async function run(ids) {
    for (const id of ids) {
      const def = LESSONS.find(l => l.id === id), t0 = performance.now();
      L = { def, errors: 0, earned: 0, pet: '' };
      show('lesson');
      log.length = 0;
      try { await def.run(); res[id] = `ok ${((performance.now() - t0) / 1000).toFixed(0)} с, шагов ${log.length}`; }
      catch (e) { res[id] = 'FAIL ' + e.message; console.error(id, e); }
    }
    res.done = true;
  }
  return { run, res, log };
})();
