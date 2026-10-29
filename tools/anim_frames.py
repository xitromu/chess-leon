"""Кадры анимации из дорисовок по маске: все кадры одного героя режутся одной рамкой, чтобы при смене не прыгали.

Запуск (из папки chess-leon): C:\\AI\\sd\\venv\\Scripts\\python.exe tools\\anim_frames.py
Результат — mockups/art/anim/<кадр>.png и точки (рот и т. п.) в долях картинки — в журнал и anim/points.json.
"""

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from make_art import OUT, cut_full

ANIM = OUT.parent / "anim"

# герой: (кадры: имя → исходник _raw.png, маска дорисовки или None — кадр берётся целиком [, размытие края маски],
#         точки в точках исходника)
GROUPS = {
    "leon": ({"leon": ("toon_leon1_raw.png", None),
              "leon_sad": ("toon_leon1_sad_f_raw.png", (230, 320, 730, 690), 24),
              "leon_eat11": ("leon_eat_s11_raw.png", (390, 540, 720, 760)),
              "leon_eat21": ("leon_eat_s21_raw.png", (390, 540, 720, 760)),
              "leon_eat31": ("leon_eat_s31_raw.png", (390, 540, 720, 760))},
             {"mouth": (530, 620)}),
    "centi": ({"centi": ("r4_centi327_raw.png", None),
               "centi_walk11": ("centi_walk_s11_raw.png", (20, 580, 1000, 830)),
               "centi_walk21": ("centi_walk_s21_raw.png", (20, 580, 1000, 830))},
              {}),
    # жучок: дорисованы только лапки, мордочку (второй эллипс маски) не трогали — make_art.py fix2
    "beetle": ({"beetle": ("r4_beetle2b_raw.png", None),
                "beetle_walk11": ("beetle_walk_s11_raw.png", (90, 560, 860, 870, 470, 520, 710, 740)),
                "beetle_walk31": ("beetle_walk_s31_raw.png", (90, 560, 860, 870, 470, 520, 710, 740))},
               {}),
}


def soft(box, size, blur=10):
    """Мягкая маска-эллипс; если в box восемь чисел — из первого эллипса вырезан второй."""
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse(box[:4], fill=255)
    if len(box) == 8:
        ImageDraw.Draw(m).ellipse(box[4:], fill=0)
    return m.filter(ImageFilter.GaussianBlur(blur))


# головы для тел-лент в игре: (картинка, эллипс лица, прямоугольник усиков) в точках картинки
HEADS = {
    "worm_head": ("r4_worm.png", (14, 40, 318, 372), (120, 0, 210, 120)),
    "cater_head": ("r4_cater.png", (8, 48, 368, 368), (135, 0, 228, 80)),
}


def heads() -> None:
    """Головы червячка и гусеницы: круглое лицо с усиками, без шеи и ножек."""
    for name, (src, face, horns) in HEADS.items():
        im = Image.open(OUT / src).convert("RGBA")
        m = Image.new("L", im.size, 0)
        d = ImageDraw.Draw(m)
        d.ellipse(face, fill=255)
        d.rectangle(horns, fill=255)
        a = ImageChops.multiply(im.getchannel("A"), m.filter(ImageFilter.GaussianBlur(3)))
        im.putalpha(a)
        im.crop(a.point(lambda v: 255 if v > 20 else 0).getbbox()).save(ANIM / f"{name}.png")
        print("saved", name, flush=True)


def main() -> None:
    ANIM.mkdir(exist_ok=True)
    heads()
    points = {}
    for hero, (frames, marks) in GROUPS.items():
        base = Image.open(OUT / frames[hero][0]).convert("RGB")
        cut = {}
        for name, (src, box, *blur) in frames.items():
            img = Image.open(OUT / src).convert("RGB")
            if box:  # вне маски — пиксели исходника: голова и туловище в кадрах совпадают точь-в-точь
                img = Image.composite(img, base, soft(box, img.size, *blur))
            cut[name] = cut_full(img)
        boxes = [c.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox() for c in cut.values()]
        pad = 12
        x0, y0 = min(b[0] for b in boxes) - pad, min(b[1] for b in boxes) - pad
        x1, y1 = max(b[2] for b in boxes) + pad, max(b[3] for b in boxes) + pad
        for name, c in cut.items():
            c = c.crop((x0, y0, x1, y1))
            c.thumbnail((512, 512), Image.LANCZOS)
            c.save(ANIM / f"{name}.png")
            print("saved", name, c.size, flush=True)
        points[hero] = {k: [round((x - x0) / (x1 - x0), 3), round((y - y0) / (y1 - y0), 3)] for k, (x, y) in marks.items()}
    (ANIM / "points.json").write_text(json.dumps(points, ensure_ascii=False, indent=1), encoding="utf-8")
    print(points)


if __name__ == "__main__":
    main()
