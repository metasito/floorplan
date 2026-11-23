#!/usr/bin/env python3
"""Export the plan geometry from build_floorplan.py to scene.json for Blender.

Blender's Python lacks shapely, so walls are decomposed into boxes here. All positions
are plan centimetres, so the 3D model always follows the revised drawing.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_floorplan as B  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402


def to_boxes(geom):
    """Split a rectilinear shape into boxes, merging cells along each row."""
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    out = []
    for poly in polys:
        xs = sorted({round(c[0], 3) for r in [poly.exterior, *poly.interiors] for c in r.coords})
        ys = sorted({round(c[1], 3) for r in [poly.exterior, *poly.interiors] for c in r.coords})
        for y0, y1 in zip(ys, ys[1:]):
            start = None
            for x0, x1 in zip(xs, xs[1:]):
                inside = poly.contains(box(x0, y0, x1, y1).representative_point())
                if inside and start is None:
                    start = x0
                if not inside and start is not None:
                    out.append([start, y0, x0, y1])
                    start = None
            if start is not None:
                out.append([start, y0, xs[-1], y1])
    return out


# Doors: wall axis ("x" = wall runs along y, so the leaf spans y), wall faces, span,
# hinge end, and the side the leaf swings into. Taken from draw_openings() in the plan.
DOORS = {
    "D0": dict(axis="x", wall=(-30, 0), span=(B.Y_D3, B.Y_ENTRY_HINGE), hinge=B.Y_ENTRY_HINGE, into=+1, w=100, entrance=True),
    "D1": dict(axis="x", wall=(B.OPEN_W, B.X_ROOMS), span=(B.Y_D1, B.Y_D1_END), hinge=B.Y_D1_END, into=+1, w=90),
    "D2": dict(axis="y", wall=(B.Y_BED1_END, B.Y_BATH1), span=tuple(B.D2_NEW), hinge=B.D2_NEW[0], into=+1, w=80),
    "D3": dict(axis="x", wall=(B.OPEN_W, B.X_ROOMS), span=(B.Y_D3, B.Y_D3_END), hinge=B.Y_D3_END, into=+1, w=90),
    "D4": dict(axis="x", wall=(B.X_B2_E, B.X_B2_OUT), span=(B.Y_D4, B.Y_D4_END), hinge=B.Y_D4, into=-1, w=80),
    "D5": dict(axis="x", wall=(B.X_STORE, B.X_B2_OUT), span=tuple(B.D5), hinge=B.D5[1], into=-1, w=80),
}

ROOM_KEYS = ("living", "hall", "storage", "bed1", "bed2", "bath1", "bath2")

# Skirting: each dry room's boundary, broken at doors, full-height glazing and the open
# side between living room and hall. Wet rooms are tiled and get none.
gaps = [
    box(B.W1[0], -5, B.W1[1], 5),
    box(B.LIVING_W - 5, B.W2[0], B.LIVING_W + 5, B.W2[1]),
    box(B.LIVING_W - 5, B.W3[0], B.LIVING_W + 5, B.W3[1]),
    box(B.X_LOWER - 5, B.W5[0], B.X_LOWER + 5, B.W5[1]),
    box(B.X_B2_OUT - 1, B.Y_B2_WALL - 5, B.OPEN_W + 1, B.Y_B2_WALL + 5),
]
for d in DOORS.values():
    a, b = d["wall"]
    s0, s1 = d["span"]
    gaps.append(box(a - 5, s0, b + 5, s1) if d["axis"] == "x" else box(s0, a - 5, s1, b + 5))
gaps = unary_union(gaps)
skirting = {}
for k in ("living", "hall", "storage", "bed1", "bed2"):
    edge = B.ROOMS[k].boundary.difference(gaps)
    segs = []
    for line in (edge.geoms if hasattr(edge, "geoms") else [edge]):
        pts = list(line.coords)
        segs += [[*a, *b] for a, b in zip(pts, pts[1:]) if abs(a[0] - b[0]) + abs(a[1] - b[1]) > 0.5]
    skirting[k] = segs

scene = {
    # columns are merged in: a column overlapping a wall leaves coplanar faces, which render black
    "walls": to_boxes(unary_union([B.EXT, B.PARTITION, *B.COLUMNS])),
    "rooms": {k: to_boxes(B.ROOMS[k].buffer(0)) for k in ROOM_KEYS},
    "room_bounds": {k: list(B.ROOMS[k].bounds) for k in ROOM_KEYS + ("bal_a", "bal_b")},
    "skirting": skirting,
    "doors": DOORS,
    "w1": list(B.W1), "w2": list(B.W2), "w3": list(B.W3), "w4": list(B.W4), "w5": list(B.W5),
    "living_w": B.LIVING_W, "living_d": B.LIVING_D, "open_w": B.OPEN_W,
    "x_store": B.X_STORE, "y_store": B.Y_STORE, "y_store_wall": B.Y_STORE_WALL, "y_b2_wall": B.Y_B2_WALL,
    "x_b2": B.X_B2, "x_b2_e": B.X_B2_E, "x_b2_out": B.X_B2_OUT, "y_b2": B.Y_B2, "y_b2_end": B.Y_B2_END,
    "y_entry": B.Y_ENTRY, "x_rooms": B.X_ROOMS, "x_lower": B.X_LOWER, "x_lower_out": B.X_LOWER_OUT,
    "y_bed1": B.Y_BED1, "y_bed1_end": B.Y_BED1_END, "y_bath1": B.Y_BATH1, "y_bath1_end": B.Y_BATH1_END,
    "y_bed2": B.Y_BED2, "y_end": B.Y_END, "col_x": [B.COL_X0, B.COL_X1], "y_col3_top": B.Y_COL3_TOP,
    "y_step_wall": B.Y_STEP_WALL, "x_bal_b": B.X_BAL_B, "rail_b": [B.RAIL_IN, B.RAIL_OUT],
    "facade_out": B.Y_FACADE_OUT, "bal_a": [B.BAL_A_X0, B.BAL_A_TOP, B.BAL_A_X1, B.Y_FACADE_OUT],
    "kitchen_shift": B.KITCHEN_SHIFT, "table": [B.TABLE_X, B.TABLE_Y, 180, 85],
    "areas": {k: round(v, 2) for k, v in B.AREA.items()},
}
(HERE / "scene.json").write_text(json.dumps(scene))
print("walls", len(scene["walls"]), "skirting", {k: len(v) for k, v in skirting.items()})
print("wall area check m2:", round(sum((b[2] - b[0]) * (b[3] - b[1]) for b in scene["walls"]) / 1e4, 2),
      "vs", round(unary_union([B.EXT, B.PARTITION, *B.COLUMNS]).area / 1e4, 2))
