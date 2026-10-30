"""Contact sheet of a take, to look at it without watching the video: contact.py <take> [every_n_frames] -> frames/sheet_<take>.jpg"""
import glob, os, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
take, every = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30
files = sorted(glob.glob(os.path.join(HERE, "frames", take, "*.jpg")))[::every]
w, h, cols = 206, 365, 8
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (w + 4), rows * (h + 4)), "white")
for i, p in enumerate(files):
    sheet.paste(Image.open(p).resize((w, h)), (i % cols * (w + 4), i // cols * (h + 4)))
sheet.save(os.path.join(HERE, "frames", f"sheet_{take}.jpg"), quality=85)
print(take, len(files), sheet.size)
