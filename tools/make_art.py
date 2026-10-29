"""Рисует картинки для «Шахмат с Леоном» программой Stable Diffusion XL (стоит в C:\\AI\\sd, работает на видеокарте).

Запуск (из папки chess-leon):
    C:\\AI\\sd\\venv\\Scripts\\python.exe tools\\make_art.py              пробный набор во всех стилях
    C:\\AI\\sd\\venv\\Scripts\\python.exe tools\\make_art.py toon leon1   только стиль toon, только leon1

Результат — mockups/art/out/<стиль>_<что>.png (фон срезан, прозрачный) и журнал mockups/art/out/log.txt.
Смотреть — mockups/mockup-2.0.html, раздел «Стиль рисования».
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch
from diffusers import AutoencoderKL, DPMSolverMultistepScheduler, StableDiffusionXLPipeline
from PIL import Image, ImageFilter

MODELS = "C:/AI/sd/models"
OUT = Path(__file__).resolve().parent.parent / "mockups" / "art" / "out"
SIZE = 1024
STEPS = 30
GUIDANCE = 7.0

# Стиль: объёмный и весёлый, на чистом белом фоне — фон потом срезаем
STYLES = {
    "toon": "3d render, cute animated movie character, pixar style, big expressive eyes, soft studio lighting, "
            "glossy, vibrant cheerful colors, isolated on a plain pure white background",
    "plush": "cute plush toy, soft felt and fleece fabric, fuzzy texture, visible stitches, embroidered eyes, "
             "e-commerce product photo on seamless pure white backdrop, soft light, vibrant cheerful colors, "
             "isolated on a plain pure white background",
    "clay": "claymation figure, cute plasticine character, handmade clay texture with fingerprints, stop motion "
            "style, soft lighting, vibrant cheerful colors, on seamless pure white backdrop, "
            "isolated on a plain pure white background",
}
AVOID = ("text, letters, watermark, signature, frame, border, multiple characters, cropped, cut off, scary, creepy, "
         "realistic photo of real animal, dark background, gradient background, scenery, ground, shadow, blurry, "
         "deformed, extra limbs")

# Что рисуем: (описание, зерно). Зерно — число, от которого зависит случайный рисунок: то же зерно — та же картинка.
SUBJECTS = {
    "leon1": ("a cute baby chameleon character, bright green, big round eyes, curled tail, small crest on the head, "
              "happy smile, sitting, full body, chibi proportions with big head, front view, centered", 11),
    "leon2": ("a cute baby chameleon character, bright green, big round eyes, curled tail, small crest on the head, "
              "happy smile, sitting, full body, chibi proportions with big head, front view, centered", 42),
    "malon": ("a cute baby gecko lizard character, reptile, smooth pale yellow lizard skin with dark brown spots, "
              "long thick striped tail, four short legs with round toe pads, no ears, no fur, big round eyes, "
              "happy smile, sitting, full body, chibi proportions with big head, front view, centered", 7),
    "hedge": ("a cute baby hedgehog character, brown spikes, cream face, tiny black nose, big round eyes, happy smile, "
              "sitting, full body, chibi proportions with big head, front view, centered", 5),
    "firefly": ("a cute small firefly beetle character, dark brown beetle body with red head shield, glowing "
                "luminous yellow-green lantern belly at the tail end, beetle wing covers, big eyes, smiling, "
                "full body, centered, simple icon", 3),
    "pirate": ("a black pirate tricorn hat with a white skull and crossbones and a gold trim, single object, "
               "front view, centered, game item icon", 9),
}


# Чего не должно быть у отдельного рисунка (добавка к AVOID): первый заход дал Малона-котёнка и светлячка-пчелу.
AVOID_FOR = {
    "malon": "cat, leopard cub, kitten, mammal, fur, furry, ears, whiskers",
    "firefly": "bee, wasp, black and yellow stripes, stinger, honey",
}


def cut_background(img: Image.Image, tint: int = 22, light: int = 120) -> Image.Image:
    """Срезает фон: заливкой от краёв убирает всё бесцветное и светлое (белый, серый, тени на полу).
    Цветной персонаж остаётся; белки глаз и зубы окружены цветом — до них заливка не доходит.
    tint — насколько цветным может быть фон (тёплая подсветка пола требует больше)."""
    out = cut_full(img, tint, light)
    box = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    if box:
        pad = 12
        out = out.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(out.width, box[2] + pad), min(out.height, box[3] + pad)))
    out.thumbnail((512, 512), Image.LANCZOS)
    return out


def cut_full(img: Image.Image, tint: int = 22, light: int = 120) -> Image.Image:
    """То же, что cut_background, но без обрезки и уменьшения: кадры одной анимации режутся потом одной рамкой."""
    rgb = np.asarray(img.convert("RGB")).astype(np.int16)
    h, w, _ = rgb.shape
    whiteish = ((rgb.max(axis=2) - rgb.min(axis=2)) < tint) & (rgb.min(axis=2) > light)
    bg = np.zeros((h, w), bool)
    stack = [(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)] + [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)]
    while stack:
        y, x = stack.pop()
        if bg[y, x] or not whiteish[y, x]:
            continue
        bg[y, x] = True
        if y > 0: stack.append((y - 1, x))
        if y < h - 1: stack.append((y + 1, x))
        if x > 0: stack.append((y, x - 1))
        if x < w - 1: stack.append((y, x + 1))
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out


# Второй заход (после выбора стиля): настроения Леона 1 — перерисовкой его же картинки (img2img), чтобы лицо и цвет
# сохранились; плюс то, что в первом заходе не вышло. Запуск: make_art.py r2
LEON = ("a cute baby chameleon character, bright green, big round eyes, curled tail, small crest on the head, {mood}, "
        "full body, chibi proportions with big head, front view, centered")
MOODS = {
    "happy": "overjoyed laughing with wide open mouth, both arms raised up high in celebration, sitting",
    "sad": "sad and upset, teary eyes, frowning mouth, droopy eyelids, hugging itself, sitting",
}
R2_EDIT = [(mood, strength) for mood in MOODS for strength in (0.5, 0.65)]
R2_NEW = [
    ("toon", "malon", 17), ("toon", "malon", 27),
    ("toon", "firefly", 13), ("toon", "firefly", 23),
    ("plush", "hat", 9), ("plush", "hat", 19),
]
SUBJECTS["firefly"] = ("a cute cartoon firefly insect character, small round body, tiny transparent wings, two antennae, "
                       "its tail end glows bright warm yellow like a little lantern, big friendly eyes, smiling, "
                       "full body, centered", 3)
SUBJECTS["hat"] = ("a plush pirate tricorn hat made of black felt with a small embroidered white skull and crossbones "
                   "and gold trim, only the hat, empty hat, no head, no face, single object, front view, centered, "
                   "game item icon", 9)
AVOID_FOR["firefly"] += ", robot, armor, mechanical, red beetle"
AVOID_FOR["hat"] = "skull face below the hat, head, person, mannequin, character wearing the hat"


def round2(pipe, note) -> None:
    from diffusers import StableDiffusionXLImg2ImgPipeline
    for style, key, seed in R2_NEW:
        started = time.time()
        image = pipe(prompt=f"{SUBJECTS[key][0]}, {STYLES[style]}",
                     negative_prompt=", ".join(filter(None, [AVOID, AVOID_FOR.get(key)])),
                     width=SIZE, height=SIZE, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                     generator=torch.Generator("cpu").manual_seed(seed)).images[0]
        name = f"{style}_{key}_s{seed}"
        image.save(OUT / f"{name}_raw.png")
        cut_background(image).save(OUT / f"{name}.png")
        note(f"SAVED {name}.png ({time.time() - started:.0f} s)")
    # отдельная загрузка: from_pipe теряет экономию видеопамяти — 110–140 с на шаг вместо 0,7
    edit =StableDiffusionXLImg2ImgPipeline.from_pretrained(
        f"{MODELS}/sdxl-base", vae=AutoencoderKL.from_pretrained(f"{MODELS}/sdxl-vae-fp16-fix", torch_dtype=torch.float16),
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    edit.scheduler = DPMSolverMultistepScheduler.from_config(edit.scheduler.config, use_karras_sigmas=True)
    edit.enable_model_cpu_offload()
    base = Image.open(OUT / "toon_leon1_raw.png").convert("RGB")
    for mood, strength in R2_EDIT:
        started = time.time()
        # CLIP читает только первые 77 слов-токенов: фон и стиль — в начало, иначе они отрезаются
        image = edit(prompt=f"isolated on plain white background, 3d pixar style render, glossy, "
                            f"{LEON.format(mood=MOODS[mood])}", negative_prompt=AVOID, image=base,
                     strength=strength, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                     generator=torch.Generator("cpu").manual_seed(11)).images[0]
        name = f"toon_leon1_{mood}_{int(strength * 100)}"
        image.save(OUT / f"{name}_raw.png")
        cut_background(image).save(OUT / f"{name}.png")
        note(f"SAVED {name}.png ({time.time() - started:.0f} s)")
    # Шляпа двумя способами: а) отдельная плюшевая шляпа (перерисовка белого листа с силой 1 — то же, что с нуля);
    # б) Леон 1, дорисованный сразу в шляпе
    hat_only = ("isolated on plain white background, plush felt toy, black pirate tricorn hat, only the hat, empty hat, "
                "small embroidered skull emblem, gold trim, product photo, front view, centered")
    in_hat = ("isolated on plain white background, 3d pixar style render, glossy, "
              + LEON.format(mood="happy smile, sitting, wearing a soft plush black pirate tricorn hat on the head"))
    white = Image.new("RGB", (SIZE, SIZE), "white")
    for name, prompt, image0, strength, seed in [
        ("plush_hatonly_s9", hat_only, white, 1.0, 9), ("plush_hatonly_s19", hat_only, white, 1.0, 19),
        ("toon_leon1_inhat_55", in_hat, base, 0.55, 11), ("toon_leon1_inhat_70", in_hat, base, 0.7, 11),
    ]:
        started = time.time()
        image = edit(prompt=prompt, negative_prompt=", ".join([AVOID, AVOID_FOR["hat"]]) if "only" in prompt else AVOID,
                     image=image0, strength=strength, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                     generator=torch.Generator("cpu").manual_seed(seed)).images[0]
        image.save(OUT / f"{name}_raw.png")
        cut_background(image).save(OUT / f"{name}.png")
        note(f"SAVED {name}.png ({time.time() - started:.0f} s)")


# Третий заход: дорисовка по маске (inpaint) — меняется только лицо или макушка, остальной Леон 1 остаётся как был.
# Запуск: make_art.py r3. Разметка — в точках исходной картинки toon_leon1_raw.png (1024 × 1024).
FACE = (230, 320, 730, 690)            # глаза и рот
FACE_ARMS = (230, 320, 730, 900)       # лицо и лапки — чтобы от радости поднять лапки
HAT_SHRINK, HAT_AT = 0.78, (112, 224)  # для шляпы Леон уменьшается и опускается: над головой появляется место
HAT_ZONE = (170, 40, 700, 340)         # макушка на уменьшенной картинке


def mask(box, size=SIZE, blur=24):
    from PIL import ImageDraw
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse(box, fill=255)
    return m.filter(ImageFilter.GaussianBlur(blur))


def round3(note) -> None:
    from diffusers import StableDiffusionXLInpaintPipeline
    paint = StableDiffusionXLInpaintPipeline.from_pretrained(
        f"{MODELS}/sdxl-base", vae=AutoencoderKL.from_pretrained(f"{MODELS}/sdxl-vae-fp16-fix", torch_dtype=torch.float16),
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    paint.scheduler = DPMSolverMultistepScheduler.from_config(paint.scheduler.config, use_karras_sigmas=True)
    paint.enable_model_cpu_offload()
    note("INPAINT LOADED")
    base = Image.open(OUT / "toon_leon1_raw.png").convert("RGB")
    small = Image.new("RGB", (SIZE, SIZE), base.getpixel((8, 8)))
    small.paste(base.resize((int(SIZE * HAT_SHRINK),) * 2, Image.LANCZOS), HAT_AT)
    head = "isolated on plain white background, 3d pixar style render, glossy, cute baby green chameleon, "
    jobs = [
        ("happy_f", base, FACE, head + "overjoyed, laughing with wide open mouth, happy closed curved eyes", 0.95, 11),
        ("happy_f2", base, FACE, head + "overjoyed, laughing with wide open mouth, sparkling happy eyes", 0.95, 21),
        ("happy_fa", base, FACE_ARMS, head + "overjoyed, laughing with wide open mouth, both arms raised up high", 0.95, 11),
        ("sad_f", base, FACE, head + "sad and upset, teary eyes with a tear drop, frowning mouth, sad eyebrows", 0.95, 11),
        ("sad_f2", base, FACE, head + "very sad, crying, big teary eyes, pouting downturned mouth", 0.95, 21),
        ("hat_pirate", small, HAT_ZONE, head + "wearing a soft plush black felt pirate tricorn hat with a small "
                                              "embroidered skull, gold trim", 1.0, 11),
        ("hat_pirate2", small, HAT_ZONE, head + "wearing a soft plush black felt pirate tricorn hat with a small "
                                               "embroidered skull, gold trim", 1.0, 21),
        ("hat_crown", small, HAT_ZONE, head + "wearing a soft plush golden crown with felt jewels", 1.0, 11),
    ]
    for key, image0, box, prompt, strength, seed in jobs:
        started = time.time()
        image = paint(prompt=prompt, negative_prompt=AVOID, image=image0, mask_image=mask(box), strength=strength,
                      width=SIZE, height=SIZE, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                      generator=torch.Generator("cpu").manual_seed(seed)).images[0]
        name = f"toon_leon1_{key}"
        image.save(OUT / f"{name}_raw.png")
        cut_background(image).save(OUT / f"{name}.png")
        note(f"SAVED {name}.png ({time.time() - started:.0f} s)")


# Четвёртый заход: кандидаты в питомцы, все букашки, значки подарков — в выбранном стиле «3D-мультфильм».
# Запуск: make_art.py r4 [имя …]. Картинки — out/r4_<имя>.png.
TOON = "isolated on plain white background, 3d pixar style render, glossy, vibrant colors, "
CHIBI = "big round eyes, happy smile, sitting, full body, chibi proportions with big head, front view, centered"
BUG = "big friendly eyes, smiling, full body, centered, simple game icon"
GIFT = "single object, centered, game item icon"
R4 = [  # (имя, описание, зерно, чего избегать)
    ("turtle_a", f"cute baby turtle character, green skin, brown shell, {CHIBI}", 5, ""),
    ("turtle_b", f"cute baby turtle character, green skin, brown shell, {CHIBI}", 15, ""),
    ("hedge_b", f"cute baby hedgehog character, brown spikes, cream face, tiny black nose, {CHIBI}", 15, ""),
    ("parrot_a", f"cute baby parrot character, bright green feathers, yellow face, red crest, orange beak, {CHIBI}", 5, ""),
    ("parrot_b", f"cute baby parrot character, bright green feathers, yellow face, red crest, orange beak, {CHIBI}", 15, ""),
    ("axo_a", f"cute baby pink axolotl character, feathery pink gills, {CHIBI}", 5, "fish, shark"),
    ("axo_b", f"cute baby pink axolotl character, feathery pink gills, {CHIBI}", 15, "fish, shark"),
    # букашки, которые уже есть в игре
    ("ant", f"cute small black ant character, {BUG}", 3, ""),
    ("fly", f"cute small housefly character, red eyes, transparent wings, {BUG}", 3, "bee, stripes"),
    ("grub", f"cute small chubby white beetle grub larva, brown head, {BUG}", 3, ""),
    ("worm", f"cute small pink earthworm character, {BUG}", 3, "snake"),
    ("beetle", f"cute small shiny blue beetle character, {BUG}", 3, ""),
    ("ladybug", f"cute small red ladybug with black spots, {BUG}", 3, ""),
    ("cater", f"cute small green caterpillar character, {BUG}", 3, ""),
    ("centi", f"cute small orange centipede character with many tiny legs, {BUG}", 3, "snake"),
    ("hopper", f"cute small green grasshopper character, {BUG}", 3, ""),
    ("dragon", f"cute small blue dragonfly character, four transparent wings, {BUG}", 3, ""),
    ("fish", f"cute small orange fish character, {BUG}", 3, ""),
    ("butter", f"cute small butterfly character, pink wings with yellow dots, {BUG}", 3, ""),
    ("frog", f"cute small green frog character, {BUG}", 3, ""),
    # новые букашки
    ("bee", f"cute small honey bee character, yellow and black stripes, tiny wings, {BUG}", 3, "stinger"),
    ("bumble", f"cute fluffy round bumblebee character, {BUG}", 3, "stinger"),
    ("mosquito", f"cute small mosquito character, thin long legs, {BUG}", 3, "blood"),
    ("moth", f"cute small fluffy beige moth character, feathery antennae, {BUG}", 3, "butterfly colors"),
    ("spider", f"cute small brown spider character, eight legs, {BUG}", 3, "web, scary, hairy"),
    ("snail", f"cute small snail character, orange spiral shell, {BUG}", 3, ""),
    ("cricket", f"cute small brown cricket insect character, long antennae, {BUG}", 3, "grasshopper green"),
    ("stag", f"cute small stag beetle character, big brown antler jaws, {BUG}", 3, ""),
    ("louse", f"cute small grey woodlouse pill bug character, {BUG}", 3, ""),
    # переделка (28.10): муравей, жучок и жук-олень вышли красными, «в наушниках» и похожими друг на друга
    ("ant2a", f"cute small glossy black ant character, six thin legs, two antennae, {BUG}", 7, "headphones, ears, red, robot"),
    ("ant2b", f"cute small glossy black ant character, six thin legs, two antennae, {BUG}", 17, "headphones, ears, red, robot"),
    ("beetle2a", f"cute small shiny blue beetle, round shell with wing covers, six legs, {BUG}", 7, "headphones, ears, robot"),
    ("beetle2b", f"cute small shiny blue beetle, round shell with wing covers, six legs, {BUG}", 17, "headphones, ears, robot"),
    ("stag2a", f"cute small dark brown stag beetle, big curved antler-like jaws on its head, round shell, {BUG}", 7,
     "ant, headphones, ears"),
    ("stag2b", f"cute small dark brown stag beetle, big curved antler-like jaws on its head, round shell, {BUG}", 17,
     "ant, headphones, ears"),
    ("fly2a", f"cute small grey housefly character, big red eyes, two transparent wings, six thin legs, {BUG}", 7,
     "headphones, ears, robot, bee, stripes"),
    ("fly2b", f"cute small grey housefly character, big red eyes, two transparent wings, six thin legs, {BUG}", 17,
     "headphones, ears, robot, bee, stripes"),
    ("lady2a", f"cute small red ladybug beetle with black spots, round shell, two antennae, {BUG}", 7, "headphones, ears, robot"),
    ("lady2b", f"cute small red ladybug beetle with black spots, round shell, two antennae, {BUG}", 17, "headphones, ears, robot"),
    ("centi2a", f"cute small orange centipede, long segmented body with many tiny legs, two antennae, {BUG}", 7,
     "headphones, ears, ant, spider, robot"),
    ("centi2b", f"cute small orange centipede, long segmented body with many tiny legs, two antennae, {BUG}", 17,
     "headphones, ears, ant, spider, robot"),
    # «small … simple game icon» модель поняла как узор из многих букашек — просим одну
    *[(f"lady3{s}", "one single cute ladybug character, red shell with black spots, two antennae, big friendly eyes, "
       "smiling, full body, centered", s, "pattern, many, multiple, repeated, wallpaper, seamless, headphones")
      for s in (7, 17, 27)],
    *[(f"centi3{s}", "one single cute orange centipede character, long segmented body with many tiny legs, two antennae, "
       "big friendly eyes, smiling, full body, centered", s, "pattern, many, multiple, repeated, wallpaper, seamless, headphones")
      for s in (7, 17, 27)],
    # Леон боком (29.10): язык хамелеона стреляет вперёд с кончика морды
    *[(f"leon_side{s}", "cute baby chameleon character, bright green, big round eyes, curled tail, small crest on the "
       "head, happy smile, sitting, full body, chibi proportions with big head, side view profile facing right, centered",
       s, "front view") for s in (11, 21)],
    # рыбка под водой (29.10): обычная рыбка сбоку, мордой вправо — плавает в луже туда-сюда
    *[(f"fish_side{s}", "one single cute small orange goldfish, side view profile facing right, swimming, flowing tail "
       "fin, one big friendly eye, smiling, full body, centered", s, "front view, pattern, many, multiple, headphones")
      for s in (7, 17)],
    # зерно 7 дало узор из многих рыбок — просим одну, крупно
    *[(f"fish_gold{s}", "one single cute little orange goldfish character alone, side view profile, swimming, rounded "
       "body, flowing tail fin, big friendly eye, happy smile, full body, centered", s,
       "front view, pattern, many, multiple, repeated, wallpaper, school of fish, headphones") for s in (27, 37, 47)],
    ("fish_clown27", "one single cute small orange clownfish with white stripes, side view profile facing right, "
     "swimming, one big friendly eye, smiling, full body, centered", 27, "front view, pattern, many, multiple, headphones"),
    # подарки
    ("g_balloons", f"bunch of colorful helium balloons on strings, {GIFT}", 3, ""),
    ("g_chest", f"open wooden treasure chest overflowing with gold coins and gems, {GIFT}", 3, ""),
    ("g_rocket", f"festive firework rocket with colorful sparks, {GIFT}", 3, "weapon, missile"),
    ("g_cake", f"birthday cake with colorful candles and frosting, {GIFT}", 3, ""),
    ("g_bubbles", f"soap bubble wand with shiny rainbow bubbles, {GIFT}", 3, ""),
    ("g_rainbow", f"small rainbow arch with two fluffy clouds, {GIFT}", 3, ""),
    ("g_wand", f"magic wand with a golden star and sparkles, {GIFT}", 3, ""),
    ("g_cup", f"shiny golden trophy cup with a star, {GIFT}", 3, ""),
    ("g_kite", f"colorful diamond kite with a ribbon tail, {GIFT}", 3, ""),
    ("g_paint", f"paint bucket with a brush and rainbow paint splashes, {GIFT}", 3, ""),
]


def round4(pipe, note, only) -> None:
    jobs = [j for j in R4 if not only or j[0] in only]
    for n, (key, what, seed, avoid) in enumerate(jobs, start=1):
        started = time.time()
        image = pipe(prompt=TOON + what, negative_prompt=", ".join(filter(None, [AVOID, avoid])),
                     width=SIZE, height=SIZE, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                     generator=torch.Generator("cpu").manual_seed(seed)).images[0]
        image.save(OUT / f"r4_{key}_raw.png")
        cut_background(image).save(OUT / f"r4_{key}.png")
        note(f"SAVED {n}/{len(jobs)} r4_{key}.png ({time.time() - started:.0f} s)")


def fix(args, note) -> None:
    """Дорисовка одной области готовой картинки: make_art.py fix <исходник_raw.png> <имя> x0 y0 x1 y1 "описание" зерно…
    Область — эллипс в точках исходника; на каждое зерно — свой вариант out/<имя>_s<зерно>.png."""
    from diffusers import StableDiffusionXLInpaintPipeline
    src, name, *box = args[:6]
    prompt, seeds = args[6], [int(s) for s in args[7:]] or [11]
    paint = StableDiffusionXLInpaintPipeline.from_pretrained(
        f"{MODELS}/sdxl-base", vae=AutoencoderKL.from_pretrained(f"{MODELS}/sdxl-vae-fp16-fix", torch_dtype=torch.float16),
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    paint.scheduler = DPMSolverMultistepScheduler.from_config(paint.scheduler.config, use_karras_sigmas=True)
    paint.enable_model_cpu_offload()
    base = Image.open(OUT / src).convert("RGB")
    for seed in seeds:
        started = time.time()
        image = paint(prompt=TOON + prompt, negative_prompt=AVOID, image=base, mask_image=mask(tuple(map(int, box)), blur=10),
                      strength=0.95, width=SIZE, height=SIZE, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                      generator=torch.Generator("cpu").manual_seed(seed)).images[0]
        image.save(OUT / f"{name}_s{seed}_raw.png")
        cut_background(image).save(OUT / f"{name}_s{seed}.png")
        note(f"SAVED {name}_s{seed}.png ({time.time() - started:.0f} s)")


def fix2(args, note) -> None:
    """То же, что fix, но из эллипса области вырезан второй эллипс — его не трогаем (например, мордочку рядом с лапками):
    make_art.py fix2 <исходник_raw.png> <имя> x0 y0 x1 y1 вx0 вy0 вx1 вy1 "описание" зерно…"""
    from diffusers import StableDiffusionXLInpaintPipeline
    from PIL import ImageChops
    src, name, *box = args[:10]
    prompt, seeds = args[10], [int(s) for s in args[11:]] or [11]
    box = list(map(int, box))
    area = ImageChops.subtract(mask(tuple(box[:4]), blur=10), mask(tuple(box[4:]), blur=10))
    paint = StableDiffusionXLInpaintPipeline.from_pretrained(
        f"{MODELS}/sdxl-base", vae=AutoencoderKL.from_pretrained(f"{MODELS}/sdxl-vae-fp16-fix", torch_dtype=torch.float16),
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    paint.scheduler = DPMSolverMultistepScheduler.from_config(paint.scheduler.config, use_karras_sigmas=True)
    paint.enable_model_cpu_offload()
    base = Image.open(OUT / src).convert("RGB")
    for seed in seeds:
        started = time.time()
        image = paint(prompt=TOON + prompt, negative_prompt=AVOID, image=base, mask_image=area,
                      strength=0.95, width=SIZE, height=SIZE, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                      generator=torch.Generator("cpu").manual_seed(seed)).images[0]
        image.save(OUT / f"{name}_s{seed}_raw.png")
        cut_background(image).save(OUT / f"{name}_s{seed}.png")
        note(f"SAVED {name}_s{seed}.png ({time.time() - started:.0f} s)")


def recut() -> None:
    """Заново срезает фон у уже нарисованных картинок (…_raw.png), без видеокарты."""
    for raw in sorted(OUT.glob("*_raw.png")):
        cut_background(Image.open(raw)).save(OUT / raw.name.replace("_raw", ""))
        print("recut", raw.name, flush=True)


def main() -> None:
    if sys.argv[1:] == ["recut"]:
        return recut()
    style_filter = sys.argv[1] if len(sys.argv) > 1 else None
    subject_filter = set(sys.argv[2:])
    OUT.mkdir(parents=True, exist_ok=True)
    log = (OUT / "log.txt").open("a", encoding="utf-8")
    jobs = [(s, k) for s in STYLES if not style_filter or s == style_filter
            for k in SUBJECTS if not subject_filter or k in subject_filter]

    def note(text: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {text}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    note(f"START torch {torch.__version__}, card {torch.cuda.get_device_name(0)}, pictures: {len(jobs)}")
    if style_filter == "fix2":
        fix2(sys.argv[2:], note)
        note("DONE")
        return
    if style_filter == "fix":
        fix(sys.argv[2:], note)
        note("DONE")
        return
    if style_filter == "r3":
        round3(note)
        note("DONE")
        return
    if style_filter == "r2moods":       # только настроения Леона: обычный конвейер не нужен
        R2_NEW.clear()
        round2(None, note)
        note("DONE")
        return
    vae =AutoencoderKL.from_pretrained(f"{MODELS}/sdxl-vae-fp16-fix", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(
        f"{MODELS}/sdxl-base", vae=vae, torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)
    pipe.enable_model_cpu_offload()     # в видеопамяти (8 ГБ) держим только ту часть модели, что сейчас считает
    note("MODEL LOADED")
    if style_filter == "r4":
        round4(pipe, note, subject_filter)
    if style_filter == "r2":
        round2(pipe, note)
        jobs = []

    for n, (style, key) in enumerate(jobs, start=1):
        what, seed = SUBJECTS[key]
        started = time.time()
        image = pipe(
            prompt=f"{what}, {STYLES[style]}", negative_prompt=", ".join(filter(None, [AVOID, AVOID_FOR.get(key)])),
            width=SIZE, height=SIZE, num_inference_steps=STEPS, guidance_scale=GUIDANCE,
            generator=torch.Generator("cpu").manual_seed(seed),
        ).images[0]
        image.save(OUT / f"{style}_{key}_raw.png")
        cut_background(image).save(OUT / f"{style}_{key}.png")
        note(f"SAVED {n}/{len(jobs)} {style}_{key}.png (seed {seed}, {time.time() - started:.0f} s)")
    note("DONE")


if __name__ == "__main__":
    main()
