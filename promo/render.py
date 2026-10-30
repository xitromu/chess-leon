"""Renders the cartoon (cartoon.html + story.js) frame by frame in headless Edge, adds music and sound, writes the MP4.

Run:  C:\\TST\\python.exe render.py                   the whole film: out/Chess_Leon_promo.mp4
      C:\\TST\\python.exe render.py sheet 0 12 .5     a contact sheet of these seconds: out/sheet_0.jpg
      C:\\TST\\python.exe render.py audio             only the sound: out/audio.wav
Needs: Microsoft Edge, Python packages av, numpy, pillow (C:\\TST\\python.exe has them). Filmed takes: capture.py.
"""
import glob
import io
import json
import os
import sys
import time
import wave
from fractions import Fraction

import av
import numpy as np
from PIL import Image

from cdp import start_edge
from music import music, make_fx, RATE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FRAMES = os.path.join(HERE, "frames")
W, H, FPS = 1080, 1920, 30
NAME = "Chess_Leon_promo.mp4"


def log(*a):
    line = " ".join([time.strftime("%H:%M:%S")] + [str(x) for x in a])
    print(line, flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "render.log"), "a", encoding="utf-8") as f:
        f.write(line + chr(10))


def open_page():
    proc, page = start_edge()
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
    takes = {os.path.basename(d): len(glob.glob(os.path.join(d, "*.jpg"))) for d in glob.glob(os.path.join(FRAMES, "*")) if os.path.isdir(d)}
    page.call("Page.addScriptToEvaluateOnNewDocument", source="window.TAKES = " + json.dumps(takes) + ";")
    page.call("Page.navigate", url="file:///" + os.path.join(HERE, "cartoon.html").replace("\\", "/"))
    page.wait_event("Page.loadEventFired")
    return proc, page


def sheet(page, a, b, step):
    os.makedirs(OUT, exist_ok=True)
    times = list(np.arange(a, b + 1e-6, step))
    w, h, cols = 216, 384, 8
    rows = (len(times) + cols - 1) // cols
    pic = Image.new("RGB", (cols * (w + 4), rows * (h + 4)), "#888")
    for i, t in enumerate(times):
        page.js(f"renderAt({float(t)})")
        im = Image.open(io.BytesIO(page.shot(quality=85))).convert("RGB").resize((w, h), Image.LANCZOS)
        pic.paste(im, (i % cols * (w + 4), i // cols * (h + 4)))
    path = os.path.join(OUT, f"sheet_{int(a)}.jpg")
    pic.save(path, quality=88)
    log("sheet", path, pic.size)


# ---------------------------------------------------------------- sound
def game_sound(k):
    path = os.path.join(FRAMES, "sounds", k.replace(":", "_") + ".f32")
    data = np.fromfile(path, dtype=np.float32)
    nz = np.nonzero(np.abs(data) > 1e-4)[0]
    return data[:nz[-1] + 1] if len(nz) else data


def soundtrack(page):
    cues = page.js("CUES")
    films = page.js("FILM_LIST")
    total = page.js("VIDEO_LEN")
    with open(os.path.join(FRAMES, "timeline.json"), encoding="utf-8") as f:
        events = json.load(f)
    fx = make_fx()
    track = music(total)
    n = track.shape[1]
    sfx = np.zeros(n, np.float32)

    def put(sound, at, gain):
        i = int(at * RATE)
        if 0 <= i < n:
            s = sound[:n - i] * gain
            sfx[i:i + len(s)] += s

    for at, k, gain in cues:
        put(fx[k[3:]] if k.startswith("fx:") else game_sound(k), at, gain)
    for take, t0, t1, off in films:              # the real game's sounds while its picture is on the screen
        for e in events:
            if e["take"] == take and off <= e["t"] and t0 + e["t"] - off < t1:
                put(game_sound(e["k"]), t0 + e["t"] - off, .55)
    mix = track * .62 + sfx[None, :] * .9
    mix = np.tanh(mix * 1.15)
    fade = np.minimum(1, (total - np.arange(n) / RATE) / .5)
    mix *= fade
    return (mix / np.max(np.abs(mix)) * .92).astype(np.float32)


def write_wav(path, sound):
    pcm = (np.clip(sound.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- film
def film(page, crf="21"):
    os.makedirs(OUT, exist_ok=True)
    log("1/2 sound: music, the game's sounds, comedy noises")
    sound = soundtrack(page)
    write_wav(os.path.join(OUT, "audio.wav"), sound)
    total = page.js("VIDEO_LEN")
    n_frames = int(total * FPS)
    path = os.path.join(OUT, NAME)
    log(f"2/2 picture: {n_frames} frames")
    started = time.time()
    with av.open(path, "w") as box:
        v = box.add_stream("libx264", rate=FPS)
        v.width, v.height, v.pix_fmt = W, H, "yuv420p"
        v.options = {"crf": crf, "preset": "medium", "movflags": "+faststart"}
        a = box.add_stream("aac", rate=RATE)
        a.layout = "stereo"
        a.bit_rate = 160_000
        chunk, pos = 1024, 0

        def write_audio(until):
            nonlocal pos
            while pos < until and pos < sound.shape[1]:
                part = sound[:, pos:pos + chunk]
                if part.shape[1] < chunk:
                    part = np.pad(part, ((0, 0), (0, chunk - part.shape[1])))
                fr = av.AudioFrame.from_ndarray(np.ascontiguousarray(part), format="fltp", layout="stereo")
                fr.sample_rate, fr.pts, fr.time_base = RATE, pos, Fraction(1, RATE)
                for p in a.encode(fr):
                    box.mux(p)
                pos += chunk

        for i in range(n_frames):
            page.js(f"renderAt({i / FPS})")
            im = Image.open(io.BytesIO(page.shot(quality=95))).convert("RGB")
            fr = av.VideoFrame.from_image(im)
            fr.pts, fr.time_base = i, Fraction(1, FPS)
            for p in v.encode(fr):
                box.mux(p)
            write_audio(int((i + 1) / FPS * RATE))
            if i % FPS == 0:
                speed = (i + 1) / (time.time() - started)
                log(f"   {100 * i // n_frames}%  video second {i // FPS} of {int(total)}, {speed:.1f} frames/s, left about {(n_frames - i) / speed / 60:.1f} min")
        write_audio(sound.shape[1])
        for p in v.encode():
            box.mux(p)
        for p in a.encode():
            box.mux(p)
    log(f"done: {path}  {os.path.getsize(path) / 1e6:.1f} MB, {total} s")


def main():
    args = sys.argv[1:]
    proc, page = open_page()
    try:
        if args and args[0] == "sheet":
            sheet(page, float(args[1]), float(args[2]), float(args[3]))
        elif args and args[0] == "audio":
            os.makedirs(OUT, exist_ok=True)
            write_wav(os.path.join(OUT, "audio.wav"), soundtrack(page))
            log("audio written")
        else:
            film(page, *(args[:1]))
    finally:
        proc.kill()


if __name__ == "__main__":
    main()
