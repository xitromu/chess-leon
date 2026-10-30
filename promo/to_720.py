"""Phone version of the finished film: 720 x 1280, the sound as it is. Writes out/Chess_Leon_promo_720p.mp4.

Run:  C:\\TST\\python.exe to_720.py
"""
import os
from fractions import Fraction

import av

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SRC, DST = os.path.join(OUT, "Chess_Leon_promo.mp4"), os.path.join(OUT, "Chess_Leon_promo_720p.mp4")
W, H, FPS = 720, 1280, 30

with av.open(SRC) as src, av.open(DST, "w", options={"movflags": "faststart"}) as dst:
    v = dst.add_stream("libx264", rate=FPS)
    v.width, v.height, v.pix_fmt = W, H, "yuv420p"
    v.options = {"crf": "23", "preset": "slow", "profile": "high", "level": "3.1"}
    a = dst.add_stream_from_template(src.streams.audio[0])
    for i, fr in enumerate(src.decode(video=0)):
        small = fr.reformat(W, H, "yuv420p", interpolation="LANCZOS")
        small.pts, small.time_base = i, Fraction(1, FPS)
        for p in v.encode(small):
            dst.mux(p)
    for p in v.encode():
        dst.mux(p)
    src.seek(0)
    for p in src.demux(src.streams.audio[0]):
        if p.dts is not None:
            p.stream = a
            dst.mux(p)

with av.open(DST) as box:
    s = box.streams.video[0]
    print(f"{s.width}x{s.height}, {s.frames} frames, {float(box.duration) / 1e6:.1f} s, audio: {box.streams.audio[0].codec_context.name}, {os.path.getsize(DST) / 1e6:.1f} MB")
