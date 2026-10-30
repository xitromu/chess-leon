"""Проверка голоса в игре на локальном сервере (сервер leon, порт 8767): запись из сети, скачивание, работа без интернета, запасной голос.
Запуск: C:\\TST\\python.exe -u tools\\voice_test.py [папка для снимков]
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "promo"))
from cdp import start_edge  # noqa: E402

URL = "http://127.0.0.1:8767/index.html"
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INFO = """JSON.stringify({ row: document.querySelector('.vrow').textContent, how: vHow, dl: !!S.voiceDL, keys: VOICE_KEYS.size,
  ac: AC ? AC.state : 'нет', voiceBtn: document.querySelector('#voiceBtn').style.display, sw: !!navigator.serviceWorker.controller })"""


def shot(page, name):
    if SHOTS:
        Path(SHOTS, name + ".png").write_bytes(page.shot("png"))


def click(page, x, y):
    for kind in ("mousePressed", "mouseReleased"):
        page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)


def load(page):
    page.call("Page.navigate", url=URL)
    page.wait_event("Page.loadEventFired", timeout=40)
    time.sleep(1.2)


proc, page = start_edge()
try:
    page.call("Page.enable"); page.call("Runtime.enable"); page.call("Network.enable")
    page.call("Emulation.setDeviceMetricsOverride", width=412, height=780, deviceScaleFactor=2, mobile=False)
    page.call("Network.setCacheDisabled", cacheDisabled=False)

    print("--- 1. запись из сети")
    load(page)
    print(page.js(INFO))
    click(page, 200, 120)                         # первое касание включает звук
    time.sleep(.3)
    print("фраза:", page.js("""(async () => { const t0 = performance.now(); const parts = voiceParts('Привет! Я Леон. Выбирай урок!');
      await speak('Привет! Я Леон. Выбирай урок!'); return JSON.stringify({ parts, ms: Math.round(performance.now() - t0), ok: parts.every(p => VOICE_KEYS.has(vkey(p))) }); })()"""))
    print("клетка:", page.js("""(async () => { const t = 'А теперь без подсветки: найди клетку e4!', t0 = performance.now(); await speak(t);
      return JSON.stringify({ parts: voiceParts(t), ms: Math.round(performance.now() - t0) }); })()"""))
    print("друг:", page.js("""(async () => { const t0 = performance.now(); await speak('Фыр-фыр! Я Ёжик. Буду дружить с Леоном!', 'pet'); return Math.round(performance.now() - t0); })()"""))
    print(page.js(INFO))
    shot(page, "net")

    print("--- 2. чем покрыты фразы игры")
    print(page.js("""JSON.stringify((() => { const all = PRAISE.concat(OOPS, PETS.map(p => p.hi), GIFTS.map(g => g.hi), Object.values(FOODS).map(f => f.say));
      const miss = all.filter(t => !voiceParts(t).every(p => VOICE_KEYS.has(vkey(p)))); return { checked: all.length, missing: miss }; })())"""))

    print("--- 3. скачивание на устройство")
    t0 = time.time()
    page.js("voiceDownload(); 0")
    for _ in range(600):
        time.sleep(.5)
        if page.js("vLoad === 0"):
            break
    print(f"за {time.time() - t0:.0f} с:", page.js(INFO))
    print("в кеше:", page.js("caches.open(VOICE_CACHE).then(c => c.keys()).then(k => k.length)"), "хранилище:", page.js("navigator.storage.estimate().then(e => Math.round(e.usage / 1e6) + ' МБ')"))
    shot(page, "disk")

    print("--- 4. без интернета, запись скачана")
    load(page)                                    # теперь страницу держит служебный скрипт
    page.call("Network.emulateNetworkConditions", offline=True, latency=0, downloadThroughput=0, uploadThroughput=0)
    load(page)
    print(page.js(INFO))
    click(page, 200, 120)
    time.sleep(.3)
    print("фраза без сети:", page.js("""(async () => { const t0 = performance.now(); await speak('Ферзь против шести пешек. Твой ход!'); return JSON.stringify({ ms: Math.round(performance.now() - t0), how: vHow }); })()"""))

    print("--- 5. без интернета, записи нет: синтез устройства")
    page.js("caches.delete(VOICE_CACHE).then(() => { vBufs.clear(); S.voiceDL = false; save(); }); 0")
    time.sleep(.5)
    page.js("speak('Ладья — сильная фигура!'); 0")
    time.sleep(1.2)
    print(page.js(INFO))
    shot(page, "dev")
    page.call("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
    print("--- 6. уроки открываются, ошибок нет")
    load(page)
    print(page.js("""(async () => { document.querySelector('#cards .card').click(); await new Promise(r => setTimeout(r, 500)); return JSON.stringify({ screen: document.querySelector('.screen.on').id, title: document.querySelector('#lTitle').textContent }); })()"""))
    errs = [e["params"]["exceptionDetails"].get("text", "") + " " + str(e["params"]["exceptionDetails"].get("exception", {}).get("description", ""))[:160] for e in page.events if e.get("method") == "Runtime.exceptionThrown"]
    print("ошибки страницы:", errs[:5])
finally:
    proc.kill()
print("done")
