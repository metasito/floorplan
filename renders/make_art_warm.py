#!/usr/bin/env python3
"""Original prints and rug patterns for the warm scheme. Nothing copyrighted is used.

Usage: python make_art_warm.py <out_dir>   (needs Pillow and numpy)
"""
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

CREAM = (238, 229, 214)
SAND = (222, 201, 168)
CLAY = (196, 122, 86)
TERRA = (170, 88, 58)
OCHRE = (204, 151, 70)
SAGE = (150, 163, 135)
OLIVE = (104, 112, 78)
INK = (52, 48, 44)
SEA = (122, 156, 168)
SKY = (196, 210, 210)


def paper(im, amount=5, seed=3):
    """Fine paper grain and a slightly uneven wash, so prints don't look digital."""
    rng = np.random.default_rng(seed)
    a = np.asarray(im.convert("RGB")).astype(float)
    h, w, _ = a.shape
    grain = rng.normal(0, amount, (h, w, 1))
    yy, xx = np.mgrid[0:h, 0:w]
    wash = (np.sin(xx / w * 3.1 + 0.7) * np.cos(yy / h * 2.3) * 4)[..., None]
    return Image.fromarray(np.clip(a + grain + wash, 0, 255).astype("uint8"))


def soft_edges(im, r=1.2):
    return im.filter(ImageFilter.GaussianBlur(r))


def sun_arch():
    W, H = 1500, 2100
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    ax0, ax1, top, bot = 260, 1240, 420, 1800
    d.rectangle([ax0, top + (ax1 - ax0) // 2, ax1, bot], fill=CLAY)
    d.ellipse([ax0, top, ax1, top + (ax1 - ax0)], fill=CLAY)
    d.ellipse([560, 980, 940, 1360], fill=OCHRE)
    d.rectangle([ax0, 1500, ax1, bot], fill=TERRA)
    d.ellipse([ax0 - 120, 1440, ax1 + 120, 1640], fill=SAND)
    d.rectangle([0, 1540, W, H], fill=CREAM)
    return paper(soft_edges(im))


def horizon():
    W, H = 2400, 1600
    a = np.zeros((H, W, 3))
    for y in range(H):
        t = y / H
        if t < 0.56:
            c = np.array(SKY) * (1 - t / 0.56) + np.array((232, 214, 190)) * (t / 0.56)
        else:
            u = (t - 0.56) / 0.44
            c = np.array(SEA) * (1 - u) + np.array((88, 120, 132)) * u
        a[y] = c
    im = Image.fromarray(a.astype("uint8"))
    d = ImageDraw.Draw(im)
    d.ellipse([1500, 600, 1760, 860], fill=(236, 196, 150))
    im = im.filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(im)
    rng = random.Random(4)
    for _ in range(140):          # brush streaks on the water
        y = rng.uniform(0.6, 0.98) * H
        x = rng.uniform(0, W)
        ln = rng.uniform(80, 420)
        d.line([(x, y), (x + ln, y)], fill=(150, 180, 188), width=rng.choice((2, 3, 4)))
    return paper(im.filter(ImageFilter.GaussianBlur(1.6)), 4)


def olive_branch():
    W, H = 1500, 2100
    im = Image.new("RGB", (W, H), (241, 235, 224))
    d = ImageDraw.Draw(im)
    rng = random.Random(11)
    pts = [(420 + 40 * math.sin(i / 9), 1850 - i * 26) for i in range(58)]
    d.line(pts, fill=OLIVE, width=9, joint="curve")
    for i in range(6, 56, 3):
        x, y = pts[i]
        for side in (-1, 1):
            ang = math.radians(rng.uniform(25, 55)) * side
            L = rng.uniform(150, 230)
            ex, ey = x + math.sin(ang) * L + side * 30, y - math.cos(ang) * L * 0.6
            mx, my = (x + ex) / 2, (y + ey) / 2
            nx, ny = -(ey - y), (ex - x)
            n = math.hypot(nx, ny)
            w = 30
            poly = [(x, y), (mx + nx / n * w, my + ny / n * w), (ex, ey), (mx - nx / n * w, my - ny / n * w)]
            d.polygon(poly, fill=SAGE if rng.random() < 0.6 else OLIVE)
    for i in (20, 33, 47):
        x, y = pts[i]
        d.ellipse([x + 30, y - 10, x + 78, y + 50], fill=INK)
    return paper(soft_edges(im, 1.5))


def shapes():
    W, H = 1500, 2100
    im = Image.new("RGB", (W, H), SAND)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1250, W, H], fill=CREAM)
    d.pieslice([200, 500, 1000, 1300], 180, 360, fill=SAGE)
    d.ellipse([820, 380, 1240, 800], fill=TERRA)
    d.rectangle([520, 1250, 1300, 1700], fill=CLAY)
    d.pieslice([520, 1460, 1300, 1940], 0, 180, fill=OCHRE)
    d.rectangle([200, 1250, 330, 1880], fill=INK)
    return paper(soft_edges(im))


def lines():
    W, H = 1500, 2100
    im = Image.new("RGB", (W, H), (243, 238, 229))
    d = ImageDraw.Draw(im)
    cx, cy = 750, 1050
    for r in range(80, 700, 46):
        d.arc([cx - r, cy - r, cx + r, cy + r], 200, 340, fill=TERRA if r % 92 else INK, width=6)
    d.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=OCHRE)
    return paper(soft_edges(im, 1.0))


def berber():
    """Cream wool rug with a charcoal diamond lattice, at 200 x 300."""
    W, H = 2000, 3000
    im = Image.new("RGB", (W, H), (232, 224, 210))
    d = ImageDraw.Draw(im)
    step = 260
    for k in range(-14, 26):
        x = k * step
        d.line([(x, 0), (x + H * 0.6, H)], fill=(70, 64, 58), width=10)
        d.line([(x + H * 0.6, 0), (x, H)], fill=(70, 64, 58), width=10)
    d.rectangle([0, 0, W - 1, H - 1], outline=(232, 224, 210), width=90)
    rng = np.random.default_rng(5)
    a = np.asarray(im).astype(float)
    a += rng.normal(0, 9, a.shape[:2] + (1,))
    a += (np.sin(np.arange(H) * 1.9)[:, None, None] * 5)
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(1.4))


def stripes():
    """Flat-woven outdoor rug: ecru with terracotta and indigo stripes, at 120 x 180."""
    W, H = 1200, 1800
    im = Image.new("RGB", (W, H), (230, 220, 200))
    d = ImageDraw.Draw(im)
    y = 60
    pattern = [(TERRA, 34), ((230, 220, 200), 40), ((60, 72, 98), 16), ((230, 220, 200), 40), (TERRA, 34),
               ((230, 220, 200), 160)]
    while y < H:
        for c, h in pattern:
            d.rectangle([0, y, W, y + h], fill=c)
            y += h
    rng = np.random.default_rng(7)
    a = np.asarray(im).astype(float)
    a += rng.normal(0, 10, a.shape[:2] + (1,))
    a += (np.sin(np.arange(W) * 2.3)[None, :, None] * 6)
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


for name, fn in (("print_arch", sun_arch), ("print_horizon", horizon), ("print_olive", olive_branch),
                 ("print_shapes", shapes), ("print_lines", lines), ("rug_berber", berber), ("rug_stripes", stripes)):
    fn().save(OUT / f"{name}.png", optimize=True)
    print("made", name)
