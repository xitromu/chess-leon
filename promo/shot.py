"""One frame at full size: shot.py 34.0 -> out/shot_34.0.jpg"""
import os, sys
from render import open_page, OUT
proc, page = open_page()
try:
    for t in sys.argv[1:]:
        page.js(f"renderAt({float(t)})")
        open(os.path.join(OUT, f"shot_{t}.jpg"), "wb").write(page.shot(quality=90))
finally:
    proc.kill()
