"""Стирает серую тень под жучком в кадрах ходьбы (её дорисовала нейросеть, и при смене кадров тень мигала).
Тень — малоцветные пиксели, связанные с прозрачным фоном; глаза (справа сверху) не трогаем.
Исходники сохраняются рядом как *_orig.png (один раз).

Запуск: C:\AI\sd\venv\Scripts\python.exe tools\deshadow.py [папка_для_пробы]
"""
import sys
from pathlib import Path
from PIL import Image

ANIM = Path(__file__).resolve().parent.parent / 'mockups' / 'art' / 'anim'
NAMES = ['beetle', 'beetle_walk11', 'beetle_walk31']


def grey(p):
    r, g, b, a = p
    return a > 0 and max(r, g, b) - min(r, g, b) < max(r, g, b) * .32 + 8


def deshadow(im):
    px, (w, h) = im.load(), im.size
    eye = lambda x, y: x > w * .5 and y < h * .62
    stack = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] == 0]
    seen = set(stack)
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not eye(nx, ny) and grey(px[nx, ny]):
                seen.add((nx, ny)); px[nx, ny] = (0, 0, 0, 0); stack.append((nx, ny))
    return im


if __name__ == '__main__':
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ANIM
    for n in NAMES:
        orig = ANIM / f'{n}_orig.png'
        if not orig.exists():
            orig.write_bytes((ANIM / f'{n}.png').read_bytes())
        deshadow(Image.open(orig).convert('RGBA')).save(out / f'{n}.png')
        print(n, 'ok')
