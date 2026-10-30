"""Образцы записанного голоса Леона: одни и те же фразы разными голосами и в разном темпе, чтобы выбрать на слух.
Движок и проверка — из C:\\projects\\CHESS\\voicekit. Пишет mockups/voice/leon_<голос>_<темп>.mp3 и mockups/voice/run.log.

Запуск: C:\\projects\\CHESS\\voicekit\\.venv\\Scripts\\python.exe -u tools\\voice_samples.py
"""
import sys
import time
from pathlib import Path

import numpy as np

KIT = Path(r"C:\projects\CHESS\voicekit")
sys.path.insert(0, str(KIT))
import voice_tool as V  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "mockups" / "voice"
OUT.mkdir(parents=True, exist_ok=True)
SPEAKERS = ["aidar", "eugene"]
TEMPOS = [1.0, 1.25]
PHRASES = [
    "Привет! Я Леон. Выбирай урок!",
    "Это ладья. Она ходит по прямой: вверх, вниз, влево и вправо — на сколько угодно клеток.",
    "Ладья умеет ловить мух! Нажми на ладью, а потом на клетку с мухой.",
    "Ферзь против шести пешек. Твой ход!",
    "А теперь без подсветки: найди клетку е четыре!",
    "Ой… Попробуй ещё разок!",
    "Урок пройден! Три звезды! Ты молодец!",
]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
log_file = open(OUT / "run.log", "w", encoding="utf-8")


def log(*a):
    line = " ".join([time.strftime("%H:%M:%S")] + [str(x) for x in a])
    print(line, flush=True)
    log_file.write(line + "\n")
    log_file.flush()


def main():
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log("device:", device)
    stress = V.load_stress(KIT / "stress.txt")
    log("loading Silero")
    engine = V.SileroEngine(SPEAKERS[0], device)
    log("loading the speech checker")
    try:
        checker = V.Checker(device, "openai/whisper-large-v3-turbo")
    except Exception as e:
        log("no checker:", e)
        checker = None
    for speaker in SPEAKERS:
        engine.speaker = speaker
        takes = []
        for text in PHRASES:
            t0 = time.time()
            y, sr = engine.synth(engine.variants(text, stress)[0], 0)
            secs = len(y) / sr
            if checker:
                heard = checker(y, sr)
                log(f"{speaker}: {secs:.1f} s of speech in {time.time() - t0:.1f} s, score {V.score(text, heard, V.KEYWORDS):.2f}, heard: {heard}")
            else:
                log(f"{speaker}: {secs:.1f} s of speech in {time.time() - t0:.1f} s")
            takes.append((y, sr))
        for tempo in TEMPOS:
            parts = []
            for y, sr in takes:
                c, out_sr = V.postprocess(y, sr, 1.0, tempo)
                parts += [c, np.zeros(int(out_sr * .55), np.float32)]
            path = OUT / f"leon_{speaker}_{tempo:.2f}.mp3"
            path.write_bytes(V.to_mp3(np.concatenate(parts), out_sr))
            log("written", path.name, f"{path.stat().st_size / 1024:.0f} KB")
    log("done")


if __name__ == "__main__":
    main()
