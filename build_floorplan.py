#!/usr/bin/env python3
"""Unit 13 floor plan: dimension-driven drawing.

Every wall position derives from the dimensions printed on the source plan (cm).
Items the source does not dimension (window positions, columns, fixtures) are marked
SCALED: they were measured on a perspective-rectified copy of the photo, whose fit
against the printed dimensions has a residual of at most 1.2 cm.

Plan coordinates: cm, origin at the top-left interior corner of the living room,
x to the right, y down the sheet. The source has no north arrow, so "top" and "right"
are positions on the sheet, not compass directions.

Output: unit13_floorplan.pdf (A3, 1:50, sheets A-01 and A-02), one PNG per sheet,
and unit13_floorplan.dxf (real size, 1 unit = 1 cm, layered).

Requires: reportlab ezdxf shapely pypdfium2
Balcony A (775 x 125) was supplied separately: its depth is cut off in the photo.
Revision B applies the client sketch IMG_0410: en-suite door, storage, kitchen changes.
Revision C applies the client correction: full kitchen run moved along the wall, dining
table moved between the kitchen and the seating.
Revision D moves the storage door from the kitchen to the corridor.
"""
import math
from pathlib import Path

import ezdxf
import pypdfium2
from ezdxf.enums import TextEntityAlignment
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.ops import unary_union

OUT = Path(__file__).resolve().parent
STEM = "unit13_floorplan"

# Balcony A: supplied separately, because its depth runs off the top of the photo.
# Measured to the slab edge, from the outer face of the facade, as on Balcony B.
BAL_A_W, BAL_A_D = 775, 125

# ---------------------------------------------------------------- printed dimensions
WALL = 12            # partitions
LIVING_W = 725
OPEN_W = 311         # kitchen, and hall at the entrance
BED1_W = 402
ROOM_W = 287         # bathroom 1 and bedroom 2
EXT_LOWER = 25       # facade along Balcony B
PARTY = 30           # party walls
BAL_B_W, BAL_B_L = 145, 570
LIVING_D = 382
BED1_D = 384
BATH1_D = 192
BED2_D = 366
LEFT_RUN = 766       # overprinted on the source; proven by the closures below
BATH2_W, BATH2_D = 167, 298
ENTRY_D = 272
CORRIDOR_W = 122
HALL_CHAIN = [218, 90, 165, 80, 255, 90, 80]   # hall wall, from bedroom 1 corner down
BATH2_CHAIN = [117, 80, 125]                   # bath 2 wall, door position
LIVING_TO_COL = 342
BED1_TO_COL = 356
CLOSET_NICHE = 70

# Derived levels
Y_BED1_WALL = LIVING_D                         # 382
Y_BED1 = Y_BED1_WALL + WALL                    # 394
Y_BED1_END = Y_BED1 + BED1_D                   # 778
Y_BATH1 = Y_BED1_END + WALL                    # 790
Y_BATH1_END = Y_BATH1 + BATH1_D                # 982
Y_BED2 = Y_BATH1_END + WALL                    # 994
Y_END = Y_BED2 + BED2_D                        # 1360
X_ROOMS = OPEN_W + WALL                        # 323
X_LOWER = X_ROOMS + ROOM_W                     # 610
X_LOWER_OUT = X_LOWER + EXT_LOWER              # 635
X_BAL_B = X_LOWER_OUT + BAL_B_W                # 780
Y_B2_WALL = LEFT_RUN                           # 766
Y_B2 = Y_B2_WALL + WALL                        # 778
Y_B2_END = Y_B2 + BATH2_D                      # 1076
Y_ENTRY = Y_B2_END + WALL                      # 1088
X_B2_OUT = OPEN_W - CORRIDOR_W                 # 189
X_B2_E = X_B2_OUT - WALL                       # 177
X_B2 = X_B2_E - BATH2_W                        # 10: service lining, confirmed on the photo
Y_D1 = Y_BED1_WALL + HALL_CHAIN[0]             # 600
Y_D1_END = Y_D1 + HALL_CHAIN[1]                # 690
Y_D2 = Y_D1_END + HALL_CHAIN[2]                # 855
Y_D2_END = Y_D2 + HALL_CHAIN[3]                # 935
Y_D3 = Y_D2_END + HALL_CHAIN[4]                # 1190
Y_D3_END = Y_D3 + HALL_CHAIN[5]                # 1280
Y_D4 = Y_B2_WALL + BATH2_CHAIN[0]              # 883
Y_D4_END = Y_D4 + BATH2_CHAIN[1]               # 963
Y_ENTRY_HINGE = Y_END - CLOSET_NICHE           # 1290
Y_COL3_TOP = Y_BED1 + BED1_TO_COL              # 750
Y_COL2_END = LIVING_D - LIVING_TO_COL          # 40

CHECKS = [
    ("Top row: 311 + 12 + 402", OPEN_W + WALL + BED1_W, LIVING_W),
    ("Bath 2 row: 10 + 167 + 12 + 122", X_B2 + BATH2_W + WALL + CORRIDOR_W, OPEN_W),
    ("Length, rooms: 382+12+384+12+192+12+366", Y_END, 1360),
    ("Length, hall: 382+218+90+165+80+255+90+80", LIVING_D + sum(HALL_CHAIN), 1360),
    ("Length, left: 766+12+298+12+272", LEFT_RUN + WALL + BATH2_D + WALL + ENTRY_D, 1360),
    ("Bath 2 side: 117+80+125 = 12+298+12", sum(BATH2_CHAIN), WALL + BATH2_D + WALL),
    ("Balcony B: 1360 - 790", Y_END - Y_BATH1, BAL_B_L),
    ("Column depth: 28 + 12 (384 - 356, plus wall)", BED1_D - BED1_TO_COL + WALL, 382 - LIVING_TO_COL),
]
for name, a, b in CHECKS:
    assert a == b, f"closure failed: {name}: {a} != {b}"

# ---------------------------------------------------------------- scaled from the photo
COL_X0, COL_X1 = 530, 600
Y_STEP_WALL = 760                     # inner face of the wall at the head of Balcony B
Y_FACADE_OUT = -25                    # outer face of the top facade
W1 = (144, 444)
W2 = (95, 245)
W3 = (470, 620)
W4 = (895, 975)
W5 = (1110, 1260)
BAL_A_X1 = 750
BAL_A_X0 = BAL_A_X1 - BAL_A_W        # -25, within 1 cm of the -26 scaled from the photo
RAIL_IN, RAIL_OUT = 771, 776          # Balcony B rail, inner and outer line
Y_BAL_B_CAP = 780

# ---------------------------------------------------------------- revision B
# Storage: written as "around 1.67 x 1.67". The sketch shows about 1.20 deep; the written
# figure governs. KITCHEN_SHIFT follows STORE_D, so the kitchen run moves with it.
STORE_D = 167
Y_STORE = Y_B2_WALL - STORE_D          # 599, clear face
Y_STORE_WALL = Y_STORE - WALL          # 587, which is also the end of the kitchen run
X_STORE = X_B2_E                       # 177: the new wall continues the bathroom 2 wall
D2_NEW = (338, 418)                    # en-suite door, measured on the sketch; 80 as before

# ---------------------------------------------------------------- revision C
# The kitchen keeps its 510 run and unit order, slid toward Balcony A to end at the storage.
KITCHEN_SHIFT = Y_B2_WALL - Y_STORE_WALL   # 179
# Dining table, 180 x 85, long side parallel to W1: 88 clear to the kitchen and to the seating.
TABLE_X, TABLE_Y = 148, 200

# ---------------------------------------------------------------- revision D
# Storage door moved from the kitchen to the corridor, in the wall that continues the
# bathroom 2 wall, like D4. 80 wide, opening in, hinged at the hall end so the open leaf
# parks against the bathroom 2 wall. 10 return to the corner.
D5 = (Y_B2_WALL - 10 - 80, Y_B2_WALL - 10)   # (676, 756) along y


def R(x0, y0, x1, y1):
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


# ---------------------------------------------------------------- building fabric
BAL_A_TOP = Y_FACADE_OUT - BAL_A_D

EXT = unary_union([
    R(-56, Y_FACADE_OUT, 750, 0),
    R(LIVING_W, 0, 750, Y_BATH1),
    R(COL_X1, Y_STEP_WALL, 750, Y_BATH1),
    R(X_LOWER, Y_BATH1, X_LOWER_OUT, Y_END),
    R(-PARTY, 0, 0, Y_END),
    R(-PARTY, Y_END, X_BAL_B, Y_END + PARTY),
    R(-56, BAL_A_TOP, BAL_A_X0, Y_FACADE_OUT),
]).difference(unary_union([
    R(W1[0], Y_FACADE_OUT - 1, W1[1], 1),
    R(LIVING_W - 1, W2[0], 751, W2[1]),
    R(LIVING_W - 1, W3[0], 751, W3[1]),
    R(X_LOWER - 1, W4[0], X_LOWER_OUT + 1, W4[1]),
    R(X_LOWER - 1, W5[0], X_LOWER_OUT + 1, W5[1]),
    R(-PARTY - 1, Y_D3, 1, Y_ENTRY_HINGE),
]))

PARTITION = unary_union([
    R(OPEN_W, Y_BED1_WALL, LIVING_W, Y_BED1),
    R(OPEN_W, Y_BED1_WALL, X_ROOMS, Y_END),
    R(X_ROOMS, Y_BED1_END, COL_X0, Y_BATH1),
    R(X_ROOMS, Y_BATH1_END, X_LOWER, Y_BED2),
    R(0, Y_B2_WALL, X_B2_OUT, Y_B2),
    R(X_B2_E, Y_B2_WALL, X_B2_OUT, Y_ENTRY),
    R(0, Y_B2_END, X_B2_OUT, Y_ENTRY),
    R(0, Y_STORE_WALL, X_B2_OUT, Y_STORE),
    R(X_STORE, Y_STORE_WALL, X_B2_OUT, Y_B2_WALL),
]).difference(unary_union([
    R(OPEN_W - 1, Y_D1, X_ROOMS + 1, Y_D1_END),
    R(D2_NEW[0], Y_BED1_END - 1, D2_NEW[1], Y_BATH1 + 1),
    R(X_STORE - 1, D5[0], X_B2_OUT + 1, D5[1]),
    R(OPEN_W - 1, Y_D3, X_ROOMS + 1, Y_D3_END),
    R(X_B2_E - 1, Y_D4, X_B2_OUT + 1, Y_D4_END),
])).difference(EXT)

LINING = R(0, Y_B2, X_B2, Y_B2_END)
COLUMNS = [
    R(-40, 0, 0, 70),
    R(COL_X0, 0, COL_X1, Y_COL2_END),
    R(COL_X0, Y_COL3_TOP, COL_X1, Y_BATH1),
]

ROOMS = {
    "living": unary_union([R(0, 0, LIVING_W, LIVING_D), R(0, LIVING_D, OPEN_W, Y_B2_WALL)])
    .difference(COLUMNS[1]).difference(R(0, Y_STORE_WALL, X_B2_OUT, Y_B2_WALL)),
    "storage": R(0, Y_STORE, X_STORE, Y_B2_WALL),
    "hall": unary_union([R(X_B2_OUT, Y_B2_WALL, OPEN_W, Y_ENTRY), R(0, Y_ENTRY, OPEN_W, Y_END)]),
    "bed1": R(X_ROOMS, Y_BED1, LIVING_W, Y_BED1_END)
    .difference(R(COL_X0, Y_COL3_TOP, COL_X1, Y_BED1_END))
    .difference(R(COL_X1, Y_STEP_WALL, LIVING_W, Y_BED1_END)),
    "bed2": R(X_ROOMS, Y_BED2, X_LOWER, Y_END),
    "bath1": R(X_ROOMS, Y_BATH1, X_LOWER, Y_BATH1_END),
    "bath2": R(X_B2, Y_B2, X_B2_E, Y_B2_END),
    "bal_a": R(BAL_A_X0, BAL_A_TOP, BAL_A_X1, Y_FACADE_OUT),
    "bal_b": R(X_LOWER_OUT, Y_BATH1, X_BAL_B, Y_END),
}
AREA = {k: v.area / 1e4 for k, v in ROOMS.items()}
NET_INTERIOR = sum(AREA[k] for k in ("living", "hall", "storage", "bed1", "bed2", "bath1", "bath2"))
BALCONIES = AREA["bal_a"] + AREA["bal_b"]

# ---------------------------------------------------------------- sheet constants
PAGE_W, PAGE_H = 297.0, 420.0
K = 0.2                     # mm of paper per cm of plan = 1:50
MM = 1 / K                  # cm of plan per mm of paper
FRAME = 10.0
PANEL_X = 205.0
OX, OY = 41.0, 72.0

INK = HexColor("#14171a")
GREY = HexColor("#5d646b")
FURN = HexColor("#737a82")
PALE = HexColor("#d3d9de")
RULE = HexColor("#c4cad0")
GLASS = HexColor("#1f6fb5")
SCALED = HexColor("#1f6fb5")
FLAG = HexColor("#b3261e")
WHITE = HexColor("#ffffff")
EXT_FILL = HexColor("#454c53")
PART_FILL = HexColor("#a9b0b7")
LINING_FILL = HexColor("#e2e6e9")
BLACK = HexColor("#000000")
SILL = HexColor("#eef3f7")
HEAD = HexColor("#eef0f2")

F, FB, FI = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"
DXF_LAYERS = {
    "A-WALL-EXT": 8, "A-WALL-INT": 9, "A-WALL-LINING": 254, "A-COLS": 7, "A-DOOR": 3, "A-GLAZ": 5,
    "A-FURN": 253, "A-FIXT": 252, "A-BALC": 251, "A-DIMS": 1, "A-DIMS-SCALED": 4, "A-ANNO": 2,
}


class Sheet:
    """Draws into the PDF in paper mm. Plan-space calls also go to the DXF when dxf is set."""

    def __init__(self, c, msp=None):
        self.c = c
        self.msp = msp

    @staticmethod
    def X(x):
        return OX + x * K

    @staticmethod
    def Y(y):
        return OY + y * K

    # paper-space -------------------------------------------------------------
    def p(self, x, y):
        return x * mm, (PAGE_H - y) * mm

    def stroke(self, color, lw, dash=None):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(lw * mm)
        self.c.setDash(*dash) if dash else self.c.setDash()
        self.c.setLineCap(0)
        self.c.setLineJoin(1)

    def pline(self, pts, color=INK, lw=0.15, closed=False, fill=None, dash=None):
        path = self.c.beginPath()
        path.moveTo(*self.p(*pts[0]))
        for q in pts[1:]:
            path.lineTo(*self.p(*q))
        if closed:
            path.close()
        self.stroke(color, lw, dash)
        if fill is not None:
            self.c.setFillColor(fill)
        self.c.drawPath(path, stroke=1 if lw > 0 else 0, fill=1 if fill is not None else 0)

    def text(self, x, y, s, size=7, font=F, color=INK, anchor="c", rot=0, bg=None):
        c = self.c
        c.saveState()
        c.translate(*self.p(x, y))
        c.rotate(rot)
        w = stringWidth(s, font, size)
        dx = {"l": 0, "c": -w / 2, "r": -w}[anchor]
        if bg is not None:
            c.setFillColor(bg)
            c.rect(dx - 0.9, -size * 0.45, w + 1.8, size * 0.9, stroke=0, fill=1)
        c.setFillColor(color)
        c.setFont(font, size)
        c.drawString(dx, -size * 0.36, s)
        c.restoreState()

    # plan-space --------------------------------------------------------------
    def _dxf_poly(self, pts, layer, closed=False):
        if self.msp is not None:
            self.msp.add_lwpolyline([(x, -y) for x, y in pts], close=closed, dxfattribs={"layer": layer})

    def line(self, pts, color=INK, lw=0.15, closed=False, fill=None, dash=None, layer="A-FURN"):
        self.pline([(self.X(x), self.Y(y)) for x, y in pts], color, lw, closed, fill, dash)
        self._dxf_poly(pts, layer, closed)

    def rect(self, x0, y0, x1, y1, color=INK, lw=0.15, fill=None, layer="A-FURN"):
        self.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color, lw, True, fill, layer=layer)

    def arc(self, cx, cy, r, a0, a1, color=INK, lw=0.13, layer="A-DOOR"):
        n = max(8, int(abs(a1 - a0)))
        pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.pline([(self.X(x), self.Y(y)) for x, y in pts], color, lw)
        if self.msp is not None:
            self.msp.add_arc((cx, -cy), r, -max(a0, a1), -min(a0, a1), dxfattribs={"layer": layer})

    def circle(self, cx, cy, r, color=INK, lw=0.13, fill=None, layer="A-FURN"):
        self.stroke(color, lw)
        if fill is not None:
            self.c.setFillColor(fill)
        self.c.circle(self.X(cx) * mm, (PAGE_H - self.Y(cy)) * mm, r * K * mm, stroke=1, fill=1 if fill is not None else 0)
        if self.msp is not None:
            self.msp.add_circle((cx, -cy), r, dxfattribs={"layer": layer})

    def shape(self, geom, fill, color=INK, lw=0.4, layer="A-WALL-EXT"):
        polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
        for poly in polys:
            path = self.c.beginPath()
            for ring in [poly.exterior, *poly.interiors]:
                pts = [self.p(self.X(x), self.Y(y)) for x, y in ring.coords]
                path.moveTo(*pts[0])
                for q in pts[1:-1]:
                    path.lineTo(*q)
                path.close()
            self.stroke(color, lw)
            self.c.setFillColor(fill)
            self.c.drawPath(path, stroke=1, fill=1, fillMode=0)
            if self.msp is not None:
                h = self.msp.add_hatch(dxfattribs={"layer": layer})
                for ring in [poly.exterior, *poly.interiors]:
                    h.paths.add_polyline_path([(x, -y) for x, y in ring.coords], is_closed=True)
                    self._dxf_poly(list(ring.coords)[:-1], layer, True)

    def ptext(self, x, y, s, size=7, font=F, color=INK, anchor="c", rot=0, bg=None, layer="A-ANNO"):
        self.text(self.X(x), self.Y(y), s, size, font, color, anchor, rot, bg)
        if self.msp is not None:
            align = {"l": TextEntityAlignment.MIDDLE_LEFT, "c": TextEntityAlignment.MIDDLE_CENTER,
                     "r": TextEntityAlignment.MIDDLE_RIGHT}[anchor]
            t = self.msp.add_text(s, height=size * 0.3528 * 0.72 * MM, rotation=rot, dxfattribs={"layer": layer})
            t.set_placement((x, -y), align=align)


# ---------------------------------------------------------------- symbols
def rrect_pts(x0, y0, x1, y1, r):
    pts = []
    for cx, cy, a in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(0, 91, 15):
            t = math.radians(a + i)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def rrect(S, x0, y0, x1, y1, r=4, color=FURN, lw=0.13, fill=None, layer="A-FURN"):
    S.line(rrect_pts(x0, y0, x1, y1, r), color, lw, True, fill, layer=layer)


def ubowl(x0, y0, x1, y1, end):
    """Sanitary bowl: square at the wall, rounded towards `end` ('n' or 'e')."""
    pts = []
    if end == "n":
        cx, r = (x0 + x1) / 2, (x1 - x0) / 2
        pts.append((x0, y1))
        for i in range(0, 181, 10):
            t = math.radians(180 + i)
            pts.append((cx + r * math.cos(t), y0 + r + r * math.sin(t)))
        pts.append((x1, y1))
    else:
        cy, r = (y0 + y1) / 2, (y1 - y0) / 2
        pts.append((x0, y0))
        for i in range(0, 181, 10):
            t = math.radians(-90 + i)
            pts.append((x1 - r + r * math.cos(t), cy + r * math.sin(t)))
        pts.append((x0, y1))
    return pts


def wc(S, x0, y0, x1, y1, end):
    S.line(ubowl(x0, y0, x1, y1, end), FURN, 0.15, True, WHITE, layer="A-FIXT")
    if end == "n":
        S.line(ubowl(x0 + 6, y0 + 6, x1 - 6, y1 - 10, end), FURN, 0.1, True, layer="A-FIXT")
        S.rect(x0 + 3, y1 - 6, x1 - 3, y1, FURN, 0.1, layer="A-FIXT")
    else:
        S.line(ubowl(x0 + 10, y0 + 5, x1 - 6, y1 - 5, end), FURN, 0.1, True, layer="A-FIXT")
        S.rect(x0, y0 + 3, x0 + 6, y1 - 3, FURN, 0.1, layer="A-FIXT")


def bidet(S, x0, y0, x1, y1, end):
    S.line(ubowl(x0, y0, x1, y1, end), FURN, 0.15, True, WHITE, layer="A-FIXT")
    if end == "n":
        S.line(ubowl(x0 + 6, y0 + 6, x1 - 6, y1 - 9, end), FURN, 0.1, True, layer="A-FIXT")
        S.circle((x0 + x1) / 2, y1 - 5, 2, FURN, 0.1, layer="A-FIXT")
    else:
        S.line(ubowl(x0 + 10, y0 + 5, x1 - 6, y1 - 5, end), FURN, 0.1, True, layer="A-FIXT")
        S.circle(x0 + 5, (y0 + y1) / 2, 2, FURN, 0.1, layer="A-FIXT")


def lamp(S, cx, cy, r=15):
    S.circle(cx, cy, r, FURN, 0.1)
    S.circle(cx, cy, r * 0.6, FURN, 0.1)
    S.line([(cx - r * 1.3, cy), (cx + r * 1.3, cy)], FURN, 0.08)
    S.line([(cx, cy - r * 1.3), (cx, cy + r * 1.3)], FURN, 0.08)


def closet(S, x0, y0, x1, y1):
    S.rect(x0, y0, x1, y1, FURN, 0.13, WHITE)
    S.line([(x0, y0), (x1, y1)], PALE, 0.1)
    S.line([(x0, y1), (x1, y0)], PALE, 0.1)


def stars(S, cx, cy, r=5):
    for a in (0, 45, 90, 135):
        t = math.radians(a)
        S.line([(cx - r * math.cos(t), cy - r * math.sin(t)), (cx + r * math.cos(t), cy + r * math.sin(t))], FURN, 0.1, layer="A-FIXT")


def chair(S, x0, y0, x1, y1, back):
    ins = 3
    if back == "n":
        S.line([(x0 + ins, y0 + 3), (x1 - ins, y0 + 3), (x1, y1), (x0, y1)], FURN, 0.13, True, WHITE)
        S.line([(x0 - 1, y0 + 2), ((x0 + x1) / 2, y0 - 2), (x1 + 1, y0 + 2)], FURN, 0.1)
    else:
        S.line([(x0, y0), (x1, y0), (x1 - ins, y1 - 3), (x0 + ins, y1 - 3)], FURN, 0.13, True, WHITE)
        S.line([(x0 - 1, y1 - 2), ((x0 + x1) / 2, y1 + 2), (x1 + 1, y1 - 2)], FURN, 0.1)


def grid(S, geom, step, color=PALE, lw=0.07):
    x0, y0, x1, y1 = geom.bounds
    segs = []
    x = x0 + step
    while x < x1:
        segs.append(LineString([(x, y0), (x, y1)]))
        x += step
    y = y0 + step
    while y < y1:
        segs.append(LineString([(x0, y), (x1, y)]))
        y += step
    for s in segs:
        r = s.intersection(geom)
        if not r.is_empty:
            for part in (r.geoms if hasattr(r, "geoms") else [r]):
                S.pline([(S.X(a), S.Y(b)) for a, b in part.coords], color, lw)


def door(S, hinge, leaf, towards, width):
    hx, hy = hinge
    lx, ly = leaf
    ox, oy = towards
    t = 5
    pts = [(hx, hy), (hx + lx * width, hy + ly * width),
           (hx + lx * width + ox * t, hy + ly * width + oy * t), (hx + ox * t, hy + oy * t)]
    S.line(pts, INK, 0.2, True, WHITE, layer="A-DOOR")
    a0 = math.degrees(math.atan2(ly, lx))
    a1 = math.degrees(math.atan2(oy, ox))
    if a1 - a0 > 180:
        a1 -= 360
    if a0 - a1 > 180:
        a1 += 360
    S.arc(hx, hy, width, a0, a1, INK, 0.1)


def leaf_45(S, hinge, closed_dir, room_dir, r):
    """Inward casement leaf shown 45 degrees open with its swing arc, as on the source."""
    hx, hy = hinge
    cx, cy = closed_dir
    rx, ry = room_dir
    s = r * math.sqrt(0.5)
    tip = (hx + (cx + rx) * s, hy + (cy + ry) * s)
    S.line([hinge, tip], GLASS, 0.13, layer="A-GLAZ")
    a0 = math.degrees(math.atan2(tip[1] - hy, tip[0] - hx))
    a1 = math.degrees(math.atan2(cy, cx))
    if a1 - a0 > 180:
        a1 -= 360
    if a0 - a1 > 180:
        a1 += 360
    S.arc(hx, hy, r, a0, a1, GLASS, 0.1, layer="A-GLAZ")


def win_h(S, x0, x1, y_out, y_in, frame=8):
    S.rect(x0, y_out, x1, y_in, GREY, 0.1, SILL, layer="A-GLAZ")
    S.rect(x0, y_in - frame, x1, y_in, GLASS, 0.15, WHITE, layer="A-GLAZ")
    S.line([(x0, y_in - frame / 2), (x1, y_in - frame / 2)], GLASS, 0.2, layer="A-GLAZ")


def win_v(S, y0, y1, x_in, x_out, frame=8):
    S.rect(x_in, y0, x_out, y1, GREY, 0.1, SILL, layer="A-GLAZ")
    S.rect(x_in, y0, x_in + frame, y1, GLASS, 0.15, WHITE, layer="A-GLAZ")
    S.line([(x_in + frame / 2, y0), (x_in + frame / 2, y1)], GLASS, 0.2, layer="A-GLAZ")


def tag(S, x, y, s):
    if s.startswith("D"):
        S.circle(x, y, 8.5, INK, 0.13, WHITE, layer="A-ANNO")
    else:
        S.rect(x - 8.5, y - 7, x + 8.5, y + 7, GLASS, 0.13, WHITE, layer="A-ANNO")
    S.ptext(x, y, s, 4.8, FB, INK if s.startswith("D") else GLASS)


def room_label(S, x, y, name, area, size=None, big=True):
    a, b = (8.2, 7.4) if big else (7, 6.4)
    S.ptext(x, y - 13, name, a, FB, INK, bg=WHITE)
    S.ptext(x, y + 1, area, b, F, INK, bg=WHITE)
    if size:
        S.ptext(x, y + 14, size, 6, F, GREY, bg=WHITE)


# ---------------------------------------------------------------- dimensions
def _label(S, x, y, lab, rot):
    scaled = lab.startswith("~")
    S.ptext(x, y, lab, 6.3, FI if scaled else F, SCALED if scaled else INK, rot=rot, bg=WHITE,
            layer="A-DIMS-SCALED" if scaled else "A-DIMS")


def hdim(S, y, xs, labels, anchors=None, nudge=None, scaled=False, above=True):
    nudge = nudge or {}
    layer = "A-DIMS-SCALED" if scaled else "A-DIMS"
    col = SCALED if scaled else INK
    S.line([(xs[0] - 8, y), (xs[-1] + 8, y)], col, 0.1, layer=layer)
    for i, x in enumerate(xs):
        S.line([(x - 4, y + 4), (x + 4, y - 4)], col, 0.22, layer=layer)
        if anchors is not None and anchors[i] is not None:
            a = anchors[i]
            S.line([(x, a + (4 if y > a else -4)), (x, y + (6 if y > a else -6))], RULE, 0.08, layer=layer)
    off = -10 if above else 10
    for i, lab in enumerate(labels):
        if lab:
            dx, dy = nudge.get(i, (0, 0))
            _label(S, (xs[i] + xs[i + 1]) / 2 + dx, y + off + dy, lab, 0)


def vdim(S, x, ys, labels, anchors=None, nudge=None, scaled=False, left=True):
    nudge = nudge or {}
    layer = "A-DIMS-SCALED" if scaled else "A-DIMS"
    col = SCALED if scaled else INK
    S.line([(x, ys[0] - 8), (x, ys[-1] + 8)], col, 0.1, layer=layer)
    for i, y in enumerate(ys):
        S.line([(x - 4, y + 4), (x + 4, y - 4)], col, 0.22, layer=layer)
        if anchors is not None and anchors[i] is not None:
            a = anchors[i]
            S.line([(a + (4 if x > a else -4), y), (x + (6 if x > a else -6), y)], RULE, 0.08, layer=layer)
    off = -10 if left else 10
    for i, lab in enumerate(labels):
        if lab:
            dx, dy = nudge.get(i, (0, 0))
            _label(S, x + off + dx, (ys[i] + ys[i + 1]) / 2 + dy, lab, 90)


# ---------------------------------------------------------------- plan content
def draw_floors(S, with_fixtures=True):
    bal_a = R(BAL_A_X0, BAL_A_TOP, BAL_A_X1, Y_FACADE_OUT)
    bal_b = Polygon([(X_LOWER_OUT, Y_BATH1), (750, Y_BATH1), (750, Y_BAL_B_CAP), (X_BAL_B, Y_BAL_B_CAP),
                     (X_BAL_B, Y_END), (X_LOWER_OUT, Y_END)])
    grid(S, bal_a, 40)
    grid(S, bal_b, 40)
    if with_fixtures:
        grid(S, ROOMS["bath1"], 30)
        grid(S, ROOMS["bath2"], 30)
    S.line(list(bal_b.exterior.coords)[:-1], INK, 0.2, True, layer="A-BALC")
    for path in (
        [(750, 788), (RAIL_IN, 788), (RAIL_IN, Y_END)],
        [(750, 782), (RAIL_OUT, 782), (RAIL_OUT, Y_END)],
    ):
        S.line(path, GREY, 0.13, layer="A-BALC")
    # Balcony A: slab edge, with the rail set in from it as on Balcony B. The far side is
    # outside the photo, so the top run of rail is assumed.
    S.line([(BAL_A_X0, BAL_A_TOP), (BAL_A_X1, BAL_A_TOP), (BAL_A_X1, Y_FACADE_OUT)], INK, 0.2, layer="A-BALC")
    for inset, x in ((10, 740), (5, 745)):
        S.line([(BAL_A_X0, BAL_A_TOP + inset), (x, BAL_A_TOP + inset), (x, Y_FACADE_OUT)], GREY, 0.13, layer="A-BALC")
    # Juliet rails outside W2 and W3
    for y0, y1 in ((W2[0] - 13, W2[1] + 13), (W3[0] - 13, W3[1] + 13)):
        S.rect(750, y0, 762, y1, GREY, 0.13, layer="A-BALC")
        S.line([(756, y0), (756, y1)], GREY, 0.08, layer="A-BALC")


def draw_furniture(S):
    # kitchen run: figures are the source positions, moved along the wall by ky()
    def ky(y):
        return y - KITCHEN_SHIFT

    S.rect(0, ky(256), 60, ky(Y_B2_WALL), FURN, 0.15, WHITE)
    for y0, y1 in ((256, 316), (376, 436), (586, 646), (706, Y_B2_WALL)):
        closet(S, 2, ky(y0), 58, ky(y1))
    for y in (316, 376, 436, 500, 586, 646, 706):
        S.line([(0, ky(y)), (60, ky(y))], FURN, 0.1)
    for y in (330, 347, 365):
        stars(S, 18, ky(y))
    for y in (457, 473, 490):
        stars(S, 50, ky(y))
    # sink
    rrect(S, 10, ky(506), 52, ky(580), 3, layer="A-FIXT")
    S.line([(11, ky(543)), (51, ky(543))], FURN, 0.1, layer="A-FIXT")
    S.circle(15, ky(521), 3, FURN, 0.1, layer="A-FIXT")
    S.circle(15, ky(564), 3, FURN, 0.1, layer="A-FIXT")
    S.line([(6, ky(543)), (23, ky(536))], FURN, 0.14, layer="A-FIXT")
    # hob
    S.rect(2, ky(649), 57, ky(705), FURN, 0.13)
    for cx, cy, r in ((17, ky(664), 12), (43, ky(664), 8), (17, ky(691), 10), (43, ky(691), 9)):
        S.circle(cx, cy, r, FURN, 0.1, layer="A-FIXT")
        S.line([(cx - r - 2, cy), (cx + r + 2, cy)], FURN, 0.07)
        S.line([(cx, cy - r - 2), (cx, cy + r + 2)], FURN, 0.07)
    S.rect(58, ky(652), 61, ky(702), FURN, 0.1)
    # dining
    for x0, x1 in ((7, 52), (70, 115), (127, 173)):
        chair(S, TABLE_X + x0, TABLE_Y - 40, TABLE_X + x1, TABLE_Y + 5, "n")
        chair(S, TABLE_X + x0, TABLE_Y + 77, TABLE_X + x1, TABLE_Y + 123, "s")
    S.rect(TABLE_X, TABLE_Y, TABLE_X + 180, TABLE_Y + 85, FURN, 0.15, WHITE)
    # seating group
    rrect(S, 484, 40, 700, 121, 3, fill=WHITE)
    for x0, x1 in ((494, 557), (560, 624), (627, 691)):
        rrect(S, x0, 52, x1, 119, 3)
    rrect(S, 416, 117, 496, 277, 3, fill=WHITE)
    S.line([(416, 132), (492, 132)], FURN, 0.1)
    S.line([(416, 262), (492, 262)], FURN, 0.1)
    rrect(S, 428, 132, 496, 196, 3)
    rrect(S, 428, 198, 496, 262, 3)
    S.rect(416, 45, 476, 107, FURN, 0.13, WHITE)
    lamp(S, 447, 76)
    S.rect(555, 185, 654, 245, FURN, 0.15, WHITE)
    S.rect(560, 190, 649, 240, FURN, 0.08)
    # TV unit in the living room
    S.line([(449, Y_BED1_WALL), (449, 347), (LIVING_W, 347)], FURN, 0.13)
    S.rect(501, 361, 632, 367, FURN, 0.13)
    # bedroom 1
    rrect(S, 424, 396, 623, 609, 3, fill=WHITE)
    rrect(S, 449, 403, 520, 446, 3)
    rrect(S, 527, 403, 598, 446, 3)
    S.line([(424, 450), (623, 450)], FURN, 0.1)
    S.line([(578, 450), (623, 490), (578, 490), (578, 450)], FURN, 0.1)
    for x0, x1, cx in ((367, 424, 393), (623, 680, 653)):
        S.rect(x0, 395, x1, 445, FURN, 0.13, WHITE)
        lamp(S, cx, 420)
    for x0, x1 in ((443, 503), (503, 530)):
        closet(S, x0, 720, x1, Y_BED1_END)
    S.line([(COL_X0, 718), (LIVING_W, 718)], FURN, 0.13)
    S.rect(561, 728, 691, 733, FURN, 0.13)
    # bedroom 2
    rrect(S, 401, 997, 597, 1096, 3, fill=WHITE)
    rrect(S, 565, 1013, 588, 1074, 3)
    S.line([(556, 998), (556, 1095)], FURN, 0.1)
    S.line([(533, 1095), (556, 1048)], FURN, 0.1)
    S.line([(533, 1048), (556, 1048)], FURN, 0.1)
    S.line([(533, 1048), (533, 1095)], FURN, 0.1)
    S.rect(569, 1100, 607, 1139, FURN, 0.13, WHITE)
    lamp(S, 588, 1119, 11)
    for x0, x1 in ((323, 383), (383, 443), (443, 503)):
        closet(S, x0, 1300, x1, Y_END)
    S.rect(503, 1311, X_LOWER, Y_END, FURN, 0.13, WHITE)
    rrect(S, 518, 1287, 580, 1312, 6)
    rrect(S, 524, 1293, 574, 1312, 4)
    # hall closets
    for x0, x1 in ((0, 60), (60, 120), (120, 180)):
        closet(S, x0, Y_ENTRY, x1, 1148)
        closet(S, x0, 1300, x1, Y_END)
    # bathroom 1
    S.rect(X_ROOMS, 922, 382, Y_BATH1_END, FURN, 0.13, WHITE, layer="A-FIXT")
    S.ptext(352, 945, "boiler +", 4.8, F, GREY)
    S.ptext(352, 958, "washer", 4.8, F, GREY)
    S.rect(418, Y_BATH1, 490, 836, FURN, 0.13, WHITE, layer="A-FIXT")
    rrect(S, 426, 800, 482, 831, 8, layer="A-FIXT")
    S.line([(454, 793), (454, 812)], FURN, 0.13, layer="A-FIXT")
    wc(S, 434, 924, 473, Y_BATH1_END, "n")
    bidet(S, 493, 924, 533, Y_BATH1_END, "n")
    S.rect(529, 797, 588, 802, FURN, 0.13, layer="A-FIXT")
    S.ptext(558, 810, "drain 60", 4.6, F, GREY)
    S.line([(524, Y_BATH1), (524, 893)], GLASS, 0.14, layer="A-GLAZ")
    S.line([(528, 889), (528, Y_BATH1_END)], GLASS, 0.14, layer="A-GLAZ")
    # bathroom 2
    S.line([(X_B2, 852), (112, 852)], GLASS, 0.14, layer="A-GLAZ")
    S.line([(97, 857), (X_B2_E, 857)], GLASS, 0.14, layer="A-GLAZ")
    S.rect(16, 788, 21, 847, FURN, 0.13, layer="A-FIXT")
    S.ptext(30, 818, "drain 60", 4.6, F, GREY, rot=90)
    wc(S, X_B2, 897, 60, 933, "e")
    bidet(S, X_B2, 957, 68, 995, "e")
    S.rect(13, 1031, 173, Y_B2_END, FURN, 0.13, WHITE, layer="A-FIXT")
    rrect(S, 63, 1037, 123, 1070, 8, layer="A-FIXT")
    S.line([(93, 1058), (93, 1074)], FURN, 0.13, layer="A-FIXT")


def draw_structure(S):
    S.shape(EXT, EXT_FILL, INK, 0.4, "A-WALL-EXT")
    S.shape(PARTITION, PART_FILL, INK, 0.3, "A-WALL-INT")
    S.shape(LINING, LINING_FILL, INK, 0.2, "A-WALL-LINING")
    for col in COLUMNS:
        S.shape(col, BLACK, BLACK, 0.3, "A-COLS")


def draw_openings(S):
    door(S, (X_ROOMS, Y_D1_END), (1, 0), (0, -1), HALL_CHAIN[1])
    door(S, (D2_NEW[0], Y_BATH1), (0, 1), (1, 0), D2_NEW[1] - D2_NEW[0])
    door(S, (X_STORE, D5[1]), (-1, 0), (0, -1), D5[1] - D5[0])
    door(S, (X_ROOMS, Y_D3_END), (1, 0), (0, -1), HALL_CHAIN[5])
    door(S, (X_B2_E, Y_D4), (-1, 0), (0, 1), BATH2_CHAIN[1])
    door(S, (0, Y_ENTRY_HINGE), (1, 0), (0, -1), Y_ENTRY_HINGE - Y_D3)
    # entrance door frame in the wall
    S.rect(-PARTY, Y_D3, 0, Y_ENTRY_HINGE, GREY, 0.1, HEAD, layer="A-DOOR")
    win_h(S, W1[0], W1[1], Y_FACADE_OUT, 0)
    mid = sum(W1) / 2
    S.rect(mid - 3, -8, mid + 3, 0, GLASS, 0.15, WHITE, layer="A-GLAZ")
    leaf_45(S, (W1[0], 0), (1, 0), (0, 1), 150)
    leaf_45(S, (W1[1], 0), (-1, 0), (0, 1), 150)
    for y0, y1 in (W2, W3):
        win_v(S, y0, y1, LIVING_W, 750)
        leaf_45(S, (LIVING_W, y0), (0, 1), (-1, 0), 75)
        leaf_45(S, (LIVING_W, y1), (0, -1), (-1, 0), 75)
    win_v(S, W4[0], W4[1], X_LOWER, X_LOWER_OUT, frame=10)
    win_v(S, W5[0], W5[1], X_LOWER, X_LOWER_OUT)
    leaf_45(S, (X_LOWER, W5[0]), (0, 1), (-1, 0), 75)
    leaf_45(S, (X_LOWER, W5[1]), (0, -1), (-1, 0), 75)


def m2(v):
    return f"{v:.2f} m²"


def draw_tags(S):
    for x, y, s in ((-15, Y_D3 + 50, "D0"), (345, 640, "D1"), (362, 815, "D2"), (345, 1235, "D3"), (158, 905, "D4"),
                    (155, 618, "D5")):
        tag(S, x, y, s)
    for x, y, s in ((sum(W1) / 2, 44, "W1"), (697, sum(W2) / 2, "W2"), (697, sum(W3) / 2, "W3"),
                    (592, sum(W4) / 2, "W4"), (582, sum(W5) / 2, "W5")):
        tag(S, x, y, s)


def sheet_furnished(S):
    draw_floors(S)
    draw_furniture(S)
    draw_structure(S)
    draw_openings(S)
    draw_tags(S)
    room_label(S, 195, 410, "LIVING ROOM + KITCHEN", m2(AREA["living"]), "725 × 382 + 311 × 384, less storage")
    room_label(S, 212, 1225, "ENTRANCE HALL", m2(AREA["hall"]), "122 × 322 + 311 × 272")
    room_label(S, 590, 665, "BEDROOM 1", m2(AREA["bed1"]), "402 × 384")
    room_label(S, 480, 1200, "BEDROOM 2", m2(AREA["bed2"]), "287 × 366")
    room_label(S, 472, 880, "BATHROOM 1", m2(AREA["bath1"]), "287 × 192, en-suite", big=False)
    room_label(S, 72, 690, "STORAGE", m2(AREA["storage"]), "177 × 167", big=False)
    room_label(S, 123, 998, "BATHROOM 2", m2(AREA["bath2"]), "167 × 298", big=False)
    room_label(S, 703, 1075, "BALCONY B", m2(AREA["bal_b"]), "145 × 570", big=False)
    room_label(S, 362, -90, "BALCONY A", m2(AREA["bal_a"]), "775 × 125", big=False)
    S.ptext(362, BAL_A_TOP - 18, "SEA VIEW", 7.4, FB, GLASS)
    S.line([(362, BAL_A_TOP - 28), (362, BAL_A_TOP - 50)], GLASS, 0.25, layer="A-ANNO")
    S.line([(355, BAL_A_TOP - 41), (362, BAL_A_TOP - 50), (369, BAL_A_TOP - 41)], GLASS, 0.25, layer="A-ANNO")


def dims_overview(S):
    """Overall chains only: every dimension is on sheet A-02."""
    left = [0, LEFT_RUN, Y_B2, Y_B2_END, Y_ENTRY, Y_END]
    vdim(S, -62, left, ["766", "12", "298", "12", "272"], [-PARTY] * 6)
    vdim(S, -92, [0, Y_END], ["1360"])
    row = [0, OPEN_W, X_ROOMS, X_LOWER, X_LOWER_OUT, X_BAL_B]
    hdim(S, Y_END + 62, row, ["311", "12", "287", "25", "145"], [Y_END + PARTY] * 6)
    hdim(S, Y_END + 92, [0, LIVING_W], ["725"])
    S.line([(LIVING_W, Y_END + 88), (LIVING_W, Y_END + 34)], RULE, 0.08, layer="A-DIMS")


def sheet_dimensioned(S):
    draw_floors(S, with_fixtures=False)
    draw_structure(S)
    draw_openings(S)
    draw_tags(S)
    room_label(S, 200, 300, "LIVING ROOM + KITCHEN", m2(AREA["living"]))
    room_label(S, 200, 1235, "ENTRANCE HALL", m2(AREA["hall"]))
    room_label(S, 640, 650, "BEDROOM 1", m2(AREA["bed1"]))
    room_label(S, 520, 1250, "BEDROOM 2", m2(AREA["bed2"]))
    room_label(S, 530, 880, "BATHROOM 1", m2(AREA["bath1"]), big=False)
    room_label(S, 92, 825, "BATHROOM 2", m2(AREA["bath2"]), big=False)
    room_label(S, 701, 1075, "BALCONY B", m2(AREA["bal_b"]), big=False)
    room_label(S, 362, -100, "BALCONY A", m2(AREA["bal_a"]), "sea view", big=False)
    room_label(S, 75, 700, "STORAGE", m2(AREA["storage"]), big=False)


def dims_full(S):
    # rows from the source
    hdim(S, 110, [0, LIVING_W], ["725"])
    hdim(S, 555, [0, OPEN_W, X_ROOMS, LIVING_W], ["311", "12", "402"], nudge={0: (45, 0)})
    hdim(S, 972, [X_B2, X_B2_E, X_B2_OUT, OPEN_W, X_ROOMS, X_LOWER], ["167", "12", "122", "12", "287"])
    hdim(S, 1150, [0, OPEN_W, X_ROOMS, X_LOWER, X_LOWER_OUT, X_BAL_B], ["311", "12", "287", "25", "145"])
    hdim(S, 135, [-PARTY, 0], ["30"])
    # lengths
    ys = [0, LIVING_D, Y_BED1, Y_BED1_END, Y_BATH1, Y_BATH1_END, Y_BED2, Y_END, Y_END + PARTY]
    vdim(S, 454, ys, ["382", "12", "384", "12", "192", "12", "366", "30"],
         nudge={1: (-3, -6), 3: (-3, -6), 5: (-3, -6)})
    vdim(S, 569, [Y_COL2_END, LIVING_D, Y_BED1, Y_COL3_TOP], ["342", "12", "356"], nudge={1: (-3, -6)})
    vdim(S, 296, [Y_BED1_WALL, Y_D1, Y_D1_END, Y_D3, Y_D3_END, Y_END],
         ["218", "90", str(Y_D3 - Y_D1_END), "90", "80"])
    # revision B
    vdim(S, 30, [Y_STORE_WALL, Y_STORE, Y_B2_WALL], ["12", str(STORE_D)], nudge={0: (-3, -6)})
    hdim(S, 650, [0, X_STORE, X_B2_OUT, OPEN_W], ["~177", "12", "122"])
    vdim(S, 205, [Y_STORE, D5[0], D5[1], Y_B2_WALL],
         [f"~{D5[0] - Y_STORE}", "~80", f"~{Y_B2_WALL - D5[1]}"], nudge={2: (0, -10)}, scaled=True, left=False)
    hdim(S, 762, [X_ROOMS, D2_NEW[0], D2_NEW[1], COL_X0], ["~15", "~80", "~112"], scaled=True)
    vdim(S, 205, [Y_B2_WALL, Y_D4, Y_D4_END, Y_ENTRY], [str(v) for v in BATH2_CHAIN], left=False)
    vdim(S, 150, [Y_ENTRY_HINGE, Y_END], ["70"], anchors=[None, None])
    S.line([(100, Y_ENTRY_HINGE), (156, Y_ENTRY_HINGE)], RULE, 0.08, layer="A-DIMS")
    vdim(S, 757, [Y_BATH1, Y_END], ["570"])
    hdim(S, BAL_A_TOP - 24, [BAL_A_X0, BAL_A_X1], ["775"], [BAL_A_TOP] * 2)
    vdim(S, 790, [BAL_A_TOP, Y_FACADE_OUT], ["125"], [BAL_A_X1] * 2, left=False)
    left = [0, LEFT_RUN, Y_B2, Y_B2_END, Y_ENTRY, Y_END]
    vdim(S, -62, left, ["766", "12", "298", "12", "272"], [-PARTY] * 6)
    vdim(S, -92, [0, Y_END], ["1360"])
    # scaled or derived values
    hdim(S, 972, [0, X_B2], ["~10"], nudge={0: (24, 0)}, scaled=True)
    hdim(S, Y_FACADE_OUT - 18, [0, W1[0], W1[1], LIVING_W], ["~144", "~300", "~281"], [Y_FACADE_OUT] * 4, scaled=True)
    hdim(S, 58, [COL_X0, COL_X1, LIVING_W], ["~70", "~125"], scaled=True)
    vdim(S, 790, [Y_FACADE_OUT, 0, W2[0], W2[1], W3[0], W3[1], Y_STEP_WALL, Y_BATH1],
         ["~25", "~95", "~150", "~225", "~150", "~140", "~30"], [750] * 8, scaled=True, left=False)
    vdim(S, 650, [Y_BATH1, W4[0], W4[1], W5[0], W5[1], Y_END], ["~105", "~80", "~135", "~150", "~100"], [X_LOWER_OUT] * 6,
         scaled=True, left=False)
    vdim(S, 20, [Y_D3, Y_ENTRY_HINGE], ["~100"], scaled=True, left=False)


# ---------------------------------------------------------------- side panel
def wrap(s, width_mm, font, size):
    out, line = [], ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if stringWidth(trial, font, size) / mm > width_mm:
            out.append(line)
            line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out


class Panel:
    def __init__(self, S, y=FRAME + 7):
        self.S = S
        self.x0 = PANEL_X + 4
        self.x1 = PAGE_W - FRAME - 4
        self.y = y

    def head(self, s):
        self.y += 3
        self.S.text(self.x0, self.y, s, 8.6, FB, INK, "l")
        self.y += 2.4
        self.S.pline([(self.x0, self.y), (self.x1, self.y)], INK, 0.25)
        self.y += 4.2

    def row(self, cells, xs, size=7.4, font=F, color=INK, aligns=None, gap=4.7, rule=True):
        aligns = aligns or ["l"] * len(cells)
        for c, x, a in zip(cells, xs, aligns):
            self.S.text(x, self.y, c, size, font, color, a)
        self.y += gap * 0.55
        if rule:
            self.S.pline([(self.x0, self.y), (self.x1, self.y)], PALE, 0.1)
        self.y += gap * 0.45

    def para(self, s, size=7.2, font=F, color=INK, lead=3.3, indent=0, width=None):
        for line in wrap(s, width or (self.x1 - self.x0 - indent), font, size):
            self.S.text(self.x0 + indent, self.y, line, size, font, color, "l")
            self.y += lead

    def item(self, tag_s, s, color=INK):
        self.S.text(self.x0, self.y, tag_s, 7.2, FB, color, "l")
        self.para(s, indent=5)
        self.y += 1.1


def frame(S, sheet, title):
    S.pline([(FRAME, FRAME), (PAGE_W - FRAME, FRAME), (PAGE_W - FRAME, PAGE_H - FRAME), (FRAME, PAGE_H - FRAME)], INK, 0.4, True)
    S.pline([(PANEL_X, FRAME), (PANEL_X, PAGE_H - FRAME)], INK, 0.25)
    # title block
    x0, x1 = PANEL_X, PAGE_W - FRAME
    y0 = PAGE_H - FRAME - 47
    S.pline([(x0, y0), (x1, y0)], INK, 0.25)
    S.text(x0 + 4, y0 + 6, "APARTMENT, UNIT 13", 11.5, FB, INK, "l")
    S.text(x0 + 4, y0 + 12, title, 8, F, INK, "l")
    y = y0 + 17
    S.pline([(x0, y), (x1, y)], INK, 0.12)
    rows = [("Sheet", sheet, "Scale", "1:50 at A3"), ("Units", "centimetres", "Date", "15 Nov 2026"),
            ("Source", "IMG_0111, IMG_0410", "Status", "For review, rev D")]
    for a, b, c, d in rows:
        y += 4.6
        S.text(x0 + 4, y, a, 5.6, F, GREY, "l")
        S.text(x0 + 15, y, b, 6.8, FB, INK, "l")
        S.text(x0 + 44, y, c, 5.6, F, GREY, "l")
        S.text(x0 + 55, y, d, 6.8, FB, INK, "l")
    y += 4
    S.pline([(x0, y), (x1, y)], INK, 0.12)
    y += 3.6
    S.text(x0 + 4, y, "Redrawn from a photographed screen. Check all dimensions on site.", 5.6, FI, GREY, "l")
    # scale bar, under the plan
    bx, by = 26.0, PAGE_H - FRAME - 9
    for i in range(5):
        S.pline([(bx + i * 20, by), (bx + (i + 1) * 20, by), (bx + (i + 1) * 20, by + 1.6), (bx + i * 20, by + 1.6)],
                INK, 0.15, True, INK if i % 2 == 0 else WHITE)
    for i in range(6):
        S.text(bx + i * 20, by - 2, str(i), 6, F, INK)
    S.text(bx + 104, by + 0.3, "metres, 1:50 at A3", 6, F, GREY, "l")


def panel_furnished(S):
    P = Panel(S)
    P.head("KEY FIGURES")
    S.text(P.x0, P.y + 1.5, f"{NET_INTERIOR:.2f} m²", 16, FB, INK, "l")
    S.text(P.x0 + 39, P.y - 0.2, "net interior floor area", 6.4, F, GREY, "l")
    S.text(P.x0 + 39, P.y + 3, "walls and columns excluded", 6.4, F, GREY, "l")
    P.y += 10
    P.head("ROOM SCHEDULE")
    xs = [P.x0, P.x0 + 30, P.x1]
    al = ["l", "l", "r"]
    P.row(["Room", "Size, cm", "Net area"], xs, 6.4, FB, GREY, al)
    for name, size, key in (
        ("Living + kitchen", "L-shape, less storage", "living"),
        ("Entrance hall", "122×322 + 311×272", "hall"),
        ("Bedroom 1", "402×384, less column", "bed1"),
        ("Bedroom 2", "287×366", "bed2"),
        ("Bathroom 1, en-suite", "287×192", "bath1"),
        ("Bathroom 2", "167×298", "bath2"),
        ("Storage", "177×167", "storage"),
    ):
        P.row([name, size, m2(AREA[key])], xs, aligns=al)
    P.row(["Interior total", "", m2(NET_INTERIOR)], xs, font=FB, aligns=al)
    P.y += 1.4
    P.row(["Balcony B", "145×570", m2(AREA["bal_b"])], xs, aligns=al)
    P.row(["Balcony A", "775×125", m2(AREA["bal_a"])], xs, aligns=al)
    P.row(["Balconies total", "", m2(BALCONIES)], xs, font=FB, aligns=al)
    P.y += 1
    P.para("Balconies are measured to the slab edge. Their rails stand about 10 cm inside it. "
           "Totals use unrounded areas, so they can differ by 0.01 from the rows above. The kitchen "
           "and hall are one open space, split here at the line of the bathroom 2 wall. The "
           "storage is 177 wide because its wall continues the bathroom 2 wall.", 6.8, F, GREY, 3.1)
    P.head("LEGEND")
    samples = [
        (EXT_FILL, "Exterior and party walls, 25 to 30"), (PART_FILL, "Partitions, 12"),
        (LINING_FILL, "Lining behind WC and bidet, 10"), (BLACK, "Structural columns, ~70 × 40"),
    ]
    for fill, s in samples:
        S.pline([(P.x0, P.y - 1.2), (P.x0 + 8, P.y - 1.2), (P.x0 + 8, P.y + 1.2), (P.x0, P.y + 1.2)], INK, 0.2, True, fill)
        S.text(P.x0 + 11, P.y, s, 7.4, F, INK, "l")
        P.y += 4.7
    S.pline([(P.x0, P.y), (P.x0 + 8, P.y)], GLASS, 0.25)
    S.text(P.x0 + 11, P.y, "Glazing, window leaves, shower glass", 7.4, F, INK, "l")
    P.y += 4.7
    S.c.setStrokeColor(INK)
    S.c.setLineWidth(0.13 * mm)
    S.c.setFillColor(WHITE)
    S.c.circle((P.x0 + 4) * mm, (PAGE_H - P.y) * mm, 1.7 * mm, stroke=1, fill=1)
    S.text(P.x0 + 4, P.y, "D", 4.8, FB, INK)
    S.text(P.x0 + 11, P.y, "Door tag, see sheet A-02", 7.4, F, INK, "l")
    P.y += 4.7
    S.pline([(P.x0 + 2.3, P.y - 1.4), (P.x0 + 5.7, P.y - 1.4), (P.x0 + 5.7, P.y + 1.4), (P.x0 + 2.3, P.y + 1.4)], GLASS, 0.13, True, WHITE)
    S.text(P.x0 + 4, P.y, "W", 4.8, FB, GLASS)
    S.text(P.x0 + 11, P.y, "Window tag, see sheet A-02", 7.4, F, INK, "l")
    P.y += 5
    P.head("NOTES")
    for t, s in (
        ("1", "The source labels this apartment 13. The brief said unit 3, and this is the only "
              "complete unit in the photo, with the rooms described."),
        ("2", "Walls come from the printed dimensions. Fixtures and furniture are scaled from the "
              "rectified photo and placed as on the source, except where revisions B and C move them."),
        ("3", "The source gives no north point, ceiling height, or window sill and head heights, "
              "so none is shown."),
        ("4", "Star symbols in the kitchen copy the source. It does not say which appliances they are."),
        ("5", "Balcony A was given as 775 × 125, because the photo cuts it off. Its far rail is "
              "assumed to match Balcony B. Sea view marked on Balcony A."),
        ("6", "Boiler and washer were erased on the sketch, where the new door swings. They are "
              "shown in the corner of bathroom 1 until a position is confirmed."),
    ):
        P.item(t, s)


def panel_dimensioned(S):
    P = Panel(S)
    P.head("OPENING SCHEDULE")
    xs = [P.x0, P.x0 + 8.5, P.x0 + 56, P.x1]
    al = ["l", "l", "r", "r"]
    P.row(["Tag", "Opening", "Width", "Basis"], xs, 6.4, FB, GREY, al)
    for row in (
        ("D0", "Entrance door", "~100", "scaled"),
        ("D1", "Bedroom 1 door", "90", "printed"),
        ("D2", "Bathroom 1 door, from bedroom 1", "80", "moved"),
        ("D3", "Bedroom 2 door", "90", "printed"),
        ("D4", "Bathroom 2 door", "80", "printed"),
        ("D5", "Storage door, from the corridor", "~80", "moved"),
        ("W1", "Double door to Balcony A, 2 leaves", "~300", "scaled"),
        ("W2", "Living room, 2 leaves + rail", "~150", "scaled"),
        ("W3", "Bedroom 1, 2 leaves + rail", "~150", "scaled"),
        ("W4", "Bathroom 1, in shower zone", "~80", "scaled"),
        ("W5", "Bedroom 2 to Balcony B, 2 leaves", "~150", "scaled"),
    ):
        P.row(list(row), xs, 7, aligns=al, gap=4.1)
    P.y += 1
    P.para("Black figures are printed on the source, or supplied for Balcony A. Blue ~ figures are scaled from the rectified "
           "photo (fit within 1.2 cm) or derived.", 6.8, F, GREY, 3.1)
    P.head("CLOSURE CHECKS, ALL EXACT")
    xs2 = [P.x0, P.x1]
    for name, a, b in CHECKS:
        P.row([name, f"{a} = {b}"], xs2, 6.5, aligns=["l", "r"], gap=3.8)
    P.head("REVISION B, FROM SKETCH IMG_0410")
    P.item("a", "Bathroom 1 door moved from the hall to bedroom 1, so it is now en-suite. The hall "
                "opening is closed.", GLASS)
    P.item("b", "New storage at the end of the kitchen, 177 × 167 clear, with its door in the "
                "kitchen. The 34 × 200 element is removed.", GLASS)
    P.item("c", "Bedroom 1 wardrobe cut from 207 to 87 to reach the new door.", GLASS)
    P.item("d", "Boiler and washer moved to the far corner of bathroom 1.", GLASS)
    P.head("REVISION C, CLIENT CORRECTION")
    P.item("a", "Kitchen keeps its full 510 run and unit order. It moves 179 along the wall toward "
                "Balcony A, ending at the storage. This replaces the 330 run of revision B.", GLASS)
    P.item("b", "Dining table moved between the kitchen and the living room, long side parallel "
                "to W1.", GLASS)
    P.head("REVISION D, CLIENT CORRECTION")
    P.item("a", "Storage door moved from the kitchen to the corridor, in the bathroom 2 wall line "
                "like D4. It opens in. The kitchen side of the storage is now a closed wall.", GLASS)
    P.head("SOURCE CORRECTIONS")
    P.item("A", "Left wall run: a line crosses the middle digit, so it can read as 706. It is 766: "
                "the left chain only closes to 1360 with 766, and the wall measures 767 on the photo.", FLAG)
    P.item("B", "122 + 12 + 167 leaves 10 of the 311. That 10 is a lining behind the WC and bidet "
                "of bathroom 2, drawn on the source but not dimensioned.", FLAG)
    P.item("C", "Balcony A depth is cut off by the photo, so 775 × 125 was supplied separately. "
                "The 775 agrees with the ~776 scaled from the photo.", FLAG)
    P.head("ARCHITECT'S REVIEW")
    for t, s in (
        ("1", "Bathroom 1: the bidet (x 493 to 533) crosses the lower shower glass (x 528) by 5. "
              "Move WC and bidet 10 to the left."),
        ("2", "Bathroom 2 has no window and the hob is about 4.7 m from the facade. No shaft is "
              "drawn: confirm extract routes."),
        ("3", "W1 leaves are 150 wide. The left leaf now swings clear, but the side table stops "
              "the right one at about 58°. Sliding doors would solve it and open up the sea view."),
        ("4", "The main sofa sits with its back to Balcony A, so nobody seated there faces the sea."),
        ("5", "W5: the bedside table sits in the sweep of the upper leaf, and W5 is the only way "
              "onto Balcony B, so bedroom 2 is the passage to it."),
        ("6", "W4 opens inside the shower: specify a water-resistant frame and privacy glass, as "
              "it faces Balcony B."),
        ("7", "The washer can now only be reached through bedroom 1. The storage backs onto "
              "bathroom 2 and would serve everyone better, if a gas boiler can be flued there."),
        ("8", "Bedroom 1 loses 120 of wardrobe. Plan replacement storage."),
        ("9", "With D0 fully open, its leaf parks 10 from the closet, blocking 2 of 3 modules."),
        ("10", "The table leaves 88 to the kitchen and 88 to the seating. Its corner chair is 57 "
               "from the bedroom 1 wall corner, less once pulled out, which pinches the way to the sofa."),
        ("11", "The moved kitchen leaves 77 of wall at the balcony end, room for a fridge or tall unit."),
    ):
        P.item(t, s)


def build():
    pdf_path = OUT / f"{STEM}.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.setTitle("Apartment Unit 13 - Floor plan")
    c.setSubject("Floor plan redrawn from photographed source, 1:50 at A3")
    c.setAuthor("")

    doc = ezdxf.new("R2018", setup=False)
    doc.header["$INSUNITS"] = 5
    for name, color in DXF_LAYERS.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    S = Sheet(c, msp)
    sheet_furnished(S)
    S.msp = None
    dims_overview(S)
    frame(S, "A-01", "Floor plan, furnished")
    panel_furnished(S)
    c.showPage()

    S2 = Sheet(c, None)
    sheet_dimensioned(S2)
    S2.msp = msp
    dims_full(S2)
    S2.msp = None
    frame(S2, "A-02", "Floor plan, dimensioned, with review")
    panel_dimensioned(S2)
    c.showPage()
    c.save()
    doc.saveas(OUT / f"{STEM}.dxf")

    pdf = pypdfium2.PdfDocument(str(pdf_path))
    for i, name in enumerate(("A01", "A02")):
        pdf[i].render(scale=300 / 72).to_pil().save(OUT / f"{STEM}_{name}.png", optimize=True)
    pdf.close()
    print("net interior m2:", round(NET_INTERIOR, 2), {k: round(v, 2) for k, v in AREA.items()})


if __name__ == "__main__":
    build()
