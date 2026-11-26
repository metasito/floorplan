#!/usr/bin/env python3
"""Lay out the warm-scheme catalogue as an A3 landscape PDF from the finished renders.

Usage: python make_catalogue.py <finished_dir>      (needs reportlab and Pillow)
Writes <finished_dir>/Unit13_warm_catalogue.pdf.
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogue_data as D  # noqa: E402

SRC = Path(sys.argv[1])
OUT = SRC / "Unit13_warm_catalogue.pdf"
W, H = landscape(A3)
M = 16 * mm
TMP = Path(tempfile.mkdtemp())

INK = HexColor("#2b2824")
MUTED = HexColor("#7a7168")
PAPER = HexColor("#f6f2ec")
RULE = HexColor("#d9d0c4")
ACCENT = HexColor("#a85f3d")


def font(name, path, idx=None):
    try:
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx) if idx is not None else TTFont(name, path))
        return name
    except Exception:
        return None


WIN = "C:/Windows/Fonts/"   # Mac fonts first, then the Windows equivalents, then PDF built-ins
SERIF = (font("Georgia", "/System/Library/Fonts/Supplemental/Georgia.ttf")
         or font("Georgia", WIN + "georgia.ttf") or "Times-Roman")
SERIF_I = (font("Georgia-Italic", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf")
           or font("Georgia-Italic", WIN + "georgiai.ttf") or "Times-Italic")
SANS = (font("AvenirNext", "/System/Library/Fonts/Avenir Next.ttc", 7)
        or font("SegoeUI", WIN + "segoeui.ttf") or "Helvetica")
SANS_D = (font("AvenirNext-Demi", "/System/Library/Fonts/Avenir Next.ttc", 2)
          or font("SegoeUI-Semibold", WIN + "seguisb.ttf") or "Helvetica-Bold")


def img(name, max_px=2600):
    p = SRC / f"{name}.jpg"
    if not p.exists():
        return None
    q = TMP / f"{name}.jpg"
    if not q.exists():
        im = Image.open(p)
        im.thumbnail((max_px, max_px))
        im.save(q, quality=90)
    return q


def cover_image(c, name, x, y, w, h):
    """Draw an image cropped to fill the box."""
    p = img(name)
    if p is None:
        c.setFillColor(RULE)
        c.rect(x, y, w, h, stroke=0, fill=1)
        return
    iw, ih = Image.open(p).size
    s = max(w / iw, h / ih)
    dw, dh = iw * s, ih * s
    c.saveState()
    path = c.beginPath()
    path.rect(x, y, w, h)
    c.clipPath(path, stroke=0, fill=0)
    c.drawImage(str(p), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh)
    c.restoreState()


def wrap(text, fnt, size, width):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if pdfmetrics.stringWidth(t, fnt, size) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def para(c, text, x, y, width, fnt=None, size=10.5, lead=15.5, color=INK):
    c.setFillColor(color)
    c.setFont(fnt or SANS, size)
    for line in wrap(text, fnt or SANS, size, width):
        c.drawString(x, y, line)
        y -= lead
    return y


def page(c, number=None, label=""):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    if number:
        c.setFillColor(MUTED)
        c.setFont(SANS, 8.5)
        c.drawString(M, 9 * mm, f"{D.TITLE.upper()}  ·  {label.upper()}")
        c.drawRightString(W - M, 9 * mm, str(number))


def eur(v):
    return f"€{v:,.0f}".replace(",", " ")


def cover(c):
    cover_image(c, "living_dusk", 0, 0, W, H)
    c.setFillColor(HexColor("#2b2824"))
    c.setFillAlpha(0.58)
    c.rect(0, 0, W * 0.46, 92 * mm, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColor(HexColor("#f6f2ec"))
    c.setFont(SERIF, 44)
    c.drawString(M + 4 * mm, 60 * mm, D.TITLE)
    c.setFont(SERIF_I, 19)
    c.drawString(M + 4 * mm, 47 * mm, D.SUBTITLE)
    c.setFont(SANS, 10.5)
    c.drawString(M + 4 * mm, 34 * mm, D.AREA)
    c.drawString(M + 4 * mm, 27 * mm, "Interior scheme and visualisation · revised plan (rev D)")
    c.showPage()


def concept(c, n):
    page(c, n, "Concept")
    c.setFillColor(INK)
    c.setFont(SERIF, 30)
    c.drawString(M, H - M - 14 * mm, "The idea")
    y = H - M - 30 * mm
    for p in D.CONCEPT:
        y = para(c, p, M, y, 150 * mm, size=11.5, lead=17.5) - 7
    y -= 8
    c.setFont(SERIF, 18)
    c.setFillColor(INK)
    c.drawString(M, y, "Materials")
    y -= 11 * mm
    for k, v in D.MATERIALS:
        c.setFont(SANS_D, 10)
        c.setFillColor(ACCENT)
        c.drawString(M, y, k.upper())
        y = para(c, v, M + 28 * mm, y, 122 * mm, size=10, lead=14.5) - 6
    x0, y0 = M + 175 * mm, H - M - 30 * mm
    c.setFillColor(INK)
    c.setFont(SERIF, 18)
    c.drawString(x0, H - M - 14 * mm, "Palette")
    gap = 5 * mm
    sw, sh = (W - x0 - M - 4 * gap) / 5, 32 * mm
    for i, (name, hexc, use) in enumerate(D.PALETTE):
        col, row = i % 5, i // 5
        x = x0 + col * (sw + gap)
        y = y0 - row * (sh + 26 * mm) - sh
        c.setFillColor(HexColor(hexc))
        c.roundRect(x, y, sw, sh, 2.5 * mm, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont(SANS_D, 9.5)
        c.drawString(x, y - 6 * mm, name)
        c.setFillColor(MUTED)
        c.setFont(SANS, 8.5)
        c.drawString(x, y - 10.5 * mm, hexc.upper())
        for j, line in enumerate(wrap(use, SANS, 8.5, sw)):
            c.drawString(x, y - (15 + 4.2 * j) * mm, line)
    strip_y, strip_h = M + 6 * mm, 62 * mm
    names = ["kitchen_day", "bedroom1", "bath2", "balcony_a"]
    sw2 = (W - x0 - M - 3 * 4 * mm) / 4
    for i, nm in enumerate(names):
        cover_image(c, nm, x0 + i * (sw2 + 4 * mm), strip_y, sw2, strip_h)
    c.showPage()


def plans(c, n):
    page(c, n, "The whole apartment")
    c.setFillColor(INK)
    c.setFont(SERIF, 30)
    c.drawString(M, H - M - 14 * mm, "The whole apartment")
    para(c, "Cut at 1.5 m and seen from above: every room furnished as the plan. One oak floor ties "
            "the dry rooms together; bathrooms and balconies take their own tiles.", M, H - M - 25 * mm,
         170 * mm, size=11)
    side = H - 2 * M - 42 * mm
    cover_image(c, "topplan", M, M + 8 * mm, side, side)
    cw = W - 2 * M - side - 8 * mm
    ch = cw * 2 / 3
    cy = M + 8 * mm + (side - ch)
    cover_image(c, "cutaway", M + side + 8 * mm, cy, cw, ch)
    c.setFillColor(MUTED)
    c.setFont(SANS, 9)
    c.drawString(M, M + 2 * mm, D.CAPTIONS["topplan"])
    c.drawString(M + side + 8 * mm, cy - 6 * mm, D.CAPTIONS["cutaway"])
    y = cy - 20 * mm
    for k, v in (("Interior", "87.32 m²"), ("Balconies", "17.95 m²"),
                 ("Rooms", "living + kitchen, 2 bedrooms, 2 bathrooms, storage, hall")):
        c.setFont(SANS_D, 10)
        c.setFillColor(ACCENT)
        c.drawString(M + side + 8 * mm, y, k.upper())
        c.setFont(SANS, 10.5)
        c.setFillColor(INK)
        c.drawString(M + side + 36 * mm, y, v)
        y -= 7 * mm
    c.showPage()


def room(c, n, r):
    page(c, n, r["title"])
    panel = 118 * mm
    iw = W - 2 * M - panel - 10 * mm
    imgs = r["images"]
    top = H - M - 4 * mm
    if len(imgs) == 1:
        ih = iw * 2 / 3
        cover_image(c, imgs[0], M, top - ih, iw, ih)
        c.setFillColor(MUTED)
        c.setFont(SANS, 9)
        c.drawString(M, top - ih - 6 * mm, D.CAPTIONS.get(imgs[0], ""))
        if r.get("pano"):            # the room's own 360° view as a band underneath
            by = M + 10 * mm
            bh = top - ih - 14 * mm - by
            cover_image(c, r["pano"], M, by, iw, bh)
            c.drawString(M, by - 5.5 * mm, "360° view of the same room: see the tour")
    else:
        ih = (top - M - 14 * mm - 8 * mm) / 2
        w2 = ih * 3 / 2
        for i, nm in enumerate(imgs):
            y = top - ih - i * (ih + 12 * mm)
            cover_image(c, nm, M, y, w2, ih)
            c.setFillColor(MUTED)
            c.setFont(SANS, 9)
            c.drawString(M, y - 5.5 * mm, D.CAPTIONS.get(nm, ""))
    x = W - M - panel
    c.setFillColor(INK)
    c.setFont(SERIF, 28)
    c.drawString(x, top - 12 * mm, r["title"])
    y = para(c, r["text"], x, top - 24 * mm, panel, size=10.5, lead=15.5) - 10
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(x, y, x + panel, y)
    y -= 8 * mm
    c.setFont(SANS_D, 8.5)
    c.setFillColor(MUTED)
    c.drawString(x, y, "PIECE")
    c.drawRightString(x + panel, y, "INDICATIVE, EUR")
    y -= 7 * mm
    lo = hi = 0
    for name, spec, a, b in r["items"]:
        lo, hi = lo + a, hi + b
        c.setFont(SANS_D, 10)
        c.setFillColor(INK)
        c.drawString(x, y, name)
        c.setFont(SANS, 10)
        c.drawRightString(x + panel, y, f"{eur(a)} – {eur(b)}")
        if spec:
            c.setFont(SANS, 8.8)
            c.setFillColor(MUTED)
            c.drawString(x, y - 4.6 * mm, spec)
            y -= 4.6 * mm
        y -= 8 * mm
    c.line(x, y + 3 * mm, x + panel, y + 3 * mm)
    c.setFont(SANS_D, 11)
    c.setFillColor(ACCENT)
    c.drawString(x, y - 3 * mm, "Room total")
    c.drawRightString(x + panel, y - 3 * mm, f"{eur(lo)} – {eur(hi)}")
    c.showPage()


def tour(c, n):
    page(c, n, "360° tour")
    c.setFillColor(INK)
    c.setFont(SERIF, 30)
    c.drawString(M, H - M - 14 * mm, "Walk through it")
    para(c, "Eight 360° panoramas, one in every room and on the balcony, are linked into an interactive tour: "
            "open the tour page and click the arrows in each doorway to move from room to room.",
         M, H - M - 25 * mm, 240 * mm, size=11)
    cols, gap = 2, 8 * mm
    th = (H - 2 * M - 46 * mm - 3 * 10 * mm) / 4
    tw = th * 2
    x0 = (W - (cols * tw + gap)) / 2
    for i, (nm, label) in enumerate(D.PANOS):
        col, row = i % cols, i // cols
        x = x0 + col * (tw + gap)
        y = H - M - 40 * mm - (row + 1) * th - row * 10 * mm
        cover_image(c, nm, x, y, tw, th)
        c.setFillColor(MUTED)
        c.setFont(SANS, 9)
        c.drawString(x, y - 5 * mm, label)
    c.showPage()


def budget(c, n):
    page(c, n, "Budget")
    c.setFillColor(INK)
    c.setFont(SERIF, 30)
    c.drawString(M, H - M - 14 * mm, "What it costs")
    x, wcol = M, 200 * mm
    y = H - M - 34 * mm
    c.setFont(SANS_D, 8.5)
    c.setFillColor(MUTED)
    c.drawString(x, y, "ROOM")
    c.drawRightString(x + wcol, y, "INDICATIVE, EUR")
    y -= 9 * mm
    c.setStrokeColor(RULE)
    for r in D.ROOMS:
        lo = sum(i[2] for i in r["items"])
        hi = sum(i[3] for i in r["items"])
        c.setFont(SANS, 12)
        c.setFillColor(INK)
        c.drawString(x, y, r["title"])
        c.drawRightString(x + wcol, y, f"{eur(lo)} – {eur(hi)}")
        c.line(x, y - 4 * mm, x + wcol, y - 4 * mm)
        y -= 12 * mm
    lo, hi = D.totals()
    c.setFont(SANS_D, 14)
    c.setFillColor(ACCENT)
    c.drawString(x, y - 2 * mm, "Total")
    c.drawRightString(x + wcol, y - 2 * mm, f"{eur(lo)} – {eur(hi)}")
    para(c, D.NOTE, x, y - 20 * mm, wcol, size=9.5, lead=14, color=MUTED)
    tip_x = x + wcol + 20 * mm
    c.setFont(SERIF, 18)
    c.setFillColor(INK)
    c.drawString(tip_x, H - M - 34 * mm, "Where to save, where to spend")
    tips = [
        "Spend on the sofa, the mattress and the kitchen fronts: they are touched every day.",
        "Save on the dining chairs, lamps, rugs and baskets: mid-range versions look the same in the room.",
        "One floor everywhere costs less to lay and makes the flat feel bigger.",
        "Limewash two walls instead of tiling or panelling them: the warmest effect for the least money.",
        "Zellige-look ceramic gives the handmade look of real zellige at a fraction of the price.",
    ]
    yy = H - M - 46 * mm
    for t in tips:
        c.setFillColor(ACCENT)
        c.circle(tip_x + 1.6 * mm, yy + 1.4 * mm, 1.2 * mm, stroke=0, fill=1)
        yy = para(c, t, tip_x + 6 * mm, yy, W - tip_x - M - 6 * mm, size=11, lead=16) - 8
    c.showPage()


def main():
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle(f"{D.TITLE} — {D.SUBTITLE}")
    c.setAuthor("")
    cover(c)
    n = 2
    for fn in (concept, plans):
        fn(c, n)
        n += 1
    for r in D.ROOMS:
        room(c, n, r)
        n += 1
    tour(c, n)
    n += 1
    budget(c, n)
    c.save()
    print("wrote", OUT, n, "pages")


main()
