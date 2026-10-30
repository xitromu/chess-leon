"""Озвучка игры голосом Silero: каждый кусочек из mockups/voice/parts.json (его собирает voice_collect.py) → voice/<ключ>.mp3.
Уже записанное не трогает; в конце вписывает список записей в index.html (блок VOICE START … VOICE END).
Отчёт о проверке распознаванием — mockups/voice/report.csv, слабые фразы сверху.

Запуск: C:\\projects\\CHESS\\voicekit\\.venv\\Scripts\\python.exe -u tools\\voice_build.py
        ... voice_build.py --redo "ладь|шах"     переписать кусочки, подходящие под это выражение
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

KIT = Path(r"C:\projects\CHESS\voicekit")
sys.path.insert(0, str(KIT))
import voice_tool as V  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK, CLIPS, HTML = ROOT / "mockups" / "voice", ROOT / "voice", ROOT / "index.html"
SPEAKER, TEMPO, KBPS = "aidar", 1.25, 40
LETTERS = dict(a="а", b="бэ", c="цэ", d="дэ", e="е", f="эф", g="жэ", h="аш")
ONES = ["ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять", "десять", "одиннадцать", "двенадцать",
        "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]
# где произносим не как написано: у Silero слабое начало фразы, а «р-р-р» он читает по слогам (проверено распознаванием 30.10.2026)
SAY = [(r"^[Лл]адья( —)?$", "Ладья!"), (r"^[Лл]адья(?= [^—])", "Лладья"), (r"^Кто ходит", "Ккто ходит"), (r"р-р-р", "ррр"), (r"^(Мат|Пат)$", r"\1!")]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
log_file = None


def log(*a):
    line = " ".join([time.strftime("%H:%M:%S")] + [str(x) for x in a])
    print(line, flush=True)
    log_file.write(line + "\n")
    log_file.flush()


def number(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return HUNDREDS[n // 100] + ("" if n % 100 == 0 else " " + number(n % 100))
    return str(n)


def spoken(part):
    """Что произнести: кусочек текста с поправками SAY, а #e4, #e, #3, #2ж, #1у — словами."""
    if not part.startswith("#"):
        for a, b in SAY:
            part = re.sub(a, b, part)
        return part
    t = part[1:]
    if t == "1ж":
        return "одна"
    if t == "1у":
        return "одну"
    if t == "2ж":
        return "две"
    if re.fullmatch("[a-h][1-8]", t):
        return f"{LETTERS[t[0]]} {number(int(t[1]))}"
    if t in LETTERS:
        return LETTERS[t]
    return number(int(t))


def main():
    global log_file
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", help="переписать кусочки, где есть это сочетание букв")
    ap.add_argument("--limit", type=int, help="только первые N кусочков (проба)")
    args = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    log_file = open(WORK / "build.log", "a", encoding="utf-8")
    parts = sorted(json.loads((WORK / "parts.json").read_text(encoding="utf-8")), key=len)
    keys = {V.hkey(p): p for p in parts}
    if len(keys) != len(parts):
        sys.exit("совпали ключи разных кусочков")
    report = {}
    if (WORK / "report.csv").exists():
        with open(WORK / "report.csv", encoding="utf-8") as f:
            report = {r["key"]: r for r in csv.DictReader(f)}

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    todo = [p for p in parts if not (CLIPS / f"{V.hkey(p)}.mp3").exists() or (args.redo and re.search(args.redo, spoken(p), re.I))]
    if args.limit:
        todo = todo[:args.limit]
    log(f"device {device}; parts {len(parts)}, to record {len(todo)}")
    if todo:
        stress = V.load_stress(KIT / "stress.txt")
        stress.update(V.load_stress(ROOT / "tools" / "voice_stress.txt"))
        engine = V.SileroEngine(SPEAKER, device)
        log("loading the speech checker, this takes a couple of minutes")
        checker = V.Checker(device, "openai/whisper-large-v3-turbo")
        t0 = time.time()
        for i, p in enumerate(todo):
            text = spoken(p)
            best = (-9.0, None, "")
            for v in engine.variants(text, stress):
                y = engine.model.apply_tts(text=v, speaker=SPEAKER, sample_rate=engine.sr, put_accent=True, put_yo=False).detach().cpu().numpy().astype("float32")
                heard = checker(y, engine.sr)
                sc = V.score(p if not p.startswith("#") else text, heard, V.KEYWORDS)
                if sc > best[0]:
                    best = (sc, y, heard)
                if sc >= .97:
                    break
            y, sr = V.postprocess(best[1], engine.sr, 1.0, TEMPO)
            (CLIPS / f"{V.hkey(p)}.mp3").write_bytes(V.to_mp3(y, sr, KBPS))
            report[V.hkey(p)] = {"key": V.hkey(p), "text": p, "score": round(best[0], 3), "heard": best[2]}
            if i % 25 == 0 or i == len(todo) - 1:
                speed = (i + 1) / (time.time() - t0)
                log(f"  {i + 1} of {len(todo)}, {speed:.1f} parts/s, left about {(len(todo) - i) / speed / 60:.1f} min; last: {text[:50]}")

    rows = sorted([report[k] for k in keys if k in report], key=lambda r: float(r["score"]))
    with open(WORK / "report.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["key", "text", "score", "heard"])
        w.writeheader()
        w.writerows(rows)
    gone = [f for f in CLIPS.glob("*.mp3") if f.stem not in keys]
    for f in gone:
        f.unlink()
    have = sorted(k for k in keys if (CLIPS / f"{k}.mp3").exists())
    size = sum((CLIPS / f"{k}.mp3").stat().st_size for k in have)
    html = HTML.read_text(encoding="utf-8")
    block = ("// VOICE START (вписывает tools/voice_build.py)\n"
             f"const VOICE_KEYS = new Set('{' '.join(have)}'.split(' ').filter(Boolean));\n"
             f"const VOICE_MB = {max(1, round(size / 1e6))};\n// VOICE END")
    new, n = re.subn(r"// VOICE START.*?// VOICE END", lambda m: block, html, flags=re.S)
    if n != 1:
        sys.exit("в index.html нет блока VOICE START … VOICE END")
    HTML.write_text(new, encoding="utf-8", newline="\n")
    weak = [r for r in rows if float(r["score"]) < .8]
    log(f"recorded {len(have)} of {len(parts)}, {size / 1e6:.1f} MB; removed old {len(gone)}; weak below 0.8: {len(weak)}")
    for r in weak[:25]:
        log(f"  {r['score']}  {r['text'][:70]}  ->  {r['heard'][:70]}")
    log("done")


if __name__ == "__main__":
    main()
