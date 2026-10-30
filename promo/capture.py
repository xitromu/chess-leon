"""Films the real game (index.html) frame by frame, by the script in scenes.js. Writes frames/<take>/NNNNN.jpg,
frames/timeline.json (sounds with their times) and frames/sounds/*.f32.

Run:  C:\\TST\\python.exe capture.py            all takes (a few minutes)
      C:\\TST\\python.exe capture.py stills     one picture of every screen: frames/still_*.jpg
      C:\\TST\\python.exe capture.py rook mini  these takes only
"""
import base64
import json
import os
import shutil
import sys
import time

from cdp import start_edge

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "..", "index.html")
FRAMES = os.path.join(HERE, "frames")
VIEW_W, VIEW_H, SCALE = 412, 730, 2                  # the phone in CSS pixels; the frames are twice that
DT = 1000 / 30


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def main():
    args = sys.argv[1:]
    stills = args == ["stills"]
    os.makedirs(FRAMES, exist_ok=True)
    log("starting Edge")
    proc, page = start_edge()
    try:
        page.call("Page.enable")
        page.call("Runtime.enable")
        page.call("Emulation.setDeviceMetricsOverride", width=VIEW_W, height=VIEW_H, deviceScaleFactor=SCALE, mobile=False)
        page.call("Page.addScriptToEvaluateOnNewDocument", source=read("clock.js"))
        page.call("Page.navigate", url="file:///" + os.path.abspath(GAME).replace("\\", "/"))
        page.wait_event("Page.loadEventFired")
        page.js(read("scenes.js") + ";0")
        for _ in range(10):                          # the first pictures settle
            page.js(f"PROMO.step({DT})")
        log("game loaded")

        if stills:
            page.js("PROMO.stills().catch(e => PROMO.errors.push('stills: ' + e.message)); 0")
        else:
            page.js("PROMO.run(%s).catch(e => PROMO.errors.push('run: ' + e.message)); 0" % json.dumps(args or None))

        current, n, started, total = None, 0, time.time(), 0
        for i in range(200000):
            r = page.js(f"PROMO.step({DT})")
            if r["err"]:
                log("  page says:", r["err"])
            if stills:
                want = page.js("PROMO.want || ''")
                if want:
                    with open(os.path.join(FRAMES, f"still_{want}.jpg"), "wb") as f:
                        f.write(page.shot(quality=90))
                    log("  still", want)
                    page.js("PROMO.want = ''")
            elif r["rec"]:
                if r["rec"] != current:
                    current, n = r["rec"], 0
                    folder = os.path.join(FRAMES, current)
                    shutil.rmtree(folder, ignore_errors=True)
                    os.makedirs(folder)
                    log(f"take '{current}'")
                with open(os.path.join(folder, f"{n:05d}.jpg"), "wb") as f:
                    f.write(page.shot())
                n += 1
                total += 1
                if n % 30 == 0:
                    log(f"  {current}: {n} frames, {total / (time.time() - started):.1f} frames/s overall")
            if r["done"]:
                break
        else:
            raise RuntimeError("the script never finished")

        if not stills:
            sounds = page.js("PROMO.sounds")
            path = os.path.join(FRAMES, "timeline.json")
            old = []
            if args and os.path.exists(path):        # a retake of some takes keeps the sounds of the others
                with open(path, encoding="utf-8") as f:
                    old = [s for s in json.load(f) if s["take"] not in args]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(old + sounds, f, ensure_ascii=False, indent=0)
            folder = os.path.join(FRAMES, "sounds")
            os.makedirs(folder, exist_ok=True)
            kinds = page.js("[...['tap', 'move', 'capture', 'right', 'wrong', 'coin', 'pop', 'win', 'chomp'].map(k => 'sfx:' + k), 'drum:', ...Object.keys(BUG_SND).map(k => 'bug:' + k)]")
            for k in kinds:
                data = page.js(f"PROMO.renderSound({json.dumps(k)})")
                with open(os.path.join(folder, k.replace(":", "_") + ".f32"), "wb") as f:
                    f.write(base64.b64decode(data))
            log(f"sounds: {len(sounds)} events, {len({s['k'] for s in sounds})} kinds")
        log(f"done in {time.time() - started:.0f} s, frames: {total}")
    finally:
        proc.kill()


if __name__ == "__main__":
    main()
