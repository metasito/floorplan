#!/usr/bin/env python3
"""Generate the rugs and wall art used in the renders, so no copyrighted artwork is involved.

Usage: python make_art.py <out_dir>   (needs Pillow and numpy)
"""
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def weave(im, amount=14, seed=1):
    """Add woven texture, so the pattern reads as textile rather than print."""
    rng = np.random.default_rng(seed)
    a = np.asarray(im.convert("RGB")).astype(float)
    h, w, _ = a.shape
    rows = np.sin(np.arange(h) * 1.7)[:, None, None] * amount * 0.5
    grain = rng.normal(0, amount * 0.55, (h, w, 1))
    return Image.fromarray(np.clip(a + rows + grain, 0, 255).astype("uint8"))


def canvas(im, amount=6, seed=2):
    rng = np.random.default_rng(seed)
    a = np.asarray(im.convert("RGB")).astype(float)
    return Image.fromarray(np.clip(a + rng.normal(0, amount, a.shape[:2] + (1,)), 0, 255).astype("uint8"))


def kilim():
    W, H = 2480, 1740
    colours = dict(ground=(176, 74, 44), ink=(42, 52, 84), cream=(232, 214, 180), sun=(214, 152, 62), rose=(150, 50, 44))
    im = Image.new("RGB", (W, H), colours["ground"])
    d = ImageDraw.Draw(im)
    b = 90
    d.rectangle([0, 0, W, H], outline=colours["ink"], width=b)
    d.rectangle([b, b, W - b, H - b], outline=colours["cream"], width=26)
    d.rectangle([b + 26, b + 26, W - b - 26, H - b - 26], outline=colours["sun"], width=30)
    for x in range(b, W - b, 86):               # stepped border
        d.polygon([(x, b + 56), (x + 43, b + 110), (x + 86, b + 56)], fill=colours["ink"])
        d.polygon([(x, H - b - 56), (x + 43, H - b - 110), (x + 86, H - b - 56)], fill=colours["ink"])
    cy = H / 2
    for i, cx in enumerate((W * 0.2, W * 0.5, W * 0.8)):
        for r, c in ((540, colours["ink"]), (450, colours["cream"]), (360, colours["rose"]), (250, colours["sun"]), (140, colours["ink"]), (60, colours["cream"])):
            rx = r * 0.8
            ry = min(r, cy - 215) * (r / 540 + 0.0 if r < 540 else 1)
            d.polygon([(cx - rx, cy), (cx, cy - ry), (cx + rx, cy), (cx, cy + ry)], fill=c)
    im.save(OUT / "kilim_flat.png")
    weave(im.filter(ImageFilter.GaussianBlur(1.2)), 16).save(OUT / "kilim.png")


def persian():
    W, H = 2460, 1720
    ground, ink, cream, gold, blue = (92, 26, 30), (24, 26, 48), (214, 190, 150), (176, 132, 70), (40, 56, 86)
    im = Image.new("RGB", (W, H), ink)
    d = ImageDraw.Draw(im)
    d.rectangle([60, 60, W - 60, H - 60], fill=cream)
    d.rectangle([84, 84, W - 84, H - 84], fill=ink)
    d.rectangle([190, 190, W - 190, H - 190], fill=cream)
    d.rectangle([212, 212, W - 212, H - 212], fill=ground)
    rng = random.Random(4)
    for x in range(110, W - 100, 62):            # border rosettes
        for y in (136, H - 136):
            d.ellipse([x - 22, y - 22, x + 22, y + 22], fill=gold)
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=ground)
    for y in range(110, H - 100, 62):
        for x in (136, W - 136):
            d.ellipse([x - 22, y - 22, x + 22, y + 22], fill=gold)
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=ground)
    for _ in range(420):                         # field of small flowers
        x, y = rng.randrange(240, W - 240), rng.randrange(240, H - 240)
        c = rng.choice((gold, blue, cream))
        s = rng.randrange(8, 20)
        for a in range(0, 360, 60):
            px, py = x + s * math.cos(math.radians(a)), y + s * math.sin(math.radians(a))
            d.ellipse([px - s * 0.55, py - s * 0.55, px + s * 0.55, py + s * 0.55], fill=c)
    cx, cy = W / 2, H / 2                        # central medallion
    for r, c in ((560, ink), (505, gold), (450, blue), (320, cream), (250, ground), (120, gold), (60, ink)):
        d.polygon([(cx - r * 1.15, cy), (cx - r * 0.5, cy - r * 0.8), (cx + r * 0.5, cy - r * 0.8), (cx + r * 1.15, cy),
                   (cx + r * 0.5, cy + r * 0.8), (cx - r * 0.5, cy + r * 0.8)], fill=c)
    weave(im.filter(ImageFilter.GaussianBlur(1.6)), 14, 3).save(OUT / "persian.png")


def art_modern():
    W, H = 1200, 1600
    a = np.zeros((H, W, 3), float)
    a[:] = (222, 219, 212)
    im = Image.fromarray(a.astype("uint8"))
    d = ImageDraw.Draw(im)
    d.polygon([(0, 1600), (0, 880), (1200, 520), (1200, 1600)], fill=(36, 37, 40))
    d.polygon([(0, 1600), (0, 1240), (1200, 1000), (1200, 1600)], fill=(112, 112, 112))
    d.ellipse([740, 160, 1040, 460], fill=(176, 138, 86))
    canvas(im.filter(ImageFilter.GaussianBlur(1.5)), 7).save(OUT / "art_modern.png")


def art_scandi():
    W, H = 1050, 1500
    im = Image.new("RGB", (W, H), (232, 226, 212))
    d = ImageDraw.Draw(im)
    for i, c in enumerate(((139, 158, 134), (196, 164, 112), (62, 74, 82))):
        y = 420 + i * 300
        d.ellipse([140 + i * 70, y, 900 - i * 40, y + 420], fill=c)
    canvas(im.filter(ImageFilter.GaussianBlur(2)), 5).save(OUT / "art_scandi.png")


def art_mid():
    W, H = 1200, 1500
    im = Image.new("RGB", (W, H), (236, 226, 202))
    d = ImageDraw.Draw(im)
    pal = [(206, 136, 38), (40, 92, 94), (176, 66, 36), (32, 36, 38)]
    rng = random.Random(9)
    for i in range(9):
        cx, cy, r = rng.randrange(150, 1050), rng.randrange(180, 1320), rng.randrange(120, 290)
        pts = [(cx + r * (0.7 + 0.45 * math.sin(3 * t + i)) * math.cos(t), cy + r * (0.7 + 0.45 * math.sin(3 * t + i)) * math.sin(t))
               for t in np.linspace(0, 2 * math.pi, 90)]
        d.polygon(pts, fill=pal[i % 4])
    canvas(im, 6).save(OUT / "art_mid.png")


def art_boho():
    W, H = 1400, 1400
    im = Image.new("RGB", (W, H), (231, 207, 170))
    d = ImageDraw.Draw(im)
    for r, c in ((640, (196, 104, 62)), (520, (231, 207, 170)), (420, (150, 66, 40)), (300, (222, 168, 84)), (180, (92, 110, 90))):
        d.pieslice([W / 2 - r, H - 120 - r, W / 2 + r, H - 120 + r], 180, 360, fill=c)
    d.rectangle([0, H - 120, W, H], fill=(92, 110, 90))
    d.ellipse([W / 2 - 110, 90, W / 2 + 110, 310], fill=(150, 66, 40))
    canvas(im.filter(ImageFilter.GaussianBlur(1.2)), 7).save(OUT / "art_boho.png")


for fn in (kilim, persian, art_modern, art_scandi, art_mid, art_boho):
    fn()
print(sorted(p.name for p in OUT.glob("*.png")))
