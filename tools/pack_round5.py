"""Собирает макет призов mockups/art/round5.html в один файл для телефона: картинки вшиваются внутрь (WebP 256 px).

Запуск (из папки chess-leon):  C:\\AI\\sd\\venv\\Scripts\\python.exe tools\\pack_round5.py <куда положить .html>
"""

import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

ART = Path(__file__).resolve().parent.parent / "mockups" / "art"
img = {}
for f in sorted((ART / "out").glob("r5_*.png")):
    if f.stem.endswith("_raw"):
        continue
    pic = Image.open(f)
    pic.thumbnail((256, 256), Image.LANCZOS)
    buf = io.BytesIO()
    pic.save(buf, "WEBP", quality=82)
    img[f.stem[3:]] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
page = (ART / "round5.html").read_text(encoding="utf-8")
page = page.replace("<script>", f"<script>window.IMG = {json.dumps(img)};</script>\n<script>", 1)
out = Path(sys.argv[1])
out.write_text(page, encoding="utf-8")
print(f"{out.name}: {len(img)} pictures, {out.stat().st_size // 1024} KB")
