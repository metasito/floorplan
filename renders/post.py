#!/usr/bin/env python3
"""Photographic finishing for the Cycles renders: the light touch a photographer gives a raw file.

Usage: python post.py <raw_dir> <out_dir>      (needs numpy and opencv-python-headless)

For each 16-bit PNG: a soft highlight bloom, a gentle vignette (stills only, so panorama
seams stay invisible), a fine unsharp mask and a whisper of grain. Writes a full-size JPEG
and a web copy (1600 px stills, 4096 px panoramas).
"""
import sys
from pathlib import Path

import cv2
import numpy as np

raw, out = Path(sys.argv[1]), Path(sys.argv[2])
(out / "web").mkdir(parents=True, exist_ok=True)


def to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def finish(path):
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return
    pano = path.stem.startswith("pano_")
    a = img[..., :3][..., ::-1].astype(np.float32) / (65535.0 if img.dtype == np.uint16 else 255.0)
    h, w, _ = a.shape
    lin = to_lin(a)
    # bloom: only what is close to white, spread wide and added back faintly
    lum = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    hi = np.clip((lum - 0.72) / 0.28, 0, 1)[..., None] * lin
    k = max(3, int(w * (0.006 if pano else 0.012)) | 1)
    bloom = cv2.GaussianBlur(hi, (0, 0), k) * 0.6 + cv2.GaussianBlur(hi, (0, 0), k * 4) * 0.4
    lin = lin + bloom * (0.05 if pano else 0.08)
    if not pano:              # vignette in linear light, about a sixth of a stop at the corners
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
        lin = lin * (1 - 0.13 * r ** 2.2)[..., None]
    s = to_srgb(lin)
    blur = cv2.GaussianBlur(s, (0, 0), 1.1 if not pano else 0.9)
    s = np.clip(s + (s - blur) * 0.45, 0, 1)
    rng = np.random.default_rng(7)
    s = np.clip(s + rng.normal(0, 0.004, (h, w, 1)).astype(np.float32), 0, 1)
    out8 = (s * 255 + 0.5).astype(np.uint8)[..., ::-1]
    cv2.imwrite(str(out / f"{path.stem}.jpg"), out8, [cv2.IMWRITE_JPEG_QUALITY, 94])
    scale = 1600 / max(h, w) if not pano else 4096 / w
    small = cv2.resize(out8, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out / "web" / f"{path.stem}.jpg"), small, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("finished", path.stem, w, "x", h)


for p in sorted(raw.glob("*.png")):
    finish(p)
