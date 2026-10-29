"""Крылья летающих букашек отдельными слоями: машут только крылья, голова и тельце неподвижны.

Запуск (из папки chess-leon): C:\\AI\\sd\\venv\\Scripts\\python.exe tools\\wings.py
Результат — mockups/art/anim/<букашка>_body.png и _w1.png, _w2.png … (все слои одного размера, одной рамкой)
и точки крепления крыльев в долях картинки — anim/wings.json.
Два способа:
- cut — непрозрачные крылья (мотылёк, бабочка) вырезаются из самой картинки: тельце — по эллипсам, остальное — крылья;
- glass — прозрачные крылья при срезании фона рвутся или пропадают (у мухи осталось одно, у комарика ни одного),
  поэтому тельце обрезается по эллипсам, а крылья рисуются заново: стеклянные, с жилками.
Вся разметка — в точках исходника _raw.png (1024 × 1024).
"""

import json
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from make_art import OUT, cut_full

ANIM = OUT.parent / "anim"
SS = 3  # рисуем крылья крупнее и уменьшаем — края гладкие
GLASS = (215, 236, 255, 120)    # обычное стеклянное крыло
YELLOW = (255, 246, 190, 125)   # пчёлка
GLOW = (255, 245, 140, 165)     # светлячок
BLUE = (200, 235, 255, 125)     # стрекоза

# cut: (исходник, срез фона tint, эллипсы тельца, x раздела левое/правое, точки крепления w1 (левое), w2 (правое)
#       [, овалы крыльев — крыло берётся только внутри своего: иначе к нему цепляется пушистый край головы])
CUT = {
    "moth": ("r4_moth_raw.png", 22, [(256, 176, 776, 552), (370, 530, 670, 840), (420, 820, 620, 880), (500, 100, 540, 200)],
             512, (395, 590), (640, 600), [(90, 470, 405, 710), (628, 492, 900, 720)]),
    "butter": ("r4_butter_raw.png", 40, [(260, 350, 610, 600), (370, 590, 570, 800), (360, 750, 610, 870), (440, 150, 600, 360)],
               470, (420, 600), (540, 590)),
}
# glass: (исходник, срез фона tint, эллипсы тельца или None — тельце целиком,
#         крылья: [(корень, кончик, ширина, цвет, жилок)] — по порядку w1, w2 …)
GLASSES = {
    "fly": ("r4_fly2b_raw.png", 55, [(150, 420, 800, 960)],
            [((515, 520), (470, 210), 130, GLASS, 3), ((545, 545), (900, 170), 170, GLASS, 3)]),
    "mosquito": ("r4_mosquito_raw.png", 45, None,
                 [((512, 610), (40, 500), 120, GLASS, 2), ((512, 610), (984, 500), 120, GLASS, 2)]),
    "dragon": ("r4_dragon_raw.png", 30, [(350, 180, 720, 480), (320, 80, 730, 220), (440, 460, 610, 580), (320, 540, 600, 820),
                                         (240, 580, 560, 880)],
               [((470, 480), (90, 220), 130, BLUE, 3), ((470, 500), (60, 550), 110, BLUE, 3),
                ((560, 480), (950, 260), 130, BLUE, 3), ((560, 500), (910, 560), 110, BLUE, 3)]),
    "bee": ("r4_bee_raw.png", 50, [(290, 180, 760, 530), (300, 520, 610, 820), (310, 720, 620, 900), (590, 520, 720, 610),
                                   (450, 100, 750, 230)],
            [((410, 570), (30, 420), 150, YELLOW, 3), ((600, 580), (830, 520), 110, YELLOW, 2)]),
    "firefly": ("toon_firefly_s23b_raw.png", 50, [(280, 280, 610, 600), (370, 580, 580, 840), (300, 800, 660, 910),
                                                  (100, 140, 780, 330), (290, 600, 420, 760)],
                [((380, 600), (70, 470), 170, GLOW, 3), ((400, 640), (250, 760), 90, GLOW, 2),
                 ((580, 580), (970, 420), 170, GLOW, 3), ((560, 640), (680, 770), 90, GLOW, 2)]),
    "bug": ("r4_lady317_raw.png", 70, [(280, 330, 780, 832), (290, 340, 540, 470)],  # розоватый пол — строже
            [((620, 520), (770, 160), 110, GLASS, 2), ((600, 540), (920, 260), 130, GLASS, 3)]),
}


FRONT = {"fly": ("w2",), "bug": ("w2",)}  # крылья перед тельцем (вид сбоку — ближнее крыло), остальные — за ним


def ellipses(boxes, size=(1024, 1024), blur=3):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for b in boxes:
        d.ellipse(b, fill=255)
    return m.filter(ImageFilter.GaussianBlur(blur))


def glass_wing(length, width, fill=GLASS, veins=3):
    """Прозрачное крыло, корень слева посередине, кончик справа."""
    w, h = length * SS, width * SS
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    edge = tuple(max(0, c - 90) for c in fill[:3]) + (235,)
    d.ellipse((0, 0, w - 1, h - 1), fill=fill, outline=edge, width=5 * SS)
    for k in range(1, veins + 1):  # жилки веером от корня
        y = h * k / (veins + 1)
        d.line([(int(w * .04), h // 2), (int(w * .55), int(h / 2 + (y - h / 2) * .8)), (int(w * .93), int(y))],
               fill=edge[:3] + (170,), width=3 * SS, joint="curve")
    d.ellipse((int(w * .1), int(h * .2), int(w * .5), int(h * .42)), fill=(255, 255, 255, 70))  # блик
    return im.resize((length, width), Image.LANCZOS)


def place(wing, root, tip, size=(1024, 1024)):
    """Кладёт крыло на холст: корень в точке root, кончик смотрит на tip."""
    ang = math.degrees(math.atan2(tip[1] - root[1], tip[0] - root[0]))
    w, h = wing.size
    pad = Image.new("RGBA", (w * 2, w * 2), (0, 0, 0, 0))  # квадрат: повёрнутое крыло не обрежется
    pad.paste(wing, (w, w - h // 2))  # корень — в центре pad
    rot = pad.rotate(-ang, resample=Image.BICUBIC, center=(w, w))
    canvas = Image.new("RGBA", (size[0] + 2 * w, size[1] + 2 * w), (0, 0, 0, 0))
    canvas.alpha_composite(rot, (int(root[0]), int(root[1])))
    return canvas.crop((w, w, w + size[0], w + size[1]))


def cut_hero(src, tint, body_boxes, split, root1, root2, wing_boxes=None):
    full = cut_full(Image.open(OUT / src).convert("RGB"), tint=tint)
    a = full.getchannel("A")
    keep = ImageChops.multiply(a, ellipses(body_boxes))
    out = {"body": full.copy()}
    out["body"].putalpha(keep)
    rest = ImageChops.subtract(a, keep)
    for k, (name, box) in enumerate((("w1", (0, 0, split, 1024)), ("w2", (split, 0, 1024, 1024)))):
        side = Image.new("L", (1024, 1024), 0)
        ImageDraw.Draw(side).rectangle(box, fill=255)
        if wing_boxes:
            side = ImageChops.multiply(side, ellipses([wing_boxes[k]], blur=1))
        wing = full.copy()
        wing.putalpha(ImageChops.multiply(rest, side))
        out[name] = wing
    return out, {"w1": root1, "w2": root2}


def glass_hero(src, tint, body_boxes, wings):
    body = cut_full(Image.open(OUT / src).convert("RGB"), tint=tint)
    if body_boxes:  # обрывки старых крыльев — прочь, остаются голова, тельце и лапки
        body.putalpha(ImageChops.multiply(body.getchannel("A"), ellipses(body_boxes, blur=2)))
    out, roots = {"body": body}, {}
    for k, (root, tip, width, fill, veins) in enumerate(wings, start=1):
        length = int(math.dist(root, tip))
        out[f"w{k}"] = place(glass_wing(length, width, fill, veins), root, tip)
        roots[f"w{k}"] = root
    return out, roots


def main() -> None:
    ANIM.mkdir(exist_ok=True)
    points = {}
    jobs = [(h, cut_hero, a) for h, a in CUT.items()] + [(h, glass_hero, a) for h, a in GLASSES.items()]
    for hero, make, args in jobs:
        layers, roots = make(*args)
        box = None
        for im in layers.values():
            b = im.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        pad = 12
        box = (max(0, box[0] - pad), max(0, box[1] - pad), min(1024, box[2] + pad), min(1024, box[3] + pad))
        bw, bh = box[2] - box[0], box[3] - box[1]
        # целиком (значок в банке с едой): задние крылья, тельце, передние
        full = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        for name in sorted(layers, key=lambda n: 1 if n == "body" else 2 if n in FRONT.get(hero, ()) else 0):
            full.alpha_composite(layers[name])
        layers["full"] = full
        for name, im in layers.items():
            im = im.crop(box)
            im.thumbnail((512, 512), Image.LANCZOS)
            im.save(ANIM / f"{hero}_{name}.png")
        points[hero] = {k: [round((x - box[0]) / bw, 3), round((y - box[1]) / bh, 3)] for k, (x, y) in roots.items()}
        points[hero]["aspect"] = round(bw / bh, 3)
        print(hero, points[hero], flush=True)
    (ANIM / "wings.json").write_text(json.dumps(points, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
