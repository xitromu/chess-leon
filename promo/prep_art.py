"""Characters for the cartoon: the same pictures and the same clean-up as in the game (tools/build_art.py), but full size.
Writes art/<name>.png and art/manifest.json (sizes and wing roots).

Run:  C:\\TST\\python.exe prep_art.py
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import build_art as B  # noqa: E402

OUT = os.path.join(HERE, "art")
EXTRA = {"g_rocket2": "r4_g_rocket"}


def main():
    os.makedirs(OUT, exist_ok=True)
    boxes = {}
    for group in B.SHARED:
        bs = [B.bbox(B.load(B.ART[k][0])) for k in group]
        union = (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
        boxes.update({k: union for k in group})
    sizes = {}
    for key, (name, _) in B.ART.items():
        im = B.load(name)
        im = im.crop(boxes.get(key) or B.bbox(im))
        im.save(os.path.join(OUT, key + ".png"))
        sizes[key] = [im.width, im.height]
    roots = {}
    for k in B.FLYERS:
        im = B.load(B.ART[k][0])
        x0, y0, x1, y1 = boxes[k]
        roots[k] = [[round((p[0] * im.width - x0) / (x1 - x0), 3), round((p[1] * im.height - y0) / (y1 - y0), 3)]
                    for w, p in B.WINGS[k].items() if w.startswith("w")]
    with open(os.path.join(OUT, "manifest.js"), "w", encoding="utf-8") as f:
        f.write("window.SIZES = " + json.dumps(sizes) + ";\nwindow.ROOTS = " + json.dumps(roots) + ";\n")
    print(len(sizes), "pictures")


if __name__ == "__main__":
    main()
