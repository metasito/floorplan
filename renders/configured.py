"""Build the apartment from a configuration (catalog.py format) instead of the fixed scheme.

Every movable piece is built at the origin, facing down the sheet, then parented to an empty
placed at the item's x, y, z and rotation, so any item can be moved, turned or swapped. Fixed
parts (walls, doors, windows, kitchen run, showers, storage shelving, downlights) follow the
finishes. With export=True every material is a plain placeholder named for its role or slot,
which the browser editor recolours; with export=False the real Cycles materials are used.
"""
import copy
import math

import bmesh
import bpy
from mathutils import Matrix

import design as D
import kit
from catalog import KINDS, METALS, WOODS
from kit import DOOR_H, H, HEAD, SC, P, ball, box, boxes, color, cube_uv, curtain, cyl, group, link, soft, tube

GEN = D.GEN
R = SC["room_bounds"]


# ---------------------------------------------------------------- materials
class Mats(D.M):
    """The scheme's materials with the finishes applied, plus per-slot materials for items."""

    def __init__(self, fin, export=False):
        self.export = export
        self._c = {}
        super().__init__()
        self.fin = fin
        if export:
            self._placeholders()
            return
        w = fin["walls"]
        self.room_walls = {k: D.paint(f"wall {k}", w[k], mottle=0.03) for k in w}
        self.room_walls["bath1"] = D.paint("bath1 paint", w["bath1"], rough=0.7, bump=0.15)
        self.room_walls["bath2"] = D.paint("bath2 paint", w["bath2"], rough=0.7, bump=0.15)
        a = fin["accents"]
        self.clay = D.paint("living accent", a["living_tv"]["color"], rough=0.92, bump=0.45, mottle=0.09,
                            tex="white_stucco", tile=2.0) if a["living_tv"]["on"] else self.room_walls["living"]
        self.sage = D.paint("bed accent", a["bed1_head"]["color"], rough=0.92, bump=0.45, mottle=0.08,
                            tex="white_stucco", tile=2.0) if a["bed1_head"]["on"] else self.room_walls["bed1"]
        self.clay2 = D.paint("band", a["bed2_band"]["color"], rough=0.9, bump=0.3, mottle=0.05) \
            if a["bed2_band"]["on"] else self.room_walls["bed2"]
        self.ceiling = D.paint("ceiling", fin["ceiling"], rough=0.95, bump=0.1)
        self.skirt = color("skirting", D.srgb(fin["skirting"]), 0.45)
        self.door = color("door paint", D.srgb(fin["doors"]), 0.4)
        self.frame = color("window frames", D.srgb(fin["frames"]), 0.45, 0.3)
        self.handle = self.metal(fin["door_handles"])
        self.floor = self.floor_mat(fin["floor"])
        self.tiles = {b: D.zellige(f"tiles {b}", fin[b]["tiles"], 10) for b in ("bath1", "bath2")}
        self.bath_floors = {b: self.bath_floor_mat(fin[b]["floor"]) for b in ("bath1", "bath2")}
        self.fittings = {b: self.metal(fin[b]["fittings"]) for b in ("bath1", "bath2")}
        self.terracotta = self.balcony_mat(fin["balconies"])
        k = fin["kitchen"]
        self.sage_front = D.paint("kitchen fronts", k["fronts"], rough=0.55, bump=0.05)
        self.k_upper = color("kitchen uppers", D.srgb(k["upper_color"]), 0.5)
        self.worktop = self.worktop_mat(k["worktop"])
        self.splash = D.zellige("splashback", k["splash"], 7.5, var=0.08)
        self.k_handle = {"brass knobs": self.brass, "black bars": self.black, "oak knobs": self.oak,
                         "handleless": self.black}[k["handles"]]

    def _placeholders(self):
        def ph(name, rgb=(0.8, 0.8, 0.8)):
            return color(name, rgb, 0.6)
        self.room_walls = {k: ph(f"wall:{k}") for k in ("living", "hall", "storage", "bed1", "bed2", "bath1", "bath2")}
        self.clay, self.sage, self.clay2 = ph("accent:living_tv"), ph("accent:bed1_head"), ph("accent:bed2_band")
        self.ceiling, self.skirt, self.door, self.frame = ph("ceiling"), ph("skirting"), ph("doors"), ph("frames")
        self.handle = ph("door_handles")
        self.floor = ph("floor:main")
        self.tiles = {b: ph(f"tiles:{b}") for b in ("bath1", "bath2")}
        self.bath_floors = {b: ph(f"bathfloor:{b}") for b in ("bath1", "bath2")}
        self.fittings = {b: ph(f"fittings:{b}") for b in ("bath1", "bath2")}
        self.terracotta = ph("floor:balcony")
        self.sage_front, self.k_upper = ph("kitchen:fronts"), ph("kitchen:uppers")
        self.worktop, self.splash, self.k_handle = ph("kitchen:worktop"), ph("kitchen:splash"), ph("kitchen:handles")
        self.facade = ph("facade")
        self.glass = ph("glass")
        self.clear = ph("clear glass")

    # finishes
    def floor_mat(self, name):
        return {"light oak": lambda: self.floor,
                "natural oak": lambda: D.pbr("natural oak floor", "laminate_floor_02", sat=0.85, hue=0.51, val=0.9, rot=90),
                "oak herringbone": lambda: D.pbr("herringbone", "herringbone_parquet", sat=0.7, val=1.15, hue=0.51),
                "light terrazzo": lambda: D.pbr("terrazzo floor", "terrazzo_tiles", sat=0.5, val=1.25, rough_mul=0.7),
                "polished concrete": lambda: D.pbr("concrete floor", "smooth_concrete_floor", sat=0.4, val=1.25,
                                                   rough_mul=0.6)}[name]()

    def bath_floor_mat(self, name):
        return {"terrazzo": lambda: self.bath_floor,
                "stone": lambda: D.pbr("stone floor", "large_grey_tiles", sat=0.35, val=1.3, tint=D.srgb("#efe6d8")),
                "light tile": lambda: D.pbr("light tile", "interior_tiles", sat=0.3, val=1.1)}[name]()

    def balcony_mat(self, name):
        return {"terracotta": lambda: self.terracotta,
                "grey stone": lambda: D.pbr("balcony stone", "large_grey_tiles", sat=0.4, val=1.15),
                "wood decking": lambda: D.pbr("decking", "wood_floor_worn", sat=0.8, val=0.9, rot=90)}[name]()

    def worktop_mat(self, name):
        return {"oak": lambda: self.worktop,
                "white quartz": lambda: color("white quartz", D.srgb("#ece9e3"), 0.22, coat=0.3),
                "terrazzo": lambda: D.pbr("terrazzo top", "terrazzo_tiles", sat=0.5, val=1.2, rough_mul=0.5),
                "concrete": lambda: D.pbr("concrete top", "brushed_concrete", sat=0.4, val=1.2)}[name]()

    # items
    def _get(self, key, fn):
        if key not in self._c:
            self._c[key] = fn()
        return self._c[key]

    def wood(self, name):
        def make():
            if name == "light oak":
                return self.oak
            if name == "natural oak":
                return D.pbr("natural oak", "oak_veneer_05", tile=1.0, sat=0.85, val=0.82, hue=0.51)
            if name == "smoked oak":
                return self.oak_dark
            if name == "walnut":
                return D.pbr("walnut", "american_walnut_veneer", tile=1.0, sat=0.8, val=1.0)
            return color(f"{name} lacquer", D.srgb(WOODS[name]), 0.45)
        return self._get(("wood", name), make)

    def metal(self, name):
        def make():
            rough = {"brushed brass": 0.32, "matt black": 0.5, "chrome": 0.06, "brushed steel": 0.3}[name]
            return color(name, D.srgb(METALS[name]), rough, 0.0 if name == "matt black" else 1.0)
        return self._get(("metal", name), make)

    def fabric_c(self, hexc, tex="rough_linen", tile=0.22):
        return self._get(("fabric", hexc, tex), lambda: D.fabric(f"fabric {hexc}", tex, hexc, tile=tile, normal=2.0))

    def paint_c(self, hexc):
        return self._get(("paint", hexc), lambda: color(f"paint {hexc}", D.srgb(hexc), 0.5))

    def slot(self, it, name):
        """The material for an item's slot, from its value or the kind's default."""
        typ, default = KINDS[it["kind"]]["slots"][name]
        val = (it.get("slots") or {}).get(name, default)
        if self.export:
            return self._get(("slot", name), lambda: color(f"slot:{name}", (0.8, 0.8, 0.8), 0.6))
        return {"fabric": self.fabric_c, "paint": self.paint_c, "wood": self.wood, "metal": self.metal}[typ](val)

    def shade_c(self, hexc):
        if self.export:
            return self._get(("shade-ph",), lambda: color("slot:shade", (0.95, 0.93, 0.9), 0.8))
        return self._get(("shade", hexc), lambda: D.shade_mat(f"shade {hexc}", hexc))


def with_mats(m, **kw):
    mm = copy.copy(m)
    for k, v in kw.items():
        setattr(mm, k, v)
    return mm


# ---------------------------------------------------------------- shell
def wall_material(m, room, nx, ny, x, y, z):
    if room is None:
        return m.facade if D.exterior(x, y) else m.room_walls["living"]
    if room in ("bath1", "bath2"):
        shower = (x >= 524) if room == "bath1" else (y <= 857)
        return m.tiles[room] if (z < 120 or shower) else m.room_walls[room]
    if room == "bed1" and ny > 0.9 and y < 400:
        return m.sage
    if room == "living" and ny < -0.9 and 370 < y < 383 and x > 311:
        return m.clay
    if room == "bed2" and z < 105:
        return m.clay2
    return m.room_walls[room]


def build_shell(m):
    D.wall_material = wall_material                      # build_walls looks it up at call time
    W1, W2, W3, W4, W5 = SC["w1"], SC["w2"], SC["w3"], SC["w4"], SC["w5"]
    LW, XL, XLO = SC["living_w"], SC["x_lower"], SC["x_lower_out"]
    walls = [(*bb[:2], 0, *bb[2:], H) for bb in SC["walls"]]
    walls += [(W1[0], -25, HEAD, W1[1], 0, H), (LW, W2[0], HEAD, 750, W2[1], H), (LW, W3[0], HEAD, 750, W3[1], H),
              (XL, W5[0], HEAD, XLO, W5[1], H), (XL, W4[0], 0, XLO, W4[1], 115), (XL, W4[0], 215, XLO, W4[1], H)]
    for d in SC["doors"].values():
        a, b = d["wall"]
        s0, s1 = d["span"]
        walls.append((a, s0, DOOR_H, b, s1, H) if d["axis"] == "x" else (s0, a, DOOR_H, s1, b, H))
    D.build_walls(m, walls)
    dry, wet, sills = [], {"bath1": [], "bath2": []}, []
    for k in ("living", "hall", "storage", "bed1", "bed2"):
        dry += [(x0, y0, -4, x1, y1, 0) for x0, y0, x1, y1 in SC["rooms"][k]]
    for k in ("bath1", "bath2"):
        wet[k] += [(x0, y0, -4, x1, y1, 0) for x0, y0, x1, y1 in SC["rooms"][k]]
    for tag, d in SC["doors"].items():
        a, b = d["wall"]
        s0, s1 = d["span"]
        bx = (a, s0, -4, b, s1, 0) if d["axis"] == "x" else (s0, a, -4, s1, b, 0)
        if tag == "D2":
            wet["bath1"].append(bx)
        elif tag == "D4":
            wet["bath2"].append(bx)
        elif tag == "D0":
            sills.append(bx)
        else:
            dry.append(bx)
    boxes("floor oak", dry, m.floor)
    for k, items in wet.items():
        boxes(f"floor {k}", items, m.bath_floors[k])
    sills += [(W1[0], -25, -4, W1[1], 0, 0.5), (LW, W2[0], -4, 750, W2[1], 0.5), (LW, W3[0], -4, 750, W3[1], 0.5),
              (XL, W5[0], -4, XLO, W5[1], 0.5), (XL - 2, W4[0], 113, XLO, W4[1], 115.5)]
    boxes("sills", sills, m.stone, 0.2)
    box("slab", -56, -150, -30, 780, 1390, -4, color("slab", (0.5, 0.5, 0.5), 0.8))
    box("ceiling", -56, -150, H, 780, 1390, H + 30, m.ceiling)
    bx0, by0, bx1, by1 = SC["bal_a"]
    boxes("balcony tiles", [(bx0, by0, -6, bx1, by1, -2), (XLO, 790, -6, 780, 1360, -2), (750, 780, -6, 780, 790, -2)],
          m.terracotta)
    rg = m.clear
    boxes("rail glass", [(bx0, by0 + 7.4, -2, bx1 - 8, by0 + 8.6, 104), (bx1 - 8.6, by0 + 8, -2, bx1 - 7.4, by1, 104),
                         (772.4, 788, -2, 773.6, 1360, 104), (750, 784.4, -2, 773, 785.6, 104)], rg)
    boxes("rail top", [(bx0, by0 + 6, 104, bx1 - 6, by0 + 10, 107), (bx1 - 10, by0 + 6, 104, bx1 - 6, by1, 107),
                       (771, 783, 104, 775, 1360, 107), (750, 783, 104, 775, 787, 107)], m.frame, 0.3)
    for y0, y1 in ((W2[0] - 13, W2[1] + 13), (W3[0] - 13, W3[1] + 13)):
        box("juliet glass", 755.4, y0, 2, 756.6, y1, 104, rg)
        box("juliet rail", 754, y0, 104, 758, y1, 107, m.frame, 0.3)
    D.window(m, "y", W1[0], W1[1], -25, 0)
    D.window(m, "x", W2[0], W2[1], LW, 750)
    D.window(m, "x", W3[0], W3[1], LW, 750)
    D.window(m, "x", W4[0], W4[1], XL, XLO, leaves=1, sill=115, head=215, glass=m.frosted)
    D.window(m, "x", W5[0], W5[1], XL, XLO)
    items, t = [], 1.3
    for segs in SC["skirting"].values():
        for x0, y0, x1, y1 in segs:
            if abs(y1 - y0) < 0.01:
                items.append((min(x0, x1), y0 - t, 0, max(x0, x1), y0 + t, 8))
            else:
                items.append((x0 - t, min(y0, y1), 0, x0 + t, max(y0, y1), 8))
    boxes("skirting", items, m.skirt, 0.15)
    if not m.export:
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=45000, matrix=Matrix.Translation((0, 0, -18)))
        cube_uv(bm)
        link(D._finish("sea", bm, D.sea_mat()))
    hm = with_mats(m, black=m.handle, brass=m.handle)
    for tag in SC["doors"]:
        D.door(hm, tag, D.DOOR_OPEN[tag])


CURTAINS = {   # window: (curtain segments, track box)
    "W1": ([((96, 6), (142, 6)), ((446, 6), (520, 6))], (90, 2, 525, 9)),
    "W2": ([((717, 48), (717, 93)), ((717, 247), (717, 300))], (713, 44, 721, 304)),
    "W3": ([((717, 432), (717, 468)), ((717, 622), (717, 660))], (713, 428, 721, 664)),
    "W5": ([((603, 1062), (603, 1098)), ((603, 1262), (603, 1298))], (599, 1058, 607, 1302)),
}


def curtains(m):
    for w, (segs, (x0, y0, x1, y1)) in CURTAINS.items():
        c = m.fin["curtains"][w]
        if not c["on"]:
            continue
        if m.export:
            mat = color(f"curtain:{w}", (0.9, 0.88, 0.84), 0.8)
        elif c["style"] == "sheer":
            mat = kit.sheer_mat(f"sheer {w}", D.srgb(c["color"]), 0.62)
        else:
            mat = D.fabric(f"curtain {w}", "rough_linen", c["color"], tile=0.25, sheen=0.4)
        for a, b in segs:
            curtain(a, b, mat, z0=1, z1=H - 4, pleats=8, amp=4 if c["style"] == "linen" else 3.5)
        box(f"curtain track {w}", x0, y0, H - 3, x1, y1, H, m.cab_white)


def kitchen(m):
    """The 5.1 m run on the left wall (revision C), with the finishes' fronts, uppers, worktop,
    splashback and handles."""
    k = SC["kitchen_shift"]
    kf = m.fin["kitchen"]
    start, end = 256 - k, 766 - k
    y_tall = start + 60
    zt = 92
    box("plinth", 0, start, 0, 54, end, 10, m.black)
    box("carcass", 0, y_tall, 10, 58, end, 88, m.carcass)
    fronts, knobs = [], []

    def front(y0, y1, z0, z1, x=58):
        fronts.append((x, y0 + 0.2, z0 + 0.2, x + 1.9, y1 - 0.2, z1 - 0.2))

    for y0, y1, kind in [(137, 197, "door"), (197, 257, "drawers"), (257, 321, "door"), (321, 407, "sink"),
                         (407, 467, "door"), (467, 527, "oven"), (527, 587, "drawers")]:
        if kind == "door":
            front(y0, y1, 10, 88)
            knobs.append((y1 - 5 if y0 < 300 else y0 + 5, 80, "v"))
        elif kind == "sink":
            mid = (y0 + y1) / 2
            front(y0, mid, 10, 88)
            front(mid, y1, 10, 88)
            knobs += [(mid - 4, 80, "v"), (mid + 4, 80, "v")]
        elif kind == "drawers":
            for a, b in ((10, 32), (32, 60), (60, 88)):
                front(y0, y1, a, b)
                knobs.append(((y0 + y1) / 2, b - 6, "h"))
        else:
            front(y0, y1, 10, 28)
            knobs.append(((y0 + y1) / 2, 22, "h"))
            box("oven", 58, y0 + 0.3, 28.3, 60, y1 - 0.3, 87.7, color("oven glass", (0.015, 0.015, 0.016), 0.06, coat=1), 0.1)
            box("oven handle", 60.5, y0 + 6, 80, 63, y1 - 6, 81.5, m.steel, 0.3)
    for a, b in ((10, 92), (92, 196), (196, 236)):
        front(start, y_tall, a, b)
    knobs += [(y_tall - 5, 100, "v"), (y_tall - 5, 85, "v"), (y_tall - 5, 202, "v")]
    box("tall carcass", 0, start, 10, 58, y_tall, 236, m.carcass)
    box("fridge end panel", 0, start - 2, 0, 60, start, 236, m.sage_front, 0.2)
    boxes("fronts", fronts, m.sage_front, 0.1)

    def handle(x, y, z, orient):
        style = kf["handles"]
        if style == "handleless":
            return
        if style in ("brass knobs", "oak knobs"):
            ball("knob", x + 1.6, y, z, 1.6, m.k_handle)
        elif orient == "h":
            box("bar", x, y - 9, z - 0.6, x + 2.4, y + 9, z + 0.6, m.k_handle, 0.3)
        else:
            box("bar", x, y - 0.6, z - 9, x + 2.4, y + 0.6, z + 9, m.k_handle, 0.3)
    for y, z, o in knobs:
        handle(59.8, y, z, o)
    sx0, sy0, sx1, sy1 = 10, 330, 50, 398
    boxes("worktop", [(0, y_tall, 88, 62, sy0, zt), (0, sy1, 88, 62, end, zt), (0, sy0, 88, sx0, sy1, zt),
                      (sx1, sy0, 88, 62, sy1, zt)], m.worktop, 0.2)
    box("splashback", 0, y_tall, zt, 1.2, end, 152, m.splash)
    d = 70
    boxes("sink", [(sx0, sy0, d, sx1, sy1, d + 1.5), (sx0, sy0, d, sx0 + 1.5, sy1, zt + 0.4),
                   (sx1 - 1.5, sy0, d, sx1, sy1, zt + 0.4), (sx0, sy0, d, sx1, sy0 + 1.5, zt + 0.4),
                   (sx0, sy1 - 1.5, d, sx1, sy1, zt + 0.4)], m.ceramic, 0.3)
    ty = (sy0 + sy1) / 2
    tap = m.k_handle if kf["handles"] != "oak knobs" else m.brass
    cyl("tap base", 5, ty, zt, zt + 4, 2.4, mat=tap)
    arc = [(5, ty, zt + 3), (5, ty, zt + 27)]
    for i in range(1, 13):
        t = math.pi * i / 12
        arc.append((14 - 9 * math.cos(t), ty, zt + 27 + 9 * math.sin(t)))
    arc.append((23, ty, zt + 23))
    tube("tap", arc, 1.0, tap)
    hy0, hy1 = 649 - k, 705 - k
    box("hob", 5, hy0, zt, 56, hy1, zt + 0.5, color("hob glass", (0.012, 0.012, 0.014), 0.05, coat=1), 0.1)
    z0, z1 = 152, 236
    uppers = kf["uppers"]
    cup_spans = {"cupboards and shelves": ((137, 197), (197, 257), (257, 321)),
                 "cupboards": ((137, 197), (197, 257), (257, 321), (321, 393), (393, 464), (532, 585)),
                 "open shelves": (), "none": ()}[uppers]
    up, upf = [], []
    for a, b in cup_spans:
        up.append((0, a, z0, 34, b, z1))
        upf.append((34, a + 0.2, z0 + 0.2, 35.8, b - 0.2, z1 - 0.2))
        handle(35.8, b - 5 if a < 250 else a + 5, z0 + 6, "v")
    if up:
        boxes("upper carcass", up, m.carcass)
        boxes("upper fronts", upf, m.k_upper, 0.1)
        D.area(24, 229, z0 - 0.8, 16, 176, 22, 2900, role="strip")
    shelves = []
    if uppers == "cupboards and shelves":
        shelves = [(0, 324, 160, 26, 464, 164), (0, 324, 198, 26, 464, 202), (0, 532, 160, 26, 585, 164)]
    elif uppers == "open shelves":
        shelves = [(0, 137, 160, 26, 464, 164), (0, 137, 198, 26, 464, 202), (0, 532, 160, 26, 585, 164)]
    if shelves:
        boxes("open shelves", shelves, m.oak, 0.2)
        D.area(13, (shelves[0][1] + shelves[0][4]) / 2, 159, 16, shelves[0][4] - shelves[0][1] - 4, 14, 2900, role="strip")
    if uppers != "none":
        box("hood", 0, hy0 - 4, 156, 48, hy1 + 4, H, m.room_walls["living"], 0.4)
        box("hood ledge", 0, hy0 - 6, 156, 50, hy1 + 6, 160, m.oak, 0.3)
    else:
        box("hood", 0, hy0 - 2, 175, 45, hy1 + 2, 182, m.steel, 0.3)
        box("hood flue", 0, hy0 + 18, 182, 22, hy1 - 18, H, m.steel, 0.3)
    for x, y in ((48, 180), (48, 400)):
        D.downlight(m, x, y, 8)


def kitchen_styling(m):
    zt = 92
    if m.fin["kitchen"]["uppers"] in ("cupboards and shelves", "open shelves"):
        D.plant("ceramic_vase_02", 12, 335, 164, h=18)
        D.plant("ceramic_vase_04", 11, 358, 164, h=22)
        D.plant("wooden_bowl_02", 12, 420, 164, w=24)
        D.book_row(3, 440, 164, 22, "y", m.books, seed=5)
        D.plant("ceramic_vase_01", 13, 350, 202, h=19)
    D.plant("wine_bottles_01", 14, 170, zt, h=31)
    D.plant("wooden_cutting_board", 6, 220, zt, w=38, face="e")
    D.plant("potted_plant_04", 16, 298, zt, h=26)
    D.plant("wooden_bowl_01", 32, 440, zt, w=28)
    for dx, dy in ((0, 0), (5, 4), (-4, 5), (2, -5)):
        D.plant("lemon", 32 + dx, 440 + dy, zt + 3, w=7)
    cyl("salt jar", 10, 556, zt, zt + 11, 4.5, mat=m.glaze)
    D.plant("planter_pot_clay", 22, 568, zt, h=14)


def bathrooms_fixed(m):
    """Showers, drains, niches and downlights: plumbed or wired, so they stay put."""
    b1, b2 = R["bath1"], R["bath2"]
    f1, f2 = m.fittings["bath1"], m.fittings["bath2"]
    box("shower glass", 523.5, b1[1], 0, 524.5, 893, 200, m.clear)
    box("shower glass", 527.5, 889, 0, 528.5, b1[3], 200, m.clear)
    boxes("glass profile", [(523, b1[1], 0, 525, b1[1] + 2, 200), (527, b1[3] - 2, 0, 529, b1[3], 200),
                            (523, b1[1], 199, 529, b1[3], 200.5)], f1)
    box("drain", 529, 797, -0.2, 588, 802, 0.05, m.steel)
    D.shower(with_mats(m, brass=f1), b1[2], 850, 210, (-1, 0))
    box("niche shelf", 560, 972, 120, 600, 982, 121.5, m.stone)
    box("shower glass", b2[0], 851.5, 0, 112, 852.5, 200, m.clear)
    box("shower glass", 97, 856.5, 0, b2[2], 857.5, 200, m.clear)
    box("glass rail", b2[0], 851, 199, b2[2], 858, 200.5, f2)
    box("drain", 16, 788, -0.2, 21, 847, 0.05, m.steel)
    D.shower(with_mats(m, brass=f2), 93, b2[1], 210, (0, 1))
    box("niche shelf", 138, b2[1], 120, 174, b2[1] + 10, 121.5, m.stone)
    if not m.export:
        cyl("bottle", 572, 977, 121.5, 141.5, 2.8, mat=color("amber bottle", D.srgb("#8a5a2b"), 0.1, coat=1))
        cyl("bottle", 150, b2[1] + 5, 121.5, 141, 2.8, mat=color("amber bottle", D.srgb("#8a5a2b"), 0.1, coat=1))
    for x, y in ((400, 860), (566, 850), (566, 930), (93, 815), (93, 960), (93, 1050)):
        D.downlight(m, x, y, 7)


def fixed_lights(m):
    for x, y in ((120, 470), (250, 470), (250, 640), (250, 120), (250, 830), (250, 1000), (120, 1225), (250, 1225)):
        D.downlight(m, x, y, 8)
    for x in (100, 400, 650):
        box("wall light", x - 6, -32, 205, x + 6, -25, 222, m.black, 0.5)
        D.point(x, -36, 212, 12, 2700, 3, "outdoor")
    box("wall light", 635, 1179, 205, 642, 1191, 222, m.black, 0.5)
    D.point(646, 1185, 212, 10, 2700, 3, "outdoor")


# ---------------------------------------------------------------- items, built at the origin facing down the sheet
def vdata(it):
    return KINDS[it["kind"]]["variants"][it["variant"]]


def size(it, default):
    return it.get("size") or KINDS[it["kind"]].get("size") or default


def b_sofa(m, it):
    w, d, n = vdata(it)
    D.sofa(m, 0, 0, w, d, "s", m.slot(it, "fabric"), m.slot(it, "legs"), n=n)


def b_lounge(m, it):
    D.plant(vdata(it), 0, 0, 0, d=80)


def b_cushion(m, it):
    D.pillow(0, 0, 0, "s", m.slot(it, "fabric"), size=vdata(it))


def b_throw(m, it):
    w, d = vdata(it)
    D.throw(0, 0, 0, w, d, "s", m.slot(it, "fabric"), 4)


def b_coffee(m, it):
    wd = m.slot(it, "wood")
    v = vdata(it)
    if v == "oval":
        D.prism("coffee top", D.rrect(-52, -32, 52, 32, 28, 10), 36, 40, wd, 0.4)
        D.prism("coffee base", D.rrect(-40, -22, 40, 22, 20, 10), 1.2, 36, wd, 0.3)
    elif v == "round":
        D.disc("coffee top", 0, 0, 36, 40, 45, 45, wd, 48, 0.4)
        cyl("coffee base", 0, 0, 0, 36, 24, mat=wd)
    else:
        box("coffee top", -55, -30, 36, 55, 30, 40, wd, 0.4)
        for x in (-49, 49):
            for y in (-24, 24):
                D.leg(x, y, 0, 36, 2.0, 2.4, wd)
        box("coffee shelf", -50, -25, 10, 50, 25, 12, wd, 0.2)


def b_side(m, it):
    wd = m.slot(it, "wood")
    if vdata(it) == "round":
        D.disc("side table", 0, 0, 0, 52, 24, 24, wd, 40, 0.3)
    else:
        box("side top", -22, -22, 50, 22, 22, 53, wd, 0.3)
        box("side shelf", -20, -20, 18, 20, 20, 20, wd, 0.2)
        for x in (-19, 19):
            for y in (-19, 19):
                D.leg(x, y, 0, 50, 1.4, 1.6, wd)


def b_media(m, it):
    w, cane = vdata(it)
    wd = m.slot(it, "wood")
    box("media carcass", -w / 2, -17, 12, w / 2, 17.5, 50, wd, 0.3)
    n = max(2, round(w / 70))
    for i in range(n):
        a = -w / 2 + 2 + i * (w - 4) / n
        b = a + (w - 4) / n
        box("front", a + 0.6, 17.5, 14, b - 0.6, 18.3, 48, m.cane if cane else wd, 0.15)
    for x in (-w / 2 + 8, w / 2 - 8):
        for y in (-11, 11):
            D.leg(x, y, 0, 12, 1.6, 2.2, wd)


def b_tv(m, it):
    w = vdata(it)
    box("tv", -w / 2, -1.75, 0, w / 2, 1.75, w * 0.58, m.tv, 0.3)
    box("tv stand", -7, -7, -4, 7, 7, 0, m.black, 0.2)


def b_floor_lamp(m, it):
    shade = m.shade_c((it.get("slots") or {}).get("shade", "#efe4d2"))
    D.floor_lamp(with_mats(m, oak=m.slot(it, "wood"), shade=shade), 0, 0, watts=30)


def b_table_lamp(m, it):
    mm = with_mats(m, shade=m.shade_c((it.get("slots") or {}).get("shade", "#efe4d2")))
    v = vdata(it)
    D.table_lamp(mm, 0, 0, 0, v, m.slot(it, "base"), watts=22 if v == "ball" else 20)


def b_pendant(m, it):
    """Pendants hang from the ceiling: built in place, the item's z is the shade's lowest point."""
    v, z = vdata(it), it["z"]
    if v == "dome":
        D.pendant_rattan(m, 0, 0, z, rx=19, rz=15, watts=35)
    elif v == "dome_l":
        D.pendant_rattan(m, 0, 0, z, rx=28, rz=16, watts=45)
    elif v == "globe":
        D.pendant_rattan(m, 0, 0, z, rx=22, rz=20, watts=40, shape="globe")
    elif v == "paper":
        D.pendant_paper(m, 0, 0, z, r=24, watts=35)
    else:
        opal = m._get(("opal",), lambda: D.shade_mat("opal glass", "#f6f3ee"))
        ball("opal globe", 0, 0, z + 15, 15, opal)
        tube("cable", [(0, 0, z + 29), (0, 0, H)], 0.3, m.black)
        cyl("canopy", 0, 0, H - 2, H, 5, mat=m.cab_white)
        D.point(0, 0, z + 15, 30, 2700, 5, "pendant")


def b_rug(m, it):
    w, d = size(it, (200, 300))
    v = vdata(it)
    x0, y0, x1, y1 = -w / 2, -d / 2, w / 2, d / 2
    if m.export:
        mat = m._get(("rug", v), lambda: color(f"rug:{v}", (0.8, 0.75, 0.68), 0.9))
    elif v == "jute":
        mat = m.jute
    elif v == "berber":
        mat = D.rug_pic(f"berber {it['id']}", GEN / "rug_berber.png", x0, y0, x1, y1)
    elif v == "stripes":
        mat = D.rug_pic(f"stripes {it['id']}", GEN / "rug_stripes.png", x0, y0, x1, y1)
    else:
        mat = m.fabric_c((it.get("slots") or {}).get("fabric", "#efeae1"), "curly_teddy_natural", 0.2)
    D.rug(x0, y0, x1, y1, mat, t=1.2)


def b_art(m, it):
    w, h = size(it, (50, 70))
    D.art(m, 0, 0, 0, w, h, "s", GEN / f"{vdata(it)}.png", m.slot(it, "frame"))


def b_mirror(m, it):
    shape, r = vdata(it)
    fr = m.slot(it, "frame")
    if shape == "round":
        D.mirror_round(m, 0, 0, 0, r, "s", fr)
        top = r
    else:
        box("mirror", -43, 0.5, -39, 43, 2.5, 39, m.mirror, 0.4)
        box("mirror frame", -45, 0.3, -41, 45, 2.0, 41, fr, 0.3)
        top = 39
    if it.get("room", "").startswith("bath"):
        D.area(0, 12, top + 6, 50, 8, 16, 3000, role="mirror")


def b_plant(m, it):
    name, var = vdata(it)
    h = size(it, (0, 100))[1]
    if name in ("calathea_orbifolia_01", "anthurium_botany_01"):      # ground plants need a pot
        D.plant("planter_pot_clay", 0, 0, 0, h=h * 0.38)
        D.plant(name, 0, 0, h * 0.32, h=h * 0.7, variant=var)
    elif var is not None:
        D.plant(name, 0, 0, 0, h=h, variant=var)
    else:
        D.plant(name, 0, 0, 0, h=h)


def b_decor(m, it):
    v = vdata(it)
    h = size(it, (0, 24))[1]
    if v == "books":
        D.book_stack(0, 0, 0, m.books, seed=sum(map(ord, it["id"])) % 7, n=3)
    elif v == "fruit":
        D.plant("wooden_bowl_02", 0, 0, 0, w=30)
        for dx, dy in ((0, 0), (6, 3), (-5, 4)):
            D.plant("food_pomegranate_01", dx, dy, 3.5, w=8)
    elif v == "towels":
        box("towels", -15, -15, 0, 15, 15, 12, m.terry_clay, 1.5)
    elif v in ("wooden_bowl_02", "wicker_basket_01"):
        D.plant(v, 0, 0, 0, w=max(h, 20))
    else:
        D.plant(v, 0, 0, 0, h=h)


def b_dining_table(m, it):
    kind, w, d = vdata(it)
    wd = m.slot(it, "wood")
    zt = 75
    if kind == "rect":
        D.prism("dining top", D.rrect(-w / 2, -d / 2, w / 2, d / 2, 9), zt - 3.5, zt, wd, 0.25)
        for x in (-w / 2 + 14, w / 2 - 14):
            for y in (-d / 2 + 12, d / 2 - 12):
                D.leg(x, y, 0, zt - 3.5, 2.0, 2.8, wd)
        box("apron", -w / 2 + 12, -d / 2 + 10, zt - 10, w / 2 - 12, d / 2 - 10, zt - 3.5, wd)
        box("runner", -w / 2 + 30, -d / 2 + 28, zt, w / 2 - 30, d / 2 - 28, zt + 0.3, m.slot(it, "runner"))
    else:
        D.disc("dining top", 0, 0, zt - 3.5, zt, w / 2, w / 2, wd, 64, 0.25)
        cyl("pedestal", 0, 0, 8, zt - 3.5, 7, 9, wd)
        D.disc("foot", 0, 0, 0, 8, w * 0.22, w * 0.22, wd, 48, 0.3)


def b_chair(m, it):
    v = vdata(it)
    if v != "spindle":
        D.plant(v, 0, 0, 0, d=48)
        return
    wd, seat = m.slot(it, "wood"), m.slot(it, "seat")
    g = group("chair", 0, 0, "s")
    for x, y in ((-20, -19), (20, -19), (-19, 19), (19, 19)):
        cyl("chair leg", x, y, 0, 76 if y > 0 else 44, 1.7, 1.6, wd, g, segs=16, world=False)
    kit.lbox(g, "seat frame", -22, -21, 42, 22, 21, 45, wd, 0.6)
    kit.lbox(g, "seat", -20, -19, 44.6, 20, 19, 46.3, seat, 0.6)
    kit.lbox(g, "back rail", -21, 17.5, 66, 21, 21.5, 78, wd, 1.2)
    for x in (-10, 0, 10):
        cyl("spindle", x, 19.5, 45, 66, 0.8, 0.8, wd, g, segs=10, world=False)
    kit.lbox(g, "stretcher", -19, -1, 18, 19, 1, 20.5, wd, 0.4)


def b_bed(m, it):
    w, l, hh = vdata(it)
    p = m.slot(it, "pillows")
    pil = [m.linen_white, m.linen_white, p, p] if w > 120 else [m.linen_white, p]
    D.bed(m, 0, 0, w, l, "s", m.slot(it, "headboard"), m.slot(it, "duvet"), m.slot(it, "throw"), pil, head_h=hh,
          frame_mat=m.slot(it, "headboard"))


def b_nightstand(m, it):
    w = vdata(it)
    D.nightstand(m, 0, 0, w, 40 if w > 40 else 38, 52 if w > 40 else 50, "s", m.slot(it, "wood"))


def b_wardrobe(m, it):
    w, n = vdata(it)
    D.closets(with_mats(m, oak=m.slot(it, "pulls")), -w / 2, -30, w / 2, 30, "s", n, mat=m.slot(it, "fronts"))


def b_dresser(m, it):
    w = vdata(it)
    wd = m.slot(it, "wood")
    box("dresser", -w / 2, -19, 12, w / 2, 19, 80, wd, 0.3)
    n = 3 if w > 100 else 2
    for i in range(n):
        a = -w / 2 + 2 + i * (w - 4) / n
        b = a + (w - 4) / n
        box("drawer", a + 0.5, 19, 16, b - 0.5, 19.8, 76, wd, 0.15)
        box("pull", (a + b) / 2 - 3, 19.8, 62.5, (a + b) / 2 + 3, 20.6, 64, m.brass, 0.2)
    for x in (-w / 2 + 4, w / 2 - 4):
        for y in (-15, 15):
            D.leg(x, y, 0, 12, 1.4, 1.8, wd)


def b_desk(m, it):
    w = vdata(it)
    wd = m.slot(it, "wood")
    box("desk top", -w / 2, -24, 73, w / 2, 24, 76, wd, 0.3)
    if w < 110:
        box("desk drawers", w / 2 - 40, -22, 12, w / 2 - 2, 22, 73, wd, 0.3)
        for y in (-21, 21):
            D.leg(-w / 2 + 4, y, 0, 73, 1.4, 1.8, wd)
    else:
        for x in (-w / 2 + 4, w / 2 - 4):
            for y in (-21, 21):
                D.leg(x, y, 0, 73, 1.4, 1.8, wd)


def b_shelf(m, it):
    w = vdata(it)
    box("shelf", -w / 2, -11, 0, w / 2, 11, 2.5, m.slot(it, "wood"), 0.2)
    D.book_row(-w / 2 + 4, -9, 2.5, w * 0.6, "x", m.books, seed=12)


def b_desk_lamp(m, it):
    mt = m.slot(it, "metal")
    cyl("lamp base", 0, 0, 0, 1.5, 7, mat=mt)
    tube("lamp arm", [(0, 0, 1), (2, 2, 36), (20, 10, 44)], 0.6, mt)
    D.shell_cone("lamp shade", 20, 10, 32, 44, 8, 4, mt)
    D.point(20, 10, 36, 6, role="table")


def b_hall_bench(m, it):
    w = vdata(it)
    wd = m.slot(it, "wood")
    box("bench top", -w / 2, -18, 42, w / 2, 18, 46, wd, 0.4)
    for x in (-w / 2 + 6, w / 2 - 6):
        box("bench leg", x - 2, -16, 0, x + 2, 16, 42, wd, 0.3)
    box("bench shelf", -w / 2 + 4, -16, 12, w / 2 - 4, 16, 14, wd, 0.2)
    D.plant("wicker_basket_01", -w / 4, 0, 14, w=min(34, w / 3))
    D.pillow(w / 4, -8, 46, "s", m.slot(it, "cushion"), size=38, lean=-6)


def b_hooks(m, it):
    wd = m.slot(it, "wood")
    box("hook rail", -50, 0, -3.5, 50, 3, 3.5, wd, 0.3)
    for x in (-35, -10, 15, 40):
        cyl("hook", x, -2.5, -1, 0.5, 0.8, mat=m.brass)


def b_wc(m, it):
    D.wc(m, 0, 0, "s", bidet=vdata(it) == "bidet")


def b_cistern(m, it):
    w, d = size(it, (140, 20))
    tiles = m.tiles.get(it.get("room"), m.tiles["bath1"])
    box("cistern box", -w / 2, -d / 2, 0, w / 2, d / 2, 112, tiles)
    box("cistern ledge", -w / 2 - 1, -d / 2 - 2, 112, w / 2 + 1, d / 2, 114, m.slot(it, "top"), 0.2)
    box("flush plate", -9, -d / 2 - 0.6, 88, 8, -d / 2, 102, m.fittings.get(it.get("room"), m.brass), 0.2)


def b_vanity(m, it):
    w, d = vdata(it)
    wd = m.slot(it, "wood")
    box("vanity", -w / 2, -d / 2, 52, w / 2, d / 2, 82, wd, 0.4)
    box("vanity top", -w / 2, -d / 2, 82, w / 2, d / 2, 85, wd, 0.3)
    D.bowl("basin", 0, 0, 98, 20, 16, 13, m.ceramic, 0.9)
    D.disc("basin foot", 0, 0, 85, 86, 12, 9, m.ceramic, 32)
    D.wall_tap(with_mats(m, brass=m.slot(it, "tap")), 0, -d / 2, 104, (0, 1))


def b_towel_rail(m, it):
    mt = m.slot(it, "metal")
    D.towel_rail(with_mats(m, brass=mt), -13, 0, 13, 0, 0, m.slot(it, "towel"))
    for x in (-13, 13):
        tube("bracket", [(x, 0, 0), (x, -4, 0)], 0.6, mt)


def b_tall(m, it):
    wd = m.slot(it, "wood")
    box("utility tall", -30, -30, 0, 30, 29, 236, m.carcass)
    box("utility front", -29.5, 29, 8, 29.5, 30.8, 120, wd, 0.1)
    box("utility front", -29.5, 29, 121, 29.5, 30.8, 236, wd, 0.1)
    box("utility pull", 22, 30.8, 100, 24, 32, 116, m.brass, 0.2)
    box("utility top", -30, -30, 236, 30, 30.8, H, m.room_walls.get(it.get("room"), m.wall))


def b_bistro_table(m, it):
    r = vdata(it)
    wd = m.slot(it, "wood")
    D.disc("bistro table", 0, 0, 70, 72, r, r, wd, 32, 0.2)
    cyl("bistro post", 0, 0, 0, 70, 2.2, mat=m.black)
    D.disc("bistro foot", 0, 0, 0, 2, 20, 20, m.black, 32)


def b_outdoor_bench(m, it):
    w = vdata(it)
    wd = m.slot(it, "wood")
    box("bench", -w / 2, -25, 30, w / 2, 25, 34, wd, 0.5)
    for x in (-w / 2 + 10, 0, w / 2 - 10):
        box("bench leg", x - 3, -21, 0, x + 3, 21, 30, wd, 0.3)
    n = max(1, round(w / 62))
    cw = (w - 10) / n
    for i in range(n):
        x = -w / 2 + 5 + cw * (i + 0.5)
        soft(group("cushion", x, 0, "s", 34), "cushion", (0, 0, 4), (cw - 2, 48, 9), m.slot(it, "cushion"),
             puff=0.06, edge=3)


def b_lounger(m, it):
    box("lounger frame", -30, -57.5, 0, 30, 57.5, 16, m.slot(it, "wood"), 0.5)
    soft(group("lounger", 0, 0, "s", 16), "cushion", (0, 0, 5), (58, 112, 10), m.slot(it, "cushion"), puff=0.05, edge=3)


BUILDERS = {
    "sofa": b_sofa, "lounge_chair": b_lounge, "cushion": b_cushion, "throw": b_throw, "coffee_table": b_coffee,
    "side_table": b_side, "media_unit": b_media, "tv": b_tv, "floor_lamp": b_floor_lamp, "table_lamp": b_table_lamp,
    "pendant": b_pendant, "rug": b_rug, "art": b_art, "mirror": b_mirror, "plant": b_plant, "decor": b_decor,
    "dining_table": b_dining_table, "dining_chair": b_chair, "bed": b_bed, "nightstand": b_nightstand,
    "wardrobe": b_wardrobe, "dresser": b_dresser, "desk": b_desk, "wall_shelf": b_shelf, "desk_lamp": b_desk_lamp,
    "hall_bench": b_hall_bench, "hook_rail": b_hooks, "wc": b_wc, "cistern_wall": b_cistern, "vanity": b_vanity,
    "towel_rail": b_towel_rail, "tall_cupboard": b_tall,
    "bistro_set": lambda m, it: D.plant("outdoor_table_chair_set_01", 0, 0, 0, h=size(it, (0, 86))[1]),
    "bistro_table": b_bistro_table, "stool": lambda m, it: D.plant("folding_wooden_stool", 0, 0, 0, h=45),
    "outdoor_bench": b_outdoor_bench, "lounger": b_lounger,
}
ABSOLUTE_Z = {"pendant"}          # built at their final height; the empty stays at z 0


def build_item(m, it):
    """Build one item at the origin, then move it into place as a single unit."""
    scene = bpy.context.scene
    before = set(scene.collection.objects)
    BUILDERS[it["kind"]](m, it)
    new = [o for o in scene.collection.objects if o not in before and o.parent is None]
    root = link(bpy.data.objects.new(f"item {it['id']} {it['kind']}", None))
    for o in new:
        o.parent = root
    root.location = P(it["x"], it["y"], 0 if it["kind"] in ABSOLUTE_Z else it.get("z", 0))
    root.rotation_euler.z = math.radians(it.get("rot", 0))
    root["item_id"] = it["id"]
    return root


def build_from_config(cfg, export=False):
    D.LIGHTS.clear()
    m = Mats(cfg["finishes"], export)
    build_shell(m)
    kitchen(m)
    if not export:
        kitchen_styling(m)
    D.storage(m)
    bathrooms_fixed(m)
    fixed_lights(m)
    curtains(m)
    for it in cfg["items"]:
        try:
            build_item(m, it)
        except Exception as e:       # one bad item must not stop a render
            print("item skipped", it.get("id"), it.get("kind"), repr(e))
    return m
