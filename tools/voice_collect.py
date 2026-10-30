"""Все фразы игры для озвучки: тексты из кода, плюс то, что реально звучит в уроках (автопрогон с подставленными значениями).
Каждую фразу режет на кусочки сама игра (voiceParts). Пишет mockups/voice/parts.json: {кусочек: сколько раз встретился}.

Запуск: C:\\TST\\python.exe -u tools\\voice_collect.py [сколько кругов автопрогона, по умолчанию 2]
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "promo"))
from cdp import start_edge  # noqa: E402

OUT = ROOT / "mockups" / "voice"
OUT.mkdir(parents=True, exist_ok=True)
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
LESSON_LIMIT = 40        # секунд на урок: бой с пешками робот сам не играет, его фразы берём из кода
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def literals(js):
    """Строковые литералы скрипта; шаблоны с ${} и html пропускаем — они придут из прогона."""
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if c == "/" and js[i + 1:i + 2] == "/":
            i = js.find("\n", i)
            i = n if i < 0 else i
            continue
        if c == "/" and js[i + 1:i + 2] == "*":
            i = js.find("*/", i + 2)
            i = n if i < 0 else i + 2
            continue
        if c in "'\"`":
            j, buf = i + 1, []
            while j < n and js[j] != c:
                if js[j] == "\\":
                    buf.append(js[j + 1:j + 2])
                    j += 2
                    continue
                if js[j] == "\n" and c != "`":
                    break
                buf.append(js[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
            continue
        i += 1
    return out


src = (ROOT / "index.html").read_text(encoding="utf-8")
slim = re.sub(r"data:[a-z]+/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+", "DATA", src)
js = slim[slim.index("<script"):]
ui = set(re.findall(r"name: '([^']+)'", slim)) | set(re.findall(r"sect: '([^']+)'", slim)) | set(re.findall(r"with: '([^']+)'", slim))
static = []
for s in literals(js):
    s = s.strip()
    if not re.search("[А-Яа-яЁё]", s) or "${" in s or re.search("<[a-z/]", s) or s in ui:
        continue
    if re.search(r"[.!?…:]$", s) or len(s.split()) >= 2:
        static.append(s)
static = sorted(set(static))
print(f"phrases in the code: {len(static)}", flush=True)

HOOK = r"""
(() => {
  window.__said = {};
  const rec = t => { if (t === undefined || t === null) return; t = String(t).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim(); if (t) __said[t] = (__said[t] || 0) + 1; };
  window.__rec = rec;
  window.speak = async t => { rec(t); };
  const T = window.tell; window.tell = async (text, o = {}) => { rec(o.voice || text); return T(text, o); };
  const A = window.askSquare; window.askSquare = async a => { rec(a.text); if (a.wrong) for (let s = 0; s < 64; s++) { try { if (!a.ok(s)) rec(a.wrong(s)); } catch (e) {} } return A(a); };
  const B = window.askChoice; window.askChoice = async a => { rec(a.text); rec(a.wrong); a.options.forEach(o => { const l = String(o.label).replace(/<[^>]+>/g, '').trim(); if (!/^\W*(Да|Нет)$/.test(l)) rec(l); rec(o.say); }); return B(a); };
  const C = window.askMove; window.askMove = async a => { rec(a.text); rec(a.wrongText); return C(a); };
  // экран итога и фразы вне уроков: имена и числа, которых в коде нет целиком
  PETS.forEach(p => { rec(`Сегодня со мной ${p.name}!`); rec(`Мы с ${p.with} проголодались! Выбирай угощение в банке.`); rec(`Это я, ${p.name}!`); rec(`${p.name} — ${p.price} ${coinsW(p.price)}. Нужно ещё 5 ${coinsW(5)} — пройди уроки!`); });
  GIFTS.forEach(g => { rec(`${g.name} — ${g.price} ${coinsW(g.price)}. Нужно ещё 5 ${coinsW(5)} — пройди уроки!`); rec(g.hi); });
  Object.values(FOODS).forEach(f => rec(f.say));
  [1, 2, 3, 5, 11, 21].forEach(n => { rec(`Нужно ещё ${n} ${coinsW(n)}. Пройди урок — и покормишь!`); rec(`Победа! Держи ${n} ${coinsW(n)}!`); rec(`Нужно ещё ${n} ${coinsW(n)} — пройди уроки!`); });
  BOARDS.forEach(b => rec(`Доска «${b[0]}» — красота!`));
})(); 0
"""
proc, page = start_edge()
try:
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Emulation.setDeviceMetricsOverride", width=412, height=730, deviceScaleFactor=1, mobile=False)
    page.call("Page.addScriptToEvaluateOnNewDocument", source=(ROOT / "promo" / "clock.js").read_text(encoding="utf-8"))
    page.call("Page.navigate", url="file:///" + str(ROOT / "index.html").replace("\\", "/"))
    page.wait_event("Page.loadEventFired")
    page.js((ROOT / "tools" / "autorun.js").read_text(encoding="utf-8") + ";0")
    page.js(HOOK)
    ids = page.js("LESSONS.map(l => l.id)")
    t0 = time.time()
    skipped = set()
    for round_no in range(1, ROUNDS + 1):
        for k, lid in enumerate(ids):
            if lid in skipped:
                continue
            page.js(f"delete BOT.res.done; BOT.run([{json.dumps(lid)}]).catch(e => PROMO.errors.push(String(e))); 0")
            start = time.time()
            while not page.js("BOT.res.done"):
                for _ in range(20):
                    page.js("PROMO.step(1500)")
                if time.time() - start > LESSON_LIMIT:
                    skipped.add(lid)
                    page.js("abortAll(); TAP = MOVE = null; 0")
                    print(f"  skipped, the robot cannot play it: {lid}", flush=True)
                    break
            if k % 10 == 0:
                print(f"round {round_no}: lesson {k + 1} of {len(ids)}, heard so far {page.js('Object.keys(__said).length')}, {time.time() - t0:.0f} s", flush=True)
    said = page.js("__said")
    print(f"heard in the lessons: {len(said)}; skipped lessons: {sorted(skipped)}", flush=True)
    fails = page.js("Object.entries(BOT.res).filter(([k, v]) => String(v).startsWith('FAIL')).map(([k, v]) => k + ': ' + v)")
    if fails:
        print("failed:", fails[:6], flush=True)
    phrases = sorted(set(static) | set(said))
    parts = page.js("(l => { const c = {}; l.forEach(t => voiceParts(t).forEach(p => { c[p] = (c[p] || 0) + 1; })); return c; })(%s)" % json.dumps(phrases, ensure_ascii=False))
    (OUT / "parts.json").write_text(json.dumps(parts, ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "phrases.json").write_text(json.dumps(phrases, ensure_ascii=False, indent=0), encoding="utf-8")
    tokens = [p for p in parts if p.startswith("#")]
    print(f"done: phrases {len(phrases)}, parts to record {len(parts)} (of them squares and numbers {len(tokens)}), chars {sum(map(len, parts))}", flush=True)
finally:
    proc.kill()
