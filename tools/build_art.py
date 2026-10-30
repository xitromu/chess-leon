"""Сборка картинок для игры: берёт выбранные PNG из mockups/art/out, обрезает прозрачные поля,
ужимает, переводит в WebP и вписывает в index.html как data:-строки (блок между ART START и ART END).

Запуск: C:\\AI\\sd\\venv\\Scripts\\python.exe tools\\build_art.py
"""
import base64, io, json, re, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'mockups' / 'art' / 'out'
HTML = ROOT / 'index.html'

# имя в игре: (файл, длинная сторона в точках)
ART = {
    'leon': ('../anim/leon', 420), 'leonSad': ('../anim/leon_sad', 420), 'leonEat': ('../anim/leon_eat21', 420),
    'malon': ('toon_malon_s17', 200), 'hedge': ('toon_hedge', 200), 'turtle': ('r4_turtle_b', 200),
    'parrot': ('r4_parrot_b', 200), 'axo': ('r4_axo_a', 200),
    'g_balloons': ('r4_g_balloons', 200), 'g_cake': ('r4_g_cake', 160), 'g_chest': ('r4_g_chest', 160),
    'g_cup': ('r4_g_cup', 160), 'g_rocket': ('r4_g_rocket', 160), 'g_bubbles': ('r4_g_bubbles', 160),
    'g_wand': ('r4_g_wand', 160), 'g_paint': ('r4_g_paint', 160),
    # 10 новых призов (выбор 29.10 по mockups/art/round5.html)
    'g_medal': ('r5_medal37', 160), 'g_flowers': ('r5_flowers27', 160), 'g_confetti': ('r5_confetti27', 160),
    'g_garland': ('r5_garland27', 220), 'g_drum': ('r5_drum27', 160), 'g_musicbox': ('r5_musicbox17', 160),
    'g_hammock': ('r5_hammock27', 220), 'g_nightlight': ('r5_nightlight37', 160), 'g_house': ('r5_house27', 200),
    'g_boardpaint': ('r5_boardpaint47', 160),
    'ant': ('r4_ant_mouth_s11', 96), 'fly': ('r4_fly2b', 96), 'worm': ('r4_worm', 96), 'beetle': ('../anim/beetle', 96),
    'bug': ('r4_lady317', 96), 'cater': ('r4_cater', 96), 'centi': ('../anim/centi', 96), 'hopper': ('r4_hopper', 96),
    'centi2': ('../anim/centi_walk11', 96), 'centi3': ('../anim/centi_walk21', 96),
    'beetle2': ('../anim/beetle_walk11', 96), 'beetle3': ('../anim/beetle_walk31', 96),
    'dragon': ('r4_dragon', 96), 'fish': ('r4_fish_side17', 120), 'butter': ('r4_butter', 96), 'frog': ('r4_frog', 96),
    'firefly': ('toon_firefly_s23b', 96), 'bee': ('r4_bee', 96), 'mosquito': ('r4_mosquito', 96), 'moth': ('r4_moth', 96),
    'spider': ('r4_spider', 96), 'snail': ('r4_snail', 96), 'cricket': ('r4_cricket', 96), 'stag': ('r4_stag', 96),
    'louse': ('r4_louse', 96), 'wormHead': ('../anim/worm_head', 120), 'caterHead': ('../anim/cater_head', 120),
}
# летуны (tools/wings.py): значок — букашка целиком, в террариуме — тельце и крылья отдельно, машут только крылья
FLYERS = ['mosquito', 'fly', 'moth', 'bug', 'firefly', 'bee', 'dragon', 'butter']
WINGS_JSON = ROOT / 'mockups' / 'art' / 'anim' / 'wings.json'
WINGS = json.loads(WINGS_JSON.read_text(encoding='utf-8'))
for k in FLYERS:
    ART[k] = (f'../anim/{k}_full', 96)
    ART[k + '_b'] = (f'../anim/{k}_body', 96)
    ART.update({f'{k}_{w}': (f'../anim/{k}_{w}', 96) for w in WINGS[k] if w.startswith('w')})


# кадры одной анимации (tools/anim_frames.py) режутся общей рамкой — иначе при смене кадра герой прыгает
SHARED = [('leon', 'leonSad', 'leonEat'), ('centi', 'centi2', 'centi3'), ('beetle', 'beetle2', 'beetle3')] + [
    tuple(k2 for k2 in ART if k2 == k or k2.startswith(k + '_')) for k in FLYERS]


# у этих фон срезался не весь: под лапками остался светлый «пол»
FLOOR = {'toon_malon_s17': .34, 'toon_hedge': .22, 'r4_axo_a': .22}  # доля высоты снизу, где ищем пол


def defloor(im, band=.22):
    """Стирает светлый малоцветный «пол», связанный с краями нижней полосы картинки."""
    px, (w, h) = im.load(), im.size
    y0 = int(h * (1 - band))
    def floor(x, y):
        r, g, b, a = px[x, y]
        return a > 0 and min(r, g, b) > 105 and max(r, g, b) - min(r, g, b) < 60
    stack = [(x, y) for y in range(y0, h) for x in (0, w - 1)] + [(x, h - 1) for x in range(w)]
    stack += [(x, y) for y in range(y0, h) for x in range(w) if px[x, y][3] == 0]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and y0 <= y < h):
            continue
        seen.add((x, y))
        if px[x, y][3] == 0 or floor(x, y):
            if px[x, y][3]:
                px[x, y] = (0, 0, 0, 0)
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return im


def load(name):
    im = Image.open(SRC / f'{name}.png').convert('RGBA')
    return defloor(im, FLOOR[name]) if name in FLOOR else im


def bbox(im):
    # поля считаем по заметной прозрачности: остатки фона бывают почти невидимыми
    return im.getchannel('A').point(lambda a: 255 if a > 24 else 0).getbbox()


def webp(name, size, box=None):
    im = load(name)
    im = im.crop(box or bbox(im))
    k = size / max(im.size)
    if k < 1:
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'WEBP', quality=82, method=6)
    return buf.getvalue(), im.size


def main():
    lines, total, boxes = [], 0, {}
    for group in SHARED:
        bs = [bbox(load(ART[k][0])) for k in group]
        union = (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
        boxes.update({k: union for k in group})
    for key, (name, size) in ART.items():
        data, (w, h) = webp(name, size, boxes.get(key))
        total += len(data)
        print(f'{key:11} {name:20} {w}x{h} {len(data) // 1024} КБ')
        lines.append(f"  {key}: 'data:image/webp;base64,{base64.b64encode(data).decode()}',")
    block = '// ART START (вписывает tools/build_art.py)\nconst ART = {\n' + '\n'.join(lines) + '\n};\n// ART END'
    wings = []
    for k in FLYERS:  # точки крепления крыльев — в долях картинки после общей обрезки
        im = load(ART[k][0])
        x0, y0, x1, y1 = boxes[k]
        roots = {w: [round((p[0] * im.width - x0) / (x1 - x0), 3), round((p[1] * im.height - y0) / (y1 - y0), 3)]
                 for w, p in WINGS[k].items() if w.startswith('w')}
        wings.append(f"  {k}: {{ aspect: {round((x1 - x0) / (y1 - y0), 3)}, roots: {json.dumps(list(roots.values()))} }},")
    wblock = '// WINGS START (вписывает tools/build_art.py)\nconst WINGS = {\n' + '\n'.join(wings) + '\n};\n// WINGS END'
    html = HTML.read_text(encoding='utf-8')
    new, n = re.subn(r'// ART START.*?// ART END', lambda m: block, html, flags=re.S)
    new, n2 = re.subn(r'// WINGS START.*?// WINGS END', lambda m: wblock, new, flags=re.S)
    if n != 1 or n2 != 1:
        sys.exit('В index.html нет блока ART START … ART END или WINGS START … WINGS END')
    HTML.write_text(new, encoding='utf-8', newline='\n')
    print(f'Итого: {total // 1024} КБ картинок, index.html — {len(new.encode()) // 1024} КБ')


if __name__ == '__main__':
    main()
