"""Music of the cartoon, drawn from nothing: a bright major tune for ukulele, marimba, glockenspiel, tuba and hand claps.
Two boring bars with a clock at the start, then the band comes in when Leon eats the fly. Original tune, no samples.
Also the comedy noises (fx:) of the cartoon.
"""
import numpy as np

RATE = 44100
BPM, BEAT = 120, .5
SWING = .08                                           # the off-beat comes this much of a beat late


def mhz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def pluck(freq, dur=1.0, bright=.5, seed=0):
    """Karplus-Strong string, a period at a time."""
    n, p = int(dur * RATE), max(2, int(RATE / freq))
    rng = np.random.default_rng(seed + int(freq))
    buf = rng.uniform(-1, 1, p).astype(np.float32)
    buf = buf * bright + np.roll(buf, 1) * (1 - bright)
    out = np.zeros(n + p, np.float32)
    for i in range(0, n, p):
        out[i:i + p] = buf
        buf = .5 * (buf + np.roll(buf, 1)) * .994
    return out[:n] * np.minimum(1, (n - np.arange(n)) / 800)


def marimba(freq, dur=.55):
    t = np.arange(int(dur * RATE)) / RATE
    w = np.sin(6.2832 * freq * t) * np.exp(-t / .2) + .35 * np.sin(6.2832 * freq * 4 * t) * np.exp(-t / .035) + .12 * np.sin(6.2832 * freq * 10 * t) * np.exp(-t / .012)
    return (w * np.minimum(1, t / .002)).astype(np.float32)


def glock(freq, dur=1.1):
    t = np.arange(int(dur * RATE)) / RATE
    w = np.sin(6.2832 * freq * t) * np.exp(-t / .45) + .3 * np.sin(6.2832 * freq * 2.76 * t) * np.exp(-t / .12)
    return (w * np.minimum(1, t / .001)).astype(np.float32)


def tuba(freq, dur=.42):
    t = np.arange(int(dur * RATE)) / RATE
    w = sum(np.sin(6.2832 * freq * h * t + h) / h ** 1.6 for h in range(1, 6))
    return (w * np.minimum(1, t / .02) * np.minimum(1, (dur - t) / .08)).astype(np.float32)


def clap(rng):
    n = int(.11 * RATE)
    t = np.arange(n) / RATE
    x = rng.standard_normal(n).astype(np.float32)
    x = np.diff(x, prepend=0)
    env = np.exp(-t / .03) + .6 * np.exp(-np.maximum(0, t - .012) / .012) * (t > .012) + .5 * np.exp(-np.maximum(0, t - .024) / .012) * (t > .024)
    return x * env.astype(np.float32)


def shake(rng):
    n = int(.05 * RATE)
    x = np.diff(rng.standard_normal(n).astype(np.float32), prepend=0)
    return x * np.exp(-np.arange(n) / RATE / .012).astype(np.float32)


def woodblock(freq):
    t = np.arange(int(.09 * RATE)) / RATE
    return (np.sin(6.2832 * freq * t) * np.exp(-t / .018)).astype(np.float32)


def bassoon(freq, dur):
    t = np.arange(int(dur * RATE)) / RATE
    w = sum(np.sin(6.2832 * freq * h * t + h * .7) / h for h in (1, 2, 3, 4, 5, 6))
    vib = 1 + .08 * np.sin(6.2832 * 4.5 * t)
    return (w * vib * np.minimum(1, t / .05) * np.minimum(1, (dur - t) / .1)).astype(np.float32)


UKE = {  # the four strings of a ukulele, high G tuning
    'C': (67, 60, 64, 72), 'Am': (69, 60, 64, 69), 'F': (69, 60, 65, 69), 'G': (67, 62, 67, 71),
    'Dm': (69, 62, 65, 69), 'Em': (67, 64, 67, 71), 'G7': (67, 62, 65, 71),
}
ROOT = {'C': (36, 43), 'Am': (33, 40), 'F': (29, 36), 'G': (31, 38), 'Dm': (38, 33), 'Em': (40, 35), 'G7': (31, 38)}

# bar: chord(s) and the melody (beat, midi note)
A = [
    ('C', [(0, 67), (1, 64), (1.5, 67), (2, 72), (3, 67)]),
    ('Am', [(0, 69), (1, 64), (1.5, 69), (2, 72), (3, 69)]),
    ('F', [(0, 65), (.5, 69), (1, 72), (2, 77), (3, 76), (3.5, 74)]),
    ('G', [(0, 74), (1, 71), (2, 67), (3.5, 67)]),
    ('C', [(0, 72), (1, 76), (1.5, 72), (2, 79), (3, 76)]),
    ('Am', [(0, 76), (1, 72), (1.5, 76), (2, 81), (3, 79)]),
    ('Dm', [(0, 77), (1, 74), (2, 79), (2.5, 77), (3, 74), (3.5, 71)]),
    ('C', [(0, 72), (1, 79), (2, 84)]),
]
B = [
    ('F', [(0, 81), (.5, 79), (1, 77), (2, 72), (3, 77)]),
    ('G', [(0, 79), (.5, 77), (1, 74), (2, 71), (3, 74)]),
    ('Em', [(0, 76), (.5, 79), (1, 83), (2, 79), (3, 76)]),
    ('Am', [(0, 81), (1, 76), (2, 72), (3, 69)]),
    ('F', [(0, 77), (1, 81), (1.5, 84), (2, 81), (3, 77)]),
    ('G', [(0, 79), (1, 83), (1.5, 86), (2, 83), (3, 79)]),
    ('C', [(0, 84), (1, 79), (2, 76), (3, 72)]),
    ('G7', [(0, 74), (.5, 74), (1, 74), (2, 79)]),
]


def music(total):
    n = int((total + 1) * RATE)
    left, right = np.zeros(n, np.float32), np.zeros(n, np.float32)
    rng = np.random.default_rng(5)

    def put(sound, at, gain, pan=0.0):
        i = int(at * RATE)
        if i >= n or i < 0:
            return
        s = sound[:n - i] * gain
        left[i:i + len(s)] += s * (1 - max(0.0, pan))
        right[i:i + len(s)] += s * (1 + min(0.0, pan))

    def when(bar_start, beat):                         # off-beats are swung
        whole = np.floor(beat)
        return bar_start + (beat + (SWING if abs(beat - whole - .5) < .01 else 0)) * BEAT

    # the two boring bars: a clock and a sleepy bassoon
    for b in range(8):
        put(woodblock(1400 if b % 2 else 1050), b * BEAT, .35)
    put(bassoon(mhz(40), .9), 0, .13)
    put(bassoon(mhz(39), .9), 1.0, .13)
    put(bassoon(mhz(38), 1.4), 2.0, .12)

    # the band: 30 bars from second 4, A A B A; the first 8 bars lighter, the last ones with bells
    form = (A + B + A + B)[:30]
    n_uke = 0
    for b, (ch, tune) in enumerate(form):
        t0 = 4 + b * 2.0
        last = b == len(form) - 1
        # ukulele strum: down, down-up, up-down-up
        for beat, up, g in ((0, 0, 1), (1, 0, .9), (1.5, 1, .6), (2.5, 1, .7), (3, 0, .9), (3.5, 1, .6)):
            if last and beat > 0:
                continue
            strings = UKE[ch][::-1] if up else UKE[ch]
            for i, m in enumerate(strings):
                n_uke += 1
                put(pluck(mhz(m), .7, .55, seed=n_uke % 7), when(t0, beat) + i * .009, .085 * g, pan=-.25)
        # tuba: root and fifth
        r1, r2 = ROOT[ch]
        put(tuba(mhz(r1 + 12)), t0, .17)
        if not last:
            put(tuba(mhz(r2 + 12)), t0 + 2 * BEAT, .15)
        # the tune
        for beat, m in tune:
            at = when(t0, beat)
            put(marimba(mhz(m)), at, .25, pan=.2)
            if b >= 8:                                 # bells join later
                put(glock(mhz(m + 12)), at, .055, pan=.35)
        # claps on 2 and 4, a shaker on the eighths
        if b >= 2 and not last:
            for beat in (1, 3):
                put(clap(rng), t0 + beat * BEAT, .22, pan=.1)
            for k in range(8):
                put(shake(rng), when(t0, k / 2), .07 if k % 2 else .04, pan=-.3)
    # the last chord, held with bells
    t0 = 4 + (len(form) - 1) * 2.0
    for k, m in enumerate((72, 76, 79, 84, 88)):
        put(glock(mhz(m), 1.8), t0 + .5 + k * .07, .1)
    mix = np.stack([left, right])[:, :int(total * RATE)]
    return (mix / np.max(np.abs(mix))).astype(np.float32)


# ---------------------------------------------------------------- comedy noises
def glide(f0, f1, dur, shape=2.0, wave='sine', decay=None):
    t = np.arange(int(dur * RATE)) / RATE
    f = f0 + (f1 - f0) * (t / dur) ** shape
    ph = 6.2832 * np.cumsum(f) / RATE
    w = np.sin(ph) if wave == 'sine' else np.sign(np.sin(ph)) * .4 + np.sin(ph) * .6
    env = np.minimum(1, t / .004) * np.minimum(1, (dur - t) / .02)
    if decay:
        env = env * np.exp(-t / decay)
    return (w * env).astype(np.float32)


def noise_band(dur, f0, f1, seed=1, env_pow=1.0):
    rng = np.random.default_rng(seed)
    n = int(dur * RATE)
    x = rng.standard_normal(n)
    out = np.zeros(n)
    t = np.arange(n) / RATE
    y1 = y2 = 0.0
    for i in range(n):                                 # a simple resonant filter that slides from f0 to f1
        w = 2 * np.sin(np.pi * (f0 + (f1 - f0) * t[i] / dur) / RATE)
        y1 += w * (x[i] - y2 - .9 * y1)
        y2 += w * y1
        out[i] = y1
    env = np.sin(np.pi * t / dur) ** env_pow
    return (out * env / np.max(np.abs(out) + 1e-6)).astype(np.float32)


def make_fx():
    fx = {}
    fx['whip'] = glide(500, 2600, .16, 1.5) * .8                        # the tongue goes out
    fx['boing'] = np.concatenate([glide(180, 620, .09), glide(620, 300, .17, 1, decay=.09)]) * .7     # a jump
    fx['whoosh'] = noise_band(.45, 500, 2600, 3) * .8
    fx['burst'] = noise_band(.5, 3400, 500, 4, .5) * .9
    fx['slideup'] = glide(380, 1500, .55, 1.3, 'square') * .3            # a slide whistle
    fx['slidedown'] = glide(1500, 300, .5, .8, 'square') * .3
    fx['bubbleup'] = np.concatenate([glide(300 + 170 * i, 700 + 170 * i, .06) * .7 for i in range(5)])
    fx['roll'] = np.concatenate([noise_band(.07, 900, 1500, 10 + i, .7) * .9 for i in range(8)])
    fx['plod'] = np.concatenate([glide(150, 95, .16, 1, decay=.12), np.zeros(int(.2 * RATE), np.float32), glide(130, 85, .16, 1, decay=.12)]) * .9
    fx['patter'] = np.concatenate([np.concatenate([glide(900 + (i % 3) * 180, 640, .035), np.zeros(int(.075 * RATE), np.float32)]) for i in range(26)]) * .5
    fx['rattle'] = np.concatenate([np.concatenate([noise_band(.03, 2600, 2000, 20 + i, .5), np.zeros(int(.025 * RATE), np.float32)]) for i in range(9)]) * .7
    fx['pop_lid'] = np.concatenate([glide(260, 1400, .05), noise_band(.09, 3000, 900, 6, .6) * .7])
    fx['splash'] = noise_band(.36, 2600, 500, 7, .6) * .85
    fx['zoom'] = glide(300, 1000, .7, .8, 'square') * .22
    fx['rocket'] = noise_band(.8, 700, 3400, 8, .8) * .55
    return fx
