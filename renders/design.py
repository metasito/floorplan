"""Unit 13, warm Mediterranean scheme: the whole apartment, furnished, for Cycles.

Every wall, door and fixed item comes from scene.json, which export_scene.py derives from the
plan (rev D), so the model follows the drawing. Furniture keeps the plan's footprints.

The scheme: warm white walls, light oak floor through the dry rooms, a sage kitchen with an oak
worktop, oatmeal linen and cream boucle, jute and terracotta, a clay wall in the living room and a
sage one behind the main bed, zellige-look tiles in the bathrooms, terracotta tiles outside.
Mid-budget pieces only: nothing bespoke but the kitchen.

Assumed, because the plan does not give them: ceiling 270, door heads 210, window heads 240.
"""
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

import kit
from kit import (ASSETS, DOOR_H, H, HEAD, SC, P, ball, box, boxes, bevelled, color, cube_uv, curtain, cyl,
                 glass_mat, group, lbox, link, new_mat, pbr, picture, place, sea_mat, sheer_mat, soft, tube)

_finish = kit._finish
_image = kit._image
GEN = ASSETS / "generated"
LIGHTS = []          # (light object, role, watts), so a mood can rebalance them
R = SC["room_bounds"]


# ---------------------------------------------------------------- colour and materials
def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def kelvin(k):
    """Blackbody colour, normalised; close enough for lamps between 2200 and 6500 K."""
    t = k / 100
    r = 255 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.1 if t <= 66 else 288.1 * (t - 60) ** -0.0755
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5 * math.log(t - 10) - 305.0)
    rgb = [max(0, min(255, v)) / 255 for v in (r, g, b)]
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    mx = max(lin)
    return tuple(v / mx for v in lin)


_cache = {}


def once(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def paint(name, hexc, rough=0.88, bump=0.25, mottle=0.0, tex="plastered_wall_04", tile=2.4):
    """Matt paint or limewash: flat colour on a scanned plaster relief. mottle adds the cloudy
    tonal drift of limewash."""
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    b = n.new("ShaderNodeBsdfPrincipled")
    base = srgb(hexc)
    b.inputs["Roughness"].default_value = rough
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1)
    l.new(tc.outputs["UV"], mp.inputs["Vector"])
    if mottle:
        nz = n.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.6
        nz.inputs["Detail"].default_value = 6
        nz.inputs["Roughness"].default_value = 0.62
        l.new(tc.outputs["Object"], nz.inputs["Vector"])
        ramp = n.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[1].position = 0.72
        ramp.color_ramp.elements[0].color = (*[c * (1 - mottle) for c in base], 1)
        ramp.color_ramp.elements[1].color = (*[min(1, c * (1 + mottle * 0.6)) for c in base], 1)
        l.new(nz.outputs["Fac"], ramp.inputs["Fac"])
        l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = (*base, 1)
    t = n.new("ShaderNodeTexImage")
    t.image = _image(ASSETS / "textures" / tex / "normal.jpg", True)
    l.new(mp.outputs[0], t.inputs["Vector"])
    nm = n.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = bump
    l.new(t.outputs[0], nm.inputs["Color"])
    l.new(nm.outputs[0], b.inputs["Normal"])
    l.new(b.outputs[0], out.inputs[0])
    return m


def fabric(name, tex, hexc, tile=None, sheen=0.7, normal=1.0, val=1.0, rough=None):
    """A scanned weave, desaturated and dyed to a colour."""
    return pbr(name, tex, tile=tile, tint=srgb(hexc), sat=0.0, val=val, sheen=sheen, normal=normal, rough=rough)


def rattan_mat(name="rattan", hexc="#b8894f"):
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    b = n.new("ShaderNodeBsdfPrincipled")
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 60
    nz.inputs["Detail"].default_value = 4
    ramp = n.new("ShaderNodeValToRGB")
    c = srgb(hexc)
    ramp.color_ramp.elements[0].color = (*[v * 0.72 for v in c], 1)
    ramp.color_ramp.elements[1].color = (*[min(1, v * 1.15) for v in c], 1)
    l.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Coat Weight"].default_value = 0.15
    l.new(b.outputs[0], out.inputs[0])
    return m


def cane_mat(name="cane", hexc="#c49a62"):
    """Woven cane webbing over a dark backing, as on cane-fronted cabinets."""
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    b = n.new("ShaderNodeBsdfPrincipled")
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (55, 55, 55)
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(45))
    l.new(tc.outputs["UV"], mp.inputs["Vector"])
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(mp.outputs[0], sep.inputs[0])
    strands = []
    for axis in ("X", "Y"):
        mul = n.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = math.pi * 2
        l.new(sep.outputs[axis], mul.inputs[0])
        s = n.new("ShaderNodeMath")
        s.operation = "SINE"
        l.new(mul.outputs[0], s.inputs[0])
        a = n.new("ShaderNodeMath")
        a.operation = "ABSOLUTE"
        l.new(s.outputs[0], a.inputs[0])
        strands.append(a)
    mx = n.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    l.new(strands[0].outputs[0], mx.inputs[0])
    l.new(strands[1].outputs[0], mx.inputs[1])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.55
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[0].color = (0.02, 0.015, 0.01, 1)
    ramp.color_ramp.elements[1].color = (*srgb(hexc), 1)
    l.new(mx.outputs[0], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.002
    l.new(mx.outputs[0], bump.inputs["Height"])
    l.new(bump.outputs[0], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.5
    l.new(b.outputs[0], out.inputs[0])
    return m


def shade_mat(name, hexc="#efe4d2"):
    """Linen lampshade: translucent, so a bulb inside lights it the way real fabric does."""
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    tl = n.new("ShaderNodeBsdfTranslucent")
    tl.inputs[0].default_value = (*srgb(hexc), 1)
    df = n.new("ShaderNodeBsdfDiffuse")
    df.inputs[0].default_value = (*srgb(hexc), 1)
    mix = n.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.55
    l.new(df.outputs[0], mix.inputs[1])
    l.new(tl.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs[0])
    return m


def emit(name, k=2700, strength=8.0):
    m, nt, out = new_mat(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*kelvin(k), 1)
    e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def frosted_mat():
    m, nt, out = new_mat("frosted glass")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.95, 0.96, 0.96, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.35
    b.inputs["IOR"].default_value = 1.45
    nt.links.new(b.outputs[0], out.inputs[0])
    return m


def glass_clear():
    """Shower and frame glass: thin, so transparent plus a Fresnel gloss renders cleanly."""
    m, nt, out = new_mat("clear glass")
    n, l = nt.nodes, nt.links
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs[0].default_value = (0.94, 0.97, 0.96, 1)
    gl = n.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.02
    fr = n.new("ShaderNodeLayerWeight")
    fr.inputs["Blend"].default_value = 0.12
    mix = n.new("ShaderNodeMixShader")
    l.new(fr.outputs["Fresnel"], mix.inputs[0])
    l.new(tr.outputs[0], mix.inputs[1])
    l.new(gl.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs[0])
    return m


def zellige(name, hexc, size=10.0, grout="#d9d2c6", var=0.12, rough=0.12):
    """Handmade glazed tiles: stack-bonded squares, each a slightly different tone, glossy and
    a little wavy, with a fine pale grout. size in cm."""
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    b = n.new("ShaderNodeBsdfPrincipled")
    tc = n.new("ShaderNodeTexCoord")
    br = n.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = size / 100
    br.inputs["Row Height"].default_value = size / 100
    br.inputs["Mortar Size"].default_value = 0.0018
    br.inputs["Mortar Smooth"].default_value = 0.3
    br.inputs["Bias"].default_value = 0.0
    base = srgb(hexc)
    br.inputs["Color1"].default_value = (*[c * (1 - var) for c in base], 1)
    br.inputs["Color2"].default_value = (*[min(1, c * (1 + var * 0.5)) for c in base], 1)
    br.inputs["Mortar"].default_value = (*srgb(grout), 1)
    l.new(tc.outputs["UV"], br.inputs["Vector"])
    # glaze pooling: a soft noise darkens tile edges and centres a little
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 28
    nz.inputs["Detail"].default_value = 3
    l.new(tc.outputs["UV"], nz.inputs["Vector"])
    mixc = n.new("ShaderNodeMix")
    mixc.data_type = "RGBA"
    mixc.blend_type = "MULTIPLY"
    mixc.inputs["Factor"].default_value = 0.18
    l.new(br.outputs["Color"], mixc.inputs["A"])
    l.new(nz.outputs["Color"], mixc.inputs["B"])
    l.new(mixc.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = 0.35
    # relief: grout recess plus the uneven glaze surface
    inv = n.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    l.new(br.outputs["Fac"], inv.inputs[1])
    h = n.new("ShaderNodeMath")
    h.operation = "MULTIPLY_ADD"
    l.new(nz.outputs["Fac"], h.inputs[0])
    h.inputs[1].default_value = 0.25
    l.new(inv.outputs[0], h.inputs[2])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.004
    l.new(h.outputs[0], bump.inputs["Height"])
    l.new(bump.outputs[0], b.inputs["Normal"])
    l.new(b.outputs[0], out.inputs[0])
    return m


def rug_pic(name, path, x0, y0, x1, y1):
    """An image laid exactly over a plan rectangle (world-space UVs are in metres)."""
    return picture(name, path, (x1 - x0) / 100, (y1 - y0) / 100, x0 / 100, -y1 / 100, rough=0.95)


class M:
    """The scheme's palette, created once per build."""

    def __init__(self):
        self.wall = paint("wall warm white", "#ece6dc", mottle=0.03)
        self.ceiling = paint("ceiling", "#f1eee8", rough=0.95, bump=0.1)
        self.wall_bath = paint("bath paint", "#ece5da", rough=0.7, bump=0.15)
        self.facade = paint("facade render", "#e9e4da", rough=0.95, bump=0.6, tex="white_stucco", tile=2.0)
        self.clay = paint("clay limewash", "#c3a58a", rough=0.92, bump=0.45, mottle=0.09, tex="white_stucco", tile=2.0)
        self.sage = paint("sage limewash", "#a9b29a", rough=0.92, bump=0.45, mottle=0.08, tex="white_stucco", tile=2.0)
        self.clay2 = paint("bedroom clay", "#d0ad94", rough=0.9, bump=0.3, mottle=0.05)
        self.skirt = color("skirting", srgb("#ebe5db"), 0.45)
        self.floor = pbr("oak floor", "laminate_floor_02", sat=0.55, hue=0.515, val=1.12, tint=srgb("#f4ebdc"), rot=90, rough_mul=0.9)
        self.tile1 = zellige("zellige sand", "#ddd0bd", 10)
        self.tile2 = zellige("zellige sage", "#a3ae96", 10, grout="#d8d6cc")
        self.bath_floor = pbr("stone tile", "mixed_stone_tiles", sat=0.6, val=1.25, rough_mul=0.8)
        self.terracotta = pbr("terracotta tile", "terracotta_floor_tiles", sat=0.85, val=1.05)
        self.stone = color("limestone", srgb("#d9d0c2"), 0.45)
        self.oak = pbr("oak", "oak_veneer_05", tile=1.0, sat=0.62, hue=0.515, val=1.0)
        self.oak_dark = pbr("oak smoked", "oak_veneer_05", tile=1.0, sat=0.9, val=0.62)
        self.sage_front = paint("kitchen sage", "#8f9a85", rough=0.55, bump=0.05)
        self.cab_white = color("cabinet white", srgb("#ebe5da"), 0.5)
        self.carcass = color("carcass", srgb("#d8d2c8"), 0.6)
        self.worktop = pbr("oak worktop", "kitchen_wood", tile=0.9, sat=0.6, hue=0.515, val=1.2, rough_mul=0.7, coat=0.15)
        self.splash = zellige("zellige cream", "#ece4d6", 7.5, var=0.08)
        self.frame = color("anthracite", srgb("#3c3f42"), 0.45, 0.3)
        self.door = color("door white", srgb("#eee9e0"), 0.4)
        self.black = color("matt black", srgb("#1d1d1d"), 0.45)
        self.brass = color("brushed brass", srgb("#c8a66a"), 0.32, 1.0)
        self.steel = color("brushed steel", (0.62, 0.62, 0.63), 0.28, 1.0)
        self.ceramic = color("ceramic white", srgb("#f3f1ec"), 0.12, coat=0.5)
        self.glaze = color("glazed ceramic", srgb("#e7dfd2"), 0.25, coat=0.4)
        self.terracotta_pot = color("terracotta pot", srgb("#b4643e"), 0.85)
        self.linen = fabric("oatmeal linen", "rough_linen", "#d9ccb6", tile=0.22, normal=2.0)
        self.linen_white = fabric("white linen", "rough_linen", "#efeae1", tile=0.22, normal=1.6)
        self.linen_rust = fabric("rust linen", "rough_linen", "#a85f3d", tile=0.22, normal=2.0)
        self.linen_sage = fabric("sage linen", "rough_linen", "#9aa58d", tile=0.22, normal=2.0)
        self.linen_ochre = fabric("ochre linen", "rough_linen", "#c99540", tile=0.22, normal=2.0)
        self.boucle = fabric("oatmeal sofa linen", "rough_linen", "#ddd3c2", tile=0.2, sheen=0.6, normal=2.2)
        self.teddy = fabric("cream teddy", "curly_teddy_natural", "#e9e1d4", tile=0.2, sheen=0.4, normal=0.8)
        self.fleece = fabric("terracotta waffle", "waffle_pique_cotton", "#c27850", sheen=0.5, normal=1.6)
        self.fleece_sage = fabric("sage waffle", "waffle_pique_cotton", "#9fac92", sheen=0.5, normal=1.6)
        self.waffle = fabric("waffle cotton", "waffle_pique_cotton", "#efe8dc", normal=1.4)
        self.terry = fabric("terry towel", "terry_cloth", "#e9e1d3", normal=1.8)
        self.terry_clay = fabric("clay towel", "terry_cloth", "#c88e70", normal=1.8)
        self.jute = fabric("jute", "hessian_230", "#c9a979", tile=0.14, sheen=0.2, normal=2.5, val=1.9)
        self.rattan = rattan_mat()
        self.cane = cane_mat()
        self.shade = shade_mat("linen shade")
        self.paper = shade_mat("paper shade", "#f3ece0")
        self.glass = glass_mat()
        self.frosted = frosted_mat()
        self.mirror = color("mirror", (0.92, 0.93, 0.93), 0.02, 1.0)
        self.clear = glass_clear()
        self.tv = color("tv screen", (0.005, 0.005, 0.006), 0.06, coat=1)
        self.books = [color(f"book {i}", srgb(c), 0.6) for i, c in
                      enumerate(("#c7b9a1", "#8b6f53", "#e9e3d7", "#a95f3e", "#5d6b5a", "#d8c7a3", "#3f4446"))]


# ---------------------------------------------------------------- geometry helpers
def prism(name, pts, z0, z1, mat, bevel=0.0):
    """A convex plan polygon (plan cm) extruded between z0 and z1."""
    bm = bmesh.new()
    vs = [bm.verts.new(P(x, y, z)) for z in (z0, z1) for x, y in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    cube_uv(bm)
    return bevelled(link(_finish(name, bm, mat)), bevel)


def rrect(x0, y0, x1, y1, r, seg=6):
    """Rounded-rectangle outline in plan cm."""
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def disc(name, cx, cy, z0, z1, rx, ry, mat, seg=48, bevel=0.0):
    pts = [(cx + rx * math.cos(2 * math.pi * i / seg), cy + ry * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    return prism(name, pts, z0, z1, mat, bevel)


def smooth(ob, levels=2):
    for p in ob.data.polygons:
        p.use_smooth = True
    sb = ob.modifiers.new("subsurf", "SUBSURF")
    sb.levels = sb.render_levels = levels
    return ob


def bowl(name, x, y, z, rx, ry, rz, mat, thick=0.8, seg=48):
    """A bowl opening upward, its rim at z (basin, fruit bowl)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 1e-4], context="VERTS")
    bmesh.ops.scale(bm, vec=(rx / 100, ry / 100, rz / 100), verts=bm.verts)
    cube_uv(bm)
    ob = link(_finish(name, bm, mat, smooth=True))
    ob.location = P(x, y, z)
    s = ob.modifiers.new("solid", "SOLIDIFY")
    s.thickness = thick / 100
    return ob


def wicker(name, x, y, z, rx, ry, rz, mat, cut=0.0, strand=0.22, seg=56):
    """Open-weave rattan shade: a dome turned into a lattice of round strands."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < cut - 1e-4], context="VERTS")
    bmesh.ops.scale(bm, vec=(rx / 100, ry / 100, rz / 100), verts=bm.verts)
    ob = link(_finish(name, bm, mat))
    ob.location = P(x, y, z)
    w = ob.modifiers.new("wire", "WIREFRAME")
    w.thickness = strand / 100
    w.use_even_offset = True
    w.use_relative_offset = False
    sb = ob.modifiers.new("subsurf", "SUBSURF")
    sb.levels = sb.render_levels = 1
    return ob


def shell_cone(name, x, y, z0, z1, r0, r1, mat, seg=48):
    """An open drum or cone, like a lampshade."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r0 / 100, radius2=r1 / 100, depth=(z1 - z0) / 100)
    cube_uv(bm)
    ob = link(_finish(name, bm, mat, smooth=True))
    ob.location = P(x, y, (z0 + z1) / 2)
    s = ob.modifiers.new("solid", "SOLIDIFY")
    s.thickness = 0.004
    return ob


# ---------------------------------------------------------------- lights
def point(x, y, z, watts, k=2700, radius=3, role="lamp", name="lamp"):
    li = bpy.data.lights.new(name, "POINT")
    li.energy = watts
    li.color = kelvin(k)
    li.shadow_soft_size = radius / 100
    ob = link(bpy.data.objects.new(name, li))
    ob.location = P(x, y, z)
    LIGHTS.append((ob, role, watts))
    return ob


def spot(x, y, z, watts, k=3000, cone=100, blend=0.6, radius=2.5, role="down", name="downlight"):
    li = bpy.data.lights.new(name, "SPOT")
    li.energy = watts
    li.color = kelvin(k)
    li.spot_size = math.radians(cone)
    li.spot_blend = blend
    li.shadow_soft_size = radius / 100
    ob = link(bpy.data.objects.new(name, li))
    ob.location = P(x, y, z)
    LIGHTS.append((ob, role, watts))
    return ob


def area(x, y, z, sx, sy, watts, k=2900, rot=(0, 0, 0), role="strip", name="strip"):
    li = bpy.data.lights.new(name, "AREA")
    li.shape = "RECTANGLE"
    li.size, li.size_y = sx / 100, sy / 100
    li.energy = watts
    li.color = kelvin(k)
    ob = link(bpy.data.objects.new(name, li))
    ob.location = P(x, y, z)
    ob.rotation_euler = rot
    ob.visible_camera = False
    ob.visible_glossy = False
    LIGHTS.append((ob, role, watts))
    return ob


def downlight(m, x, y, watts=8):
    """A recessed downlight: trim ring and lens flush with the ceiling, and its beam."""
    cyl("downlight trim", x, y, H - 0.4, H, 4.6, mat=m.cab_white)
    cyl("downlight lens", x, y, H - 0.5, H - 0.4, 3.4, mat=once("lens", lambda: emit("lens", 3000, 12)))
    spot(x, y, H - 1.5, watts)


# ---------------------------------------------------------------- construction
def room_at(x, y):
    for k, bxs in SC["rooms"].items():
        for b in bxs:
            if b[0] - 0.01 <= x <= b[2] + 0.01 and b[1] - 0.01 <= y <= b[3] + 0.01:
                return k
    return None


def exterior(x, y):
    if y < SC["bal_a"][3] + 0.5 or x > 750 - 0.5 or y > 1390 - 0.5 or x < -30 + 0.5:
        return True
    return x > SC["x_lower_out"] - 0.5 and y > 780


def wall_material(m, room, nx, ny, x, y, z):
    if room is None:
        return m.facade if exterior(x, y) else m.wall
    if room == "bath1":
        return m.tile1 if (z < 120 or x >= 524) else m.wall_bath
    if room == "bath2":
        return m.tile2 if (z < 120 or y <= 857) else m.wall_bath
    if room == "bed1" and ny > 0.9 and y < 400:
        return m.sage
    if room == "living" and ny < -0.9 and 370 < y < 383 and x > 311:
        return m.clay
    if room == "bed2" and z < 105:
        return m.clay2
    return m.wall


CUT_X, CUT_Y, CUT_Z = [524], [857], [105, 120]


def split(b):
    x0, y0, z0, x1, y1, z1 = b
    xs = [x0] + [c for c in CUT_X if x0 < c < x1] + [x1]
    ys = [y0] + [c for c in CUT_Y if y0 < c < y1] + [y1]
    zs = [z0] + [c for c in CUT_Z if z0 < c < z1] + [z1]
    return [(xs[i], ys[j], zs[k], xs[i + 1], ys[j + 1], zs[k + 1])
            for i in range(len(xs) - 1) for j in range(len(ys) - 1) for k in range(len(zs) - 1)]


def build_walls(m, items):
    """Walls as one mesh; each face takes the finish of the room it faces."""
    mats = []
    bm = bmesh.new()
    for b in items:
        for x0, y0, z0, x1, y1, z1 in split(b):
            lo, hi = P(x0, y1, z0), P(x1, y0, z1)
            T = Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*(hi - lo), 1))
            bmesh.ops.create_cube(bm, size=1, matrix=T)
    bm.normal_update()
    cube_uv(bm)
    for f in bm.faces:
        c, nrm = f.calc_center_median(), f.normal
        px, py, pz = c.x * 100, -c.y * 100, c.z * 100
        nx, ny = nrm.x, -nrm.y
        if abs(nrm.z) > 0.5:
            mat = m.wall
        else:
            qx, qy = px + nx * 3, py + ny * 3
            mat = wall_material(m, room_at(qx, qy), nx, ny, qx, qy, pz)
        if mat not in mats:
            mats.append(mat)
        f.material_index = mats.index(mat)
    me = bpy.data.meshes.new("walls")
    bm.to_mesh(me)
    bm.free()
    for mt in mats:
        me.materials.append(mt)
    return link(bpy.data.objects.new("walls", me))


DOOR_OPEN = {"D0": 0, "D1": 92, "D2": 75, "D3": 88, "D4": 80, "D5": 70}


def door(m, tag, angle):
    """A door set: lining, architraves on both faces, the leaf at `angle` degrees, levers."""
    d = SC["doors"][tag]
    a, b = d["wall"]
    s0, s1 = d["span"]
    hinge, into = d["hinge"], d["into"]
    other = s1 if hinge == s0 else s0
    d0 = 1 if other > hinge else -1
    entrance = d.get("entrance", False)
    leaf_mat = m.oak if entrance else m.door
    hand = m.brass if entrance else m.black
    t_leaf = 6 if entrance else 4

    def Q(u, v):                     # u across the wall, v along it
        return (u, v) if d["axis"] == "x" else (v, u)

    items = [(a, s0, 0, b, s0 + 2, DOOR_H), (a, s1 - 2, 0, b, s1, DOOR_H), (a, s0, DOOR_H - 2, b, s1, DOOR_H)]
    for face, out in ((a, -1), (b, 1)):
        f0, f1 = sorted((face, face + out * 1.6))
        items += [(f0, s0 - 7, 0, f1, s0, DOOR_H + 7), (f0, s1, 0, f1, s1 + 7, DOOR_H + 7),
                  (f0, s0 - 7, DOOR_H, f1, s1 + 7, DOOR_H + 7)]
    conv = []
    for u0, v0, z0, u1, v1, z1 in items:
        (x0, y0), (x1, y1) = Q(u0, v0), Q(u1, v1)
        conv.append((x0, y0, z0, x1, y1, z1))
    boxes(f"{tag} frame", conv, m.door, 0.12)
    face = b if into > 0 else a
    w = (s1 - s0) - 4
    th = math.radians(angle)
    c, s = (0.0, d0), (into, 0.0)
    v = (c[0] * math.cos(th) + s[0] * math.sin(th), c[1] * math.cos(th) + s[1] * math.sin(th))
    nrm = (-(s[0] * math.cos(th) - c[0] * math.sin(th)), -(s[1] * math.cos(th) - c[1] * math.sin(th)))
    p0 = (face - into * 0.5, hinge + d0 * 2)
    corners = [p0, (p0[0] + v[0] * w, p0[1] + v[1] * w),
               (p0[0] + v[0] * w + nrm[0] * t_leaf, p0[1] + v[1] * w + nrm[1] * t_leaf),
               (p0[0] + nrm[0] * t_leaf, p0[1] + nrm[1] * t_leaf)]
    prism(f"{tag} leaf", [Q(*p) for p in corners], 0.8, DOOR_H - 2.5, leaf_mat, 0.2)
    ex = (p0[0] + v[0] * (w - 7), p0[1] + v[1] * (w - 7))
    for side in (-1, 1):
        off = t_leaf / 2 + side * (t_leaf / 2 + 0.2)
        cx, cy = ex[0] + nrm[0] * off, ex[1] + nrm[1] * off
        ou, ov = nrm[0] * side, nrm[1] * side
        rose = [(cx - v[0] * 2.5, cy - v[1] * 2.5), (cx + v[0] * 2.5, cy + v[1] * 2.5),
                (cx + v[0] * 2.5 + ou * 0.8, cy + v[1] * 2.5 + ov * 0.8), (cx - v[0] * 2.5 + ou * 0.8, cy - v[1] * 2.5 + ov * 0.8)]
        prism("rose", [Q(*p) for p in rose], 102.5, 107.5, hand, 0.1)
        q0 = (cx + ou * 5, cy + ov * 5)
        lev = [(q0[0] - v[0] * 13 - ou * 0.9, q0[1] - v[1] * 13 - ov * 0.9),
               (q0[0] + v[0] * 1 - ou * 0.9, q0[1] + v[1] * 1 - ov * 0.9),
               (q0[0] + v[0] * 1 + ou * 0.9, q0[1] + v[1] * 1 + ov * 0.9),
               (q0[0] - v[0] * 13 + ou * 0.9, q0[1] - v[1] * 13 + ov * 0.9)]
        prism("lever", [Q(*p) for p in lev], 104.1, 105.9, hand, 0.3)
        neck = [(cx, cy), (cx + ou * 5, cy + ov * 5), (cx + ou * 5 + v[0] * 1.6, cy + ov * 5 + v[1] * 1.6),
                (cx + v[0] * 1.6, cy + v[1] * 1.6)]
        prism("lever neck", [Q(*p) for p in neck], 104.2, 105.8, hand)


def window(m, axis, s0, s1, w0, w1, leaves=2, sill=0, head=HEAD, glass=None):
    """Aluminium window or glazed door in a wall from w0 to w1 (across), spanning s0..s1.
    axis "x": the wall runs along y; axis "y": it runs along x."""
    glass = glass or m.glass
    fw = 6
    c0, c1 = w0 + 7, w1 - 7
    bars = [(c0 - 1, s0, sill, c1 + 1, s1, sill + 4), (c0 - 1, s0, head - 5, c1 + 1, s1, head),
            (c0 - 1, s0, sill, c1 + 1, s0 + fw, head), (c0 - 1, s1 - fw, sill, c1 + 1, s1, head)]
    span = (s1 - s0) / leaves
    handles = []
    for i in range(leaves):
        a, b = s0 + i * span, s0 + (i + 1) * span
        bars += [(c0, a + 2, sill + 4, c1, a + 8, head - 5), (c0, b - 8, sill + 4, c1, b - 2, head - 5),
                 (c0, a + 8, sill + 4, c1, b - 8, sill + 12), (c0, a + 8, head - 13, c1, b - 8, head - 5)]
        hs = b - 5 if (i == 0 or leaves == 1) else a + 5
        room_face = c1 if (axis == "y") else c0      # handles on the room side
        hz = sill + min(105, (head - sill) * 0.5)
        handles.append((room_face + (1 if axis == "y" else -3), hs - 1, hz - 8,
                        room_face + (3 if axis == "y" else -1), hs + 1, hz + 3))
    mid = (c0 + c1) / 2
    panes = [(mid - 0.4, s0 + 3, sill + 4, mid + 0.4, s1 - 3, head - 5)]

    def swap(items):
        return [(s_0, u0, z0, s_1, u1, z1) for (u0, s_0, z0, u1, s_1, z1) in items]
    if axis == "y":
        bars, panes, handles = swap(bars), swap(panes), swap(handles)
    boxes("window frame", bars, m.frame, 0.15)
    boxes("glass", panes, glass)
    boxes("window handle", handles, m.frame, 0.3)


def build_shell(m):
    W1, W2, W3, W4, W5 = SC["w1"], SC["w2"], SC["w3"], SC["w4"], SC["w5"]
    LW, XL, XLO = SC["living_w"], SC["x_lower"], SC["x_lower_out"]
    walls = [(*bb[:2], 0, *bb[2:], H) for bb in SC["walls"]]
    # lintels over full-height openings, and the bathroom window's upstand and head
    walls += [(W1[0], -25, HEAD, W1[1], 0, H), (LW, W2[0], HEAD, 750, W2[1], H), (LW, W3[0], HEAD, 750, W3[1], H),
              (XL, W5[0], HEAD, XLO, W5[1], H), (XL, W4[0], 0, XLO, W4[1], 115), (XL, W4[0], 215, XLO, W4[1], H)]
    for d in SC["doors"].values():
        a, b = d["wall"]
        s0, s1 = d["span"]
        walls.append((a, s0, DOOR_H, b, s1, H) if d["axis"] == "x" else (s0, a, DOOR_H, s1, b, H))
    build_walls(m, walls)

    # floors: oak in the dry rooms and their thresholds, stone in the bathrooms
    dry, wet, sills = [], [], []
    for k in ("living", "hall", "storage", "bed1", "bed2"):
        dry += [(x0, y0, -4, x1, y1, 0) for x0, y0, x1, y1 in SC["rooms"][k]]
    for k in ("bath1", "bath2"):
        wet += [(x0, y0, -4, x1, y1, 0) for x0, y0, x1, y1 in SC["rooms"][k]]
    for tag, d in SC["doors"].items():
        a, b = d["wall"]
        s0, s1 = d["span"]
        bx = (a, s0, -4, b, s1, 0) if d["axis"] == "x" else (s0, a, -4, s1, b, 0)
        (wet if tag in ("D2", "D4") else sills if tag == "D0" else dry).append(bx)
    boxes("floor oak", dry, m.floor)
    boxes("floor stone", wet, m.bath_floor)
    sills += [(W1[0], -25, -4, W1[1], 0, 0.5), (LW, W2[0], -4, 750, W2[1], 0.5), (LW, W3[0], -4, 750, W3[1], 0.5),
              (XL, W5[0], -4, XLO, W5[1], 0.5), (XL - 2, W4[0], 113, XLO, W4[1], 115.5)]
    boxes("sills", sills, m.stone, 0.2)
    box("slab", -56, -150, -30, 780, 1390, -4, color("slab", (0.5, 0.5, 0.5), 0.8))
    box("ceiling", -56, -150, H, 780, 1390, H + 30, m.ceiling)
    # balcony floors, a step down from the rooms
    bx0, by0, bx1, by1 = SC["bal_a"]
    boxes("balcony tiles", [(bx0, by0, -6, bx1, by1, -2), (XLO, 790, -6, 780, 1360, -2), (750, 780, -6, 780, 790, -2)],
          m.terracotta)
    rg = m.clear
    boxes("rail glass", [(bx0, by0 + 7.4, -2, bx1 - 8, by0 + 8.6, 104), (bx1 - 8.6, by0 + 8, -2, bx1 - 7.4, by1, 104),
                         (772.4, 788, -2, 773.6, 1360, 104), (750, 784.4, -2, 773, 785.6, 104)], rg)
    boxes("rail top", [(bx0, by0 + 6, 104, bx1 - 6, by0 + 10, 107), (bx1 - 10, by0 + 6, 104, bx1 - 6, by1, 107),
                       (771, 783, 104, 775, 1360, 107), (750, 783, 104, 775, 787, 107)], m.frame, 0.3)
    for y0, y1 in ((W2[0] - 13, W2[1] + 13), (W3[0] - 13, W3[1] + 13)):      # Juliet balconies
        box("juliet glass", 755.4, y0, 2, 756.6, y1, 104, rg)
        box("juliet rail", 754, y0, 104, 758, y1, 107, m.frame, 0.3)
    window(m, "y", W1[0], W1[1], -25, 0)
    window(m, "x", W2[0], W2[1], LW, 750)
    window(m, "x", W3[0], W3[1], LW, 750)
    window(m, "x", W4[0], W4[1], XL, XLO, leaves=1, sill=115, head=215, glass=m.frosted)
    window(m, "x", W5[0], W5[1], XL, XLO)
    items = []
    t = 1.3
    for segs in SC["skirting"].values():
        for x0, y0, x1, y1 in segs:
            if abs(y1 - y0) < 0.01:
                items.append((min(x0, x1), y0 - t, 0, max(x0, x1), y0 + t, 8))
            else:
                items.append((x0 - t, min(y0, y1), 0, x0 + t, max(y0, y1), 8))
    boxes("skirting", items, m.skirt, 0.15)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=45000, matrix=Matrix.Translation((0, 0, -18)))
    cube_uv(bm)
    link(_finish("sea", bm, sea_mat()))


# ---------------------------------------------------------------- furniture
def leg(x, y, z0, z1, r0, r1, mat):
    return cyl("leg", x, y, z0, z1, r0, r1, mat, segs=20)


MULTI = {"pachira_aquatica_01", "calathea_orbifolia_01", "anthurium_botany_01", "fern_02"}


def load_variant(name, idx):
    """Some scans hold several plants side by side; keep one, chosen by idx (left to right)."""
    key = f"{name}#{idx}"
    if key in kit._models:
        return key
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ASSETS / "models" / name / f"{name}.gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    meshes = [o for o in new if o.type == "MESH"]

    def bb(o):
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return (min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))
    boxes_ = {o: bb(o) for o in meshes}
    groups = []                      # cluster meshes whose footprints touch
    for o in sorted(meshes, key=lambda o: boxes_[o][0]):
        b = boxes_[o]
        for g in groups:
            if any(b[0] <= q[2] + 0.02 and q[0] <= b[2] + 0.02 and b[1] <= q[3] + 0.02 and q[1] <= b[3] + 0.02
                   for q in (boxes_[x] for x in g)):
                g.append(o)
                break
        else:
            groups.append([o])
    groups.sort(key=lambda g: min(boxes_[o][0] for o in g))
    keep = set(groups[idx % len(groups)])
    drop = [o for o in new if o.type == "MESH" and o not in keep]
    new = [o for o in new if o not in drop]
    for o in drop:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    coll = bpy.data.collections.new(key)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    coll.instance_offset = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
    kit._models[key] = (coll, (hi - lo) * 100)
    print("variant", key, "of", len(groups), "size cm", [round(v) for v in (hi - lo) * 100])
    return key


def plant(name, x, y, z=0.0, face="s", variant=0, **kw):
    """Place a scanned model; a missing one should never stop a render."""
    try:
        if name in MULTI:
            name = load_variant(name, variant)
        return place(name, x, y, z, face=face, **kw)
    except Exception as e:
        print("model skipped", name, e)


def sofa(m, cx, cy, w, d, face, fabric_mat, leg_mat, seat=44, back=78, arm=16, n=3):
    """A deep, soft-edged sofa of the kind sold in boucle or linen at mid-range shops."""
    g = group("sofa", cx, cy, face)
    lh = 12
    for x, y in [(sx * (w / 2 - 9), sy * (d / 2 - 9)) for sx in (-1, 1) for sy in (-1, 1)]:
        cyl("sofa leg", x, y, 0, lh, 1.8, 2.4, leg_mat, g, segs=16, world=False)
    soft(g, "base", (0, 2, lh + 8), (w, d - 4, 18), fabric_mat, puff=0.02, edge=5)
    soft(g, "back", (0, d / 2 - 9, (lh + back) / 2 + 4), (w - 2, 18, back - lh - 6), fabric_mat, puff=0.04, edge=8)
    for sx in (-1, 1):
        soft(g, "arm", (sx * (w / 2 - arm / 2), 1, (lh + seat + 16) / 2 + 2), (arm, d - 2, seat + 16 - lh - 2), fabric_mat,
             puff=0.05, edge=7)
    inner = w - 2 * arm
    cw = inner / n
    for i in range(n):
        x = -inner / 2 + cw * (i + 0.5)
        soft(g, "seat", (x, -3, seat - 7), (cw - 0.4, d - 22, 15), fabric_mat, puff=0.09, edge=6)
        soft(g, "back cushion", (x, d / 2 - 24, seat + 19), (cw - 0.4, 20, back - seat - 4), fabric_mat, tilt=-10,
             puff=0.14, edge=7)
    return g


def pillow(cx, cy, z, face, mat, size=48, lean=-20, turn=0, depth=14):
    g = group("pillow", cx, cy, (kit.FACE.get(face, 0) if isinstance(face, str) else face) + turn, z)
    soft(g, "pillow", (0, 0, 0), (size, depth, size * 0.92), mat, tilt=lean, puff=0.26, edge=6)
    return g


def throw(cx, cy, z, w, d, face, mat, fold=3.0):
    g = group("throw", cx, cy, face, z)
    soft(g, "throw", (0, 0, 0), (w, d, fold), mat, puff=0.05, edge=1.4)
    return g


def rug(x0, y0, x1, y1, mat, t=1.2, name="rug", z=0.0):
    return box(name, x0, y0, z, x1, y1, z + t, mat, 0.4)


def art(m, x, y, z, w, h, wall, path, frame_mat=None, depth=2.5, mount=6):
    """A framed print with a white mount; (x, y) on the wall face, z its centre."""
    g = group("art", x, y, wall, z)
    frame_mat = frame_mat or m.oak
    t = 2.2
    lbox(g, "frame", -w / 2 - t, -depth, -h / 2 - t, w / 2 + t, 0, h / 2 + t, frame_mat, 0.15)
    lbox(g, "mount", -w / 2, -depth - 0.1, -h / 2, w / 2, -0.4, h / 2, once("mount", lambda: color("mount", srgb("#f4f1ea"), 0.8)))
    img = picture(f"art {Path(path).stem}", path, (w - 2 * mount) / 100, (h - 2 * mount) / 100)
    lbox(g, "print", -w / 2 + mount, -depth - 0.25, -h / 2 + mount, w / 2 - mount, -0.5, h / 2 - mount, img)
    lbox(g, "glass", -w / 2, -depth - 0.4, -h / 2, w / 2, -depth - 0.3, h / 2, m.clear)
    return g


def book_row(x, y, z, length, along, mats, seed=1, h=(19, 27)):
    """Books standing on a shelf, spines out; along is 'x' or 'y'."""
    rng = random.Random(seed)
    pos = 0
    while pos < length - 3:
        t = rng.uniform(1.8, 4.2)
        bh = rng.uniform(*h)
        dep = rng.uniform(14, 20)
        mt = rng.choice(mats)
        if along == "x":
            box("book", x + pos, y, z, x + pos + t, y + dep, z + bh, mt, 0.15)
        else:
            box("book", x, y + pos, z, x + dep, y + pos + t, z + bh, mt, 0.15)
        pos += t + 0.15


def book_stack(x, y, z, mats, seed=2, n=3):
    rng = random.Random(seed)
    for i in range(n):
        w, d, t = rng.uniform(21, 28), rng.uniform(15, 20), rng.uniform(1.8, 3.2)
        ob = box("book", x - w / 2, y - d / 2, z, x + w / 2, y + d / 2, z + t, mats[(i + seed) % len(mats)], 0.12)
        ob.rotation_euler.z = math.radians(rng.uniform(-6, 6))
        z += t
    return z


def table_lamp(m, x, y, z, body="ball", base_mat=None, shade_h=26, shade_r=(19, 15), watts=22, role="table"):
    base_mat = base_mat or m.glaze
    if body == "ball":
        ball("lamp body", x, y, z + 13, 13, base_mat, 1.0)
        top = z + 25
    else:
        cyl("lamp body", x, y, z, z + 30, 7, 5, base_mat)
        top = z + 30
    cyl("lamp stem", x, y, top, top + 10, 0.6, mat=m.brass)
    shell_cone("lamp shade", x, y, top + 4, top + 4 + shade_h, shade_r[0], shade_r[1], m.shade)
    point(x, y, top + 10, watts, 2700, 2, role)


def floor_lamp(m, x, y, watts=40):
    """Tripod floor lamp in oak with a linen drum."""
    for a in (90, 210, 330):
        r = math.radians(a)
        tube("tripod", [(x + 17 * math.cos(r), y + 17 * math.sin(r), 0), (x, y, 132)], 1.1, m.oak)
    cyl("lamp stem", x, y, 128, 140, 0.8, mat=m.brass)
    shell_cone("floor shade", x, y, 132, 160, 20, 18, m.shade)
    point(x, y, 145, watts, 2700, 3, "table")


def pendant_rattan(m, x, y, bottom, rx=24, rz=20, watts=40, shape="dome"):
    if shape == "dome":
        wicker("rattan shade", x, y, bottom, rx, rx, rz * 2, m.rattan, cut=0.0)
    else:
        wicker("rattan globe", x, y, bottom + rz, rx, rx, rz, m.rattan, cut=-0.85)
    top = bottom + 2 * rz
    tube("cable", [(x, y, top - 2), (x, y, H)], 0.35, m.black)
    cyl("canopy", x, y, H - 2, H, 5.5, mat=m.cab_white)
    ball("bulb", x, y, bottom + rz * 0.75, 4.2, once("bulb", lambda: emit("bulb", 2600, 18)))
    point(x, y, bottom + rz * 0.75, watts, 2600, 4, "pendant")


def pendant_paper(m, x, y, bottom, r=22, watts=35):
    ball("paper globe", x, y, bottom + r, r, m.paper)
    tube("cable", [(x, y, bottom + 2 * r - 1), (x, y, H)], 0.3, m.black)
    cyl("canopy", x, y, H - 2, H, 5, mat=m.cab_white)
    point(x, y, bottom + r, watts, 2700, 6, "pendant")


def mirror_round(m, x, y, z, r, wall, frame_mat=None):
    g = group("mirror", x, y, wall, z)
    frame_mat = frame_mat or m.brass
    fr = cyl("mirror frame", 0, 0, -1.2, 1.2, r + 1.6, mat=frame_mat, parent=g, world=False)
    fr.rotation_euler.x = math.radians(90)
    fr.location = Vector((0, -0.012, 0))
    mi = cyl("mirror", 0, 0, -0.4, 0.4, r, mat=m.mirror, parent=g, world=False)
    mi.rotation_euler.x = math.radians(90)
    mi.location = Vector((0, -0.026, 0))
    return g


def closets(m, x0, y0, x1, y1, face, n, h=240, mat=None):
    """Flush built-in wardrobe, fronts facing `face`, two doors per module, slim oak pulls."""
    mat = mat or m.cab_white
    box("closet carcass", x0, y0, 0, x1, y1, h, m.carcass)
    box("closet plinth", x0, y0, 0, x1, y1, 8, m.black)
    ns = face in ("n", "s")
    w = ((x1 - x0) if ns else (y1 - y0)) / n
    fr, pulls = [], []
    for i in range(n * 2):
        a = (x0 if ns else y0) + i * w / 2
        b = a + w / 2
        p = b - 3 if i % 2 == 0 else a + 3
        if face == "s":
            fr.append((a + 0.2, y1, 8.3, b - 0.2, y1 + 1.9, h - 0.3))
            pulls.append((p - 0.8, y1 + 1.9, 95, p + 0.8, y1 + 3.6, 125))
        elif face == "n":
            fr.append((a + 0.2, y0 - 1.9, 8.3, b - 0.2, y0, h - 0.3))
            pulls.append((p - 0.8, y0 - 3.6, 95, p + 0.8, y0 - 1.9, 125))
        elif face == "e":
            fr.append((x1, a + 0.2, 8.3, x1 + 1.9, b - 0.2, h - 0.3))
            pulls.append((x1 + 1.9, p - 0.8, 95, x1 + 3.6, p + 0.8, 125))
        else:
            fr.append((x0 - 1.9, a + 0.2, 8.3, x0, b - 0.2, h - 0.3))
            pulls.append((x0 - 3.6, p - 0.8, 95, x0 - 1.9, p + 0.8, 125))
    boxes("closet fronts", fr, mat, 0.1)
    boxes("closet pulls", pulls, m.oak if mat is not m.oak else m.brass, 0.3)
    if h < H:
        box("bulkhead", x0, y0, h, x1, y1, H, m.wall)


# ---------------------------------------------------------------- the rooms
def kitchen(m):
    """The source's 510 run on the left wall, unit order unchanged, moved toward Balcony A.
    Sage fronts, oak worktop, cream zellige splashback; open oak shelves keep it light."""
    k = SC["kitchen_shift"]
    start, end = 256 - k, 766 - k           # 77, 587
    y_tall = start + 60
    zt = 92
    box("plinth", 0, start, 0, 54, end, 10, m.black)
    box("carcass", 0, y_tall, 10, 58, end, 88, m.carcass)
    fronts, knobs = [], []

    def front(y0, y1, z0, z1, x=58):
        fronts.append((x, y0 + 0.2, z0 + 0.2, x + 1.9, y1 - 0.2, z1 - 0.2))

    units = [(137, 197, "door"), (197, 257, "drawers"), (257, 321, "door"), (321, 407, "sink"),
             (407, 467, "door"), (467, 527, "oven"), (527, 587, "drawers")]
    for y0, y1, kind in units:
        if kind == "door":
            front(y0, y1, 10, 88)
            knobs.append((y1 - 5 if y0 < 300 else y0 + 5, 80))
        elif kind == "sink":
            mid = (y0 + y1) / 2
            front(y0, mid, 10, 88)
            front(mid, y1, 10, 88)
            knobs += [(mid - 4, 80), (mid + 4, 80)]
        elif kind == "drawers":
            for a, b in ((10, 32), (32, 60), (60, 88)):
                front(y0, y1, a, b)
                knobs.append(((y0 + y1) / 2, b - 6))
        elif kind == "oven":
            front(y0, y1, 10, 28)
            knobs.append(((y0 + y1) / 2, 22))
            box("oven", 58, y0 + 0.3, 28.3, 60, y1 - 0.3, 87.7, color("oven glass", (0.015, 0.015, 0.016), 0.06, coat=1), 0.1)
            box("oven handle", 60.5, y0 + 6, 80, 63, y1 - 6, 81.5, m.steel, 0.3)
    # tall integrated fridge column, with a top cupboard
    for a, b in ((10, 92), (92, 196), (196, 236)):
        front(start, y_tall, a, b)
    knobs += [(y_tall - 5, 100), (y_tall - 5, 85), (y_tall - 5, 202)]
    box("tall carcass", 0, start, 10, 58, y_tall, 236, m.carcass)
    box("fridge end panel", 0, start - 2, 0, 60, start, 236, m.sage_front, 0.2)
    boxes("fronts", fronts, m.sage_front, 0.1)
    for y, z in knobs:
        ball("knob", 61.4, y, z, 1.6, m.brass)
    sx0, sy0, sx1, sy1 = 10, 330, 50, 398
    boxes("worktop", [(0, y_tall, 88, 62, sy0, zt), (0, sy1, 88, 62, end, zt), (0, sy0, 88, sx0, sy1, zt),
                      (sx1, sy0, 88, 62, sy1, zt)], m.worktop, 0.2)
    box("splashback", 0, y_tall, zt, 1.2, end, 152, m.splash)
    d = 70                                   # ceramic sink, brass bridge tap
    boxes("sink", [(sx0, sy0, d, sx1, sy1, d + 1.5), (sx0, sy0, d, sx0 + 1.5, sy1, zt + 0.4),
                   (sx1 - 1.5, sy0, d, sx1, sy1, zt + 0.4), (sx0, sy0, d, sx1, sy0 + 1.5, zt + 0.4),
                   (sx0, sy1 - 1.5, d, sx1, sy1, zt + 0.4)], m.ceramic, 0.3)
    ty = (sy0 + sy1) / 2
    cyl("tap base", 5, ty, zt, zt + 4, 2.4, mat=m.brass)
    arc = [(5, ty, zt + 3), (5, ty, zt + 27)]
    for i in range(1, 13):
        t = math.pi * i / 12
        arc.append((14 - 9 * math.cos(t), ty, zt + 27 + 9 * math.sin(t)))
    arc.append((23, ty, zt + 23))
    tube("tap", arc, 1.0, m.brass)
    hy0, hy1 = 649 - k, 705 - k              # induction hob over the oven
    box("hob", 5, hy0, zt, 56, hy1, zt + 0.5, color("hob glass", (0.012, 0.012, 0.014), 0.05, coat=1), 0.1)
    ring = color("hob ring", (0.13, 0.13, 0.13), 0.5)
    for cx, cy, r in ((18, hy0 + 15, 10), (43, hy0 + 15, 7.5), (18, hy0 + 42, 8), (43, hy0 + 42, 9)):
        cyl("ring", cx, cy, zt + 0.5, zt + 0.53, r, mat=ring)
        cyl("ring", cx, cy, zt + 0.5, zt + 0.54, r - 0.5, mat=m.black)
    # uppers: warm-white cupboards beside the fridge, open oak shelves, a plastered hood
    z0, z1 = 152, 236
    up, upf = [], []
    for a, b in ((137, 197), (197, 257), (257, 321)):
        up.append((0, a, z0, 34, b, z1))
        upf.append((34, a + 0.2, z0 + 0.2, 35.8, b - 0.2, z1 - 0.2))
        ball("knob", 37.4, b - 5 if a < 250 else a + 5, z0 + 6, 1.4, m.brass)
    boxes("upper carcass", up, m.carcass)
    boxes("upper fronts", upf, m.cab_white, 0.1)
    boxes("open shelves", [(0, 324, 160, 26, 464, 164), (0, 324, 198, 26, 464, 202), (0, 532, 160, 26, 585, 164)],
          m.oak, 0.2)
    box("hood", 0, hy0 - 4, 156, 48, hy1 + 4, H, m.wall, 0.4)
    box("hood ledge", 0, hy0 - 6, 156, 50, hy1 + 6, 160, m.oak, 0.3)
    area(24, 229, z0 - 0.8, 16, 176, 22, 2900, role="strip")
    area(13, 394, 159, 16, 136, 14, 2900, role="strip")
    box("led diffuser", 28, 140, z0 - 0.6, 31, 318, z0, emit("led strip", 2900, 3.0))
    # what lives on a worktop and its shelves
    plant("ceramic_vase_02", 12, 335, 164, h=18)
    plant("ceramic_vase_04", 11, 358, 164, h=22)
    plant("wooden_bowl_02", 12, 420, 164, w=24)
    book_row(3, 440, 164, 22, "y", m.books, seed=5)
    plant("ceramic_vase_01", 13, 350, 202, h=19)
    z = 202
    for i in range(6):
        cyl("plate", 13, 395, z, z + 0.9, 12 - (i % 2), mat=m.glaze)
        z += 0.9
    for i in range(3):
        bowl("bowl", 13, 430, 202 + 7 + i * 3.2, 8, 8, 7, m.glaze, 0.4)
    plant("wine_bottles_01", 14, 170, zt, h=31)
    plant("wooden_cutting_board", 6, 220, zt, w=38, face="e")
    plant("potted_plant_04", 16, 298, zt, h=26)
    plant("wooden_bowl_01", 32, 440, zt, w=28)
    for dx, dy in ((0, 0), (5, 4), (-4, 5), (2, -5)):
        plant("lemon", 32 + dx, 440 + dy, zt + 3, w=7)
    cyl("oil bottle", 8, 545, zt, zt + 26, 3.2, mat=color("olive oil", srgb("#556b2a"), 0.08, coat=0.8))
    cyl("salt jar", 10, 556, zt, zt + 11, 4.5, mat=m.glaze)
    plant("planter_pot_clay", 22, 568, zt, h=14)
    for x, y in ((48, 180), (48, 400)):
        downlight(m, x, y, 8)


def dining_chair(m, cx, cy, face):
    """Oak chair with a woven paper-cord seat and a curved back rail."""
    g = group("chair", cx, cy, face)
    cord = once("cord", lambda: fabric("paper cord", "hessian_230", "#d8c39c", tile=0.06, sheen=0.1, normal=3.0))
    for x, y in ((-20, -19), (20, -19), (-19, 19), (19, 19)):
        top = 76 if y > 0 else 44
        cyl("chair leg", x, y, 0, top, 1.7, 1.6, m.oak, g, segs=16, world=False)
    lbox(g, "seat frame", -22, -21, 42, 22, 21, 45, m.oak, 0.6)
    lbox(g, "seat", -20, -19, 44.6, 20, 19, 46.3, cord, 0.6)
    lbox(g, "back rail", -21, 17.5, 66, 21, 21.5, 78, m.oak, 1.2)
    for x in (-10, 0, 10):
        cyl("spindle", x, 19.5, 45, 66, 0.8, 0.8, m.oak, g, segs=10, world=False)
    lbox(g, "stretcher", -19, -1, 18, 19, 1, 20.5, m.oak, 0.4)
    return g


def dining(m):
    tx, ty, tw, td = SC["table"]
    zt = 75
    prism("dining top", rrect(tx, ty, tx + tw, ty + td, 9), zt - 3.5, zt, m.oak, 0.25)
    for x, y in ((tx + 14, ty + 12), (tx + tw - 14, ty + 12), (tx + 14, ty + td - 12), (tx + tw - 14, ty + td - 12)):
        leg(x, y, 0, zt - 3.5, 2.0, 2.8, m.oak)
    box("apron", tx + 12, ty + 10, zt - 10, tx + tw - 12, ty + td - 10, zt - 3.5, m.oak)
    for a, b in ((7, 52), (70, 115), (127, 173)):
        cx = tx + (a + b) / 2
        dining_chair(m, cx, ty - 14, "s")
        dining_chair(m, cx, ty + td + 14, "n")
    box("runner", tx + 30, ty + 28, zt, tx + tw - 30, ty + td - 28, zt + 0.3, m.linen)
    plant("ceramic_vase_03", tx + tw / 2 - 30, ty + td / 2, zt + 0.3, h=30)
    plant("wooden_bowl_02", tx + tw / 2 + 25, ty + td / 2, zt + 0.3, w=30)
    for dx, dy in ((0, 0), (6, 3), (-5, 4)):
        plant("food_pomegranate_01", tx + tw / 2 + 25 + dx, ty + td / 2 + dy, zt + 4, w=8)
    plant("wooden_candlestick", tx + tw / 2 - 55, ty + td / 2 + 6, zt + 0.3, h=22)
    for x in (tx + tw / 2 - 42, tx + tw / 2 + 42):
        pendant_rattan(m, x, ty + td / 2, 160, rx=19, rz=15, watts=35)


def living(m):
    sofa(m, 592, 81, 216, 81, "s", m.boucle, m.oak, n=3)
    sofa(m, 456, 197, 160, 80, "e", m.boucle, m.oak, n=2)
    pillow(522, 88, 66, "s", m.linen_rust)
    pillow(566, 90, 66, "s", m.linen, turn=8)
    pillow(660, 88, 66, "s", m.linen_ochre, turn=-6)
    pillow(452, 250, 66, "e", m.linen_sage)
    pillow(450, 150, 66, "e", m.linen, turn=10, size=42)
    throw(686, 80, 63, 26, 60, "s", m.fleece, 4)
    rug(462, 126, 716, 316, m.jute, name="jute rug")
    ct = (604.5, 215)
    prism("coffee top", rrect(ct[0] - 52, ct[1] - 32, ct[0] + 52, ct[1] + 32, 28, 10), 36, 40, m.oak, 0.4)
    prism("coffee base", rrect(ct[0] - 40, ct[1] - 22, ct[0] + 40, ct[1] + 22, 20, 10), 1.2, 36, m.oak, 0.3)
    z = book_stack(ct[0] - 18, ct[1] + 6, 40, m.books, seed=3)
    plant("ceramic_vase_01", ct[0] + 24, ct[1] - 4, 40, h=24)
    plant("lambis_shell", ct[0] - 18, ct[1] + 4, z, w=16)
    disc("side table", 446, 76, 0, 52, 24, 24, m.oak, 40, 0.3)
    table_lamp(m, 446, 72, 52, "ball", m.terracotta_pot, watts=25)
    floor_lamp(m, 698, 150, watts=30)
    # media wall: a cane-fronted oak unit with the TV on it, as the plan
    x0, x1, y0, y1 = 449, 725, 347, 382
    box("media carcass", x0, y0, 12, x1, y1 - 0.5, 50, m.oak, 0.3)
    for i in range(4):
        a = x0 + 2 + i * (x1 - x0 - 4) / 4
        b = a + (x1 - x0 - 4) / 4
        box("cane front", a + 0.6, y0 - 0.8, 14, b - 0.6, y0, 48, m.cane, 0.15)
    for x in (x0 + 8, x1 - 8):
        for y in (y0 + 6, y1 - 6):
            leg(x, y, 0, 12, 1.6, 2.2, m.oak)
    box("tv", 506, 366, 54, 628, 369.5, 125, m.tv, 0.3)
    box("tv stand", 560, 360, 50, 574, 374, 54, m.black, 0.2)
    plant("ceramic_vase_02", 480, 364, 50, h=26)
    book_stack(668, 364, 50, m.books, seed=6, n=4)
    plant("potted_plant_02", 700, 364, 50, h=34)
    art(m, 565, 40, 158, 50, 70, "s", GEN / "print_arch.png")
    plant("pachira_aquatica_01", 84, 40, 0, h=165, variant=0)
    plant("wicker_basket_02", 470, 330, 0, h=30, face="w")
    sheer = once("sheer", lambda: sheer_mat("linen sheer", srgb("#eee6d8"), 0.62))
    curtain((96, 6), (142, 6), sheer, z0=1, z1=H - 4, pleats=8, amp=4)
    curtain((446, 6), (520, 6), sheer, z0=1, z1=H - 4, pleats=10, amp=4)
    curtain((717, 48), (717, 93), sheer, z0=1, z1=H - 4, pleats=7, amp=3.5)
    curtain((717, 247), (717, 300), sheer, z0=1, z1=H - 4, pleats=8, amp=3.5)
    box("curtain track", 90, 2, H - 3, 525, 9, H, m.cab_white)
    box("curtain track", 713, 44, H - 3, 721, 304, H, m.cab_white)
    for x, y in ((120, 470), (250, 470), (250, 640), (250, 120)):
        downlight(m, x, y, 8)


def storage(m):
    """Shelving round the storage; its door opens in from the corridor."""
    x0, y0, x1, y1 = R["storage"]
    sh = []
    for z in (30, 70, 110, 150, 190):
        sh += [(x0, y0, z, x1, y0 + 40, z + 2.5), (x0, y0 + 40, z, x0 + 40, y1, z + 2.5)]
    boxes("storage shelves", sh, m.cab_white, 0.2)
    rng = random.Random(9)
    for z in (32.5, 72.5, 112.5, 152.5):
        x = 10
        while x < 160:
            w = rng.uniform(28, 40)
            if rng.random() < 0.6:
                plant("wicker_basket_01", x + w / 2, y0 + 20, z, w=w * 0.95)
            else:
                box("storage box", x, y0 + 4, z, x + w - 2, y0 + 36, z + rng.uniform(18, 28),
                    color("box", srgb(rng.choice(("#d9cdb8", "#c9b79c", "#e6e0d5"))), 0.8), 0.4)
            x += w + 3
    cyl("vacuum body", 62, 745, 0, 22, 12, mat=color("vacuum", srgb("#d6d3cc"), 0.4))
    tube("vacuum wand", [(62, 745, 20), (58, 760, 105)], 1.6, m.steel)
    downlight(m, 100, 690, 7)


def hall(m):
    """Built-in wardrobes either side of the entrance, an oak bench, hooks and a mirror."""
    closets(m, 0, SC["y_entry"], 180, SC["y_entry"] + 60, "s", 3)
    closets(m, 0, 1300, 180, 1360, "n", 3)
    box("bench top", 190, 1322, 42, 300, 1358, 46, m.oak, 0.4)
    for x in (196, 294):
        box("bench leg", x - 2, 1324, 0, x + 2, 1356, 42, m.oak, 0.3)
    box("bench shelf", 194, 1324, 12, 296, 1356, 14, m.oak, 0.2)
    plant("wicker_basket_01", 222, 1340, 14, w=34)
    pillow(270, 1348, 46, "n", m.linen_rust, size=38, lean=-6)
    box("hook rail", 195, 1357, 160, 295, 1360, 167, m.oak, 0.3)
    for x in (210, 235, 260, 285):
        cyl("hook", x, 1355.5, 162, 163.5, 0.8, mat=m.brass)
    mirror_round(m, 245, 1360, 212, 26, "n")
    rug(212, 790, 288, 1080, m.jute, name="runner")
    art(m, 189, 1020, 150, 40, 54, "e", GEN / "print_olive.png")
    art(m, 189, 820, 150, 40, 54, "e", GEN / "print_lines.png")
    for x, y in ((250, 830), (250, 1000), (120, 1225), (250, 1225)):
        downlight(m, x, y, 8)
    plant("potted_plant_01", 290, 1106, 0, h=95)


def bed(m, cx, cy, w, l, face, head_mat, duvet_mat, throw_mat, pillow_mats, head_h=112, frame_mat=None):
    """Upholstered bed; the headboard sits on the group's +Y side (the wall it backs onto)."""
    g = group("bed", cx, cy, face)
    frame_mat = frame_mat or head_mat
    soft(g, "bed base", (0, 0, 22), (w, l, 26), frame_mat, puff=0.02, edge=4)
    for x, y in [(sx * (w / 2 - 8), sy * (l / 2 - 8)) for sx in (-1, 1) for sy in (-1, 1)]:
        cyl("bed leg", x, y, 0, 9, 2.0, 2.4, m.oak, g, segs=16, world=False)
    soft(g, "headboard", (0, l / 2 + 5, head_h / 2 + 9), (w + 8, 10, head_h), head_mat, puff=0.03, edge=4)
    soft(g, "mattress", (0, 0, 44), (w - 4, l - 4, 20), m.linen_white, puff=0.04, edge=5)
    soft(g, "duvet", (0, -l * 0.1, 51), (w + 6, l * 0.8, 15), duvet_mat, puff=0.07, edge=6)
    soft(g, "duvet fold", (0, l * 0.29, 57.5), (w + 4, 16, 5), duvet_mat, puff=0.1, edge=2.5)
    soft(g, "throw", (0, -l / 2 + 30, 59.5), (w + 12, 46, 3.2), throw_mat, puff=0.06, edge=1.4)
    n = len(pillow_mats)
    for i, pm in enumerate(pillow_mats):
        row = i // 2 if n > 2 else 0
        if n == 1:
            x, pw = 0, w - 30
        else:
            x, pw = (-w / 4 + (i % 2) * w / 2), w / 2 - 8
        soft(g, "pillow", (x, l / 2 - 18 - row * 13, 60 + row * 2), (pw - row * 10, 14, 42 - row * 8),
             pm, tilt=-22, puff=0.22, edge=6)
    return g


def nightstand(m, cx, cy, w, d, h, face, mat=None):
    g = group("nightstand", cx, cy, face)
    mat = mat or m.oak
    lbox(g, "top", -w / 2, -d / 2, h - 2.5, w / 2, d / 2, h, mat, 0.3)
    lbox(g, "body", -w / 2 + 1, -d / 2 + 1, 22, w / 2 - 1, d / 2, h - 2.5, mat, 0.2)
    lbox(g, "drawer", -w / 2 + 2, -d / 2 + 0.5, 34, w / 2 - 2, -d / 2 + 1.2, h - 4, mat, 0.2)
    lbox(g, "shelf", -w / 2 + 1, -d / 2 + 1, 18, w / 2 - 1, d / 2, 20, mat, 0.2)
    for x, y in [(sx * (w / 2 - 3), sy * (d / 2 - 3)) for sx in (-1, 1) for sy in (-1, 1)]:
        cyl("ns leg", x, y, 0, 22, 1.4, 1.6, mat, g, segs=12, world=False)
    lbox(g, "pull", -1.2, -d / 2 - 0.4, h - 14, 1.2, -d / 2 + 0.5, h - 12, m.brass, 0.2)
    return g


def bedroom1(m):
    rug(410, 470, 640, 700, rug_pic("berber rug", GEN / "rug_berber.png", 410, 470, 640, 700), name="berber rug")
    bed(m, 523.5, 509.5, 186, 210, "s", m.linen, m.linen_white, m.fleece,
        [m.linen_white, m.linen_white, m.linen_rust, m.linen_sage])
    for cx in (395.5, 651.5):
        nightstand(m, cx, 420, 50, 40, 52, "s")
        table_lamp(m, cx + (6 if cx > 500 else -6), 424, 52, "cyl", m.glaze, watts=20)
    book_stack(645, 424, 52, m.books, seed=8, n=2)
    plant("ceramic_vase_04", 408, 414, 52, h=18)
    art(m, 480, 394, 160, 50, 70, "s", GEN / "print_shapes.png")
    art(m, 567, 394, 160, 50, 70, "s", GEN / "print_olive.png")
    # wardrobe as the plan, cut to 87; a dresser on the far wall instead of the plan's TV
    closets(m, 443, 720, 530, 778, "n", 1, mat=m.oak)
    box("dresser", 600, 722, 12, 722, 760, 80, m.oak, 0.3)
    for x in (604, 718):
        for y in (726, 756):
            leg(x, y, 0, 12, 1.4, 1.8, m.oak)
    for i in range(3):
        box("dresser drawer", 602 + i * 40, 721.2, 16, 600 + (i + 1) * 40, 722, 76, m.oak, 0.15)
        box("drawer pull", 618 + i * 40, 720.4, 62.5, 624 + i * 40, 721.2, 64, m.brass, 0.2)
    mirror_round(m, 661, 760, 140, 32, "n")
    plant("ceramic_vase_03", 616, 742, 80, h=28)
    plant("potted_plant_01", 706, 740, 80, h=40)
    box("dresser tray", 640, 735, 80, 668, 750, 81, m.brass, 0.2)
    pendant_rattan(m, 523.5, 545, 200, rx=28, rz=16, watts=45)
    lined = once("lined", lambda: fabric("curtain linen", "rough_linen", "#e3d8c6", tile=0.25, sheen=0.4))
    curtain((717, 432), (717, 468), lined, z0=1, z1=H - 4, pleats=6, amp=4)
    curtain((717, 622), (717, 660), lined, z0=1, z1=H - 4, pleats=6, amp=4)
    box("curtain track", 713, 428, H - 3, 721, 664, H, m.cab_white)
    plant("planter_pot_clay", 704, 692, 0, h=26)
    plant("calathea_orbifolia_01", 704, 692, 22, h=50)


def bedroom2(m):
    """Guest room and study: a single bed, a desk under a shelf, wardrobes as the plan."""
    rug(395, 1105, 560, 1230, rug_pic("striped rug", GEN / "rug_stripes.png", 395, 1105, 560, 1230), name="flatweave")
    bed(m, 499, 1046.5, 96, 196, "w", m.linen, m.waffle, m.fleece_sage, [m.linen_white, m.linen_ochre],
        head_h=80, frame_mat=m.linen)
    nightstand(m, 588, 1119.5, 38, 38, 50, "s")
    table_lamp(m, 590, 1122, 50, "ball", m.glaze, shade_r=(15, 12), shade_h=20, watts=18)
    plant("ceramic_vase_04", 580, 1108, 50, h=16)
    closets(m, 323, 1300, 503, 1360, "n", 3)
    box("desk top", 503, 1311, 73, 608, 1359, 76, m.oak, 0.3)
    box("desk drawers", 568, 1314, 12, 606, 1358, 73, m.oak, 0.3)
    for y in (1314, 1356):
        leg(507, y, 0, 73, 1.4, 1.8, m.oak)
    box("desk shelf", 506, 1338, 120, 606, 1360, 122.5, m.oak, 0.2)
    book_row(510, 1340, 122.5, 60, "x", m.books, seed=12)
    plant("ceramic_vase_02", 590, 1348, 122.5, h=20)
    dining_chair(m, 549, 1296, "s")
    book_stack(532, 1340, 76, m.books, seed=4, n=2)
    plant("potted_plant_04", 594, 1336, 76, h=20)
    cyl("desk lamp base", 518, 1346, 76, 77.5, 7, mat=m.black)
    tube("desk lamp arm", [(518, 1346, 77), (520, 1344, 112), (538, 1336, 120)], 0.6, m.black)
    shell_cone("desk lamp shade", 540, 1335, 108, 120, 8, 4, m.black)
    point(540, 1335, 112, 6, role="table")
    art(m, 450, 994, 150, 60, 42, "s", GEN / "print_horizon.png")
    pendant_paper(m, 466, 1170, 205, r=24, watts=35)
    lined = once("lined", lambda: fabric("curtain linen", "rough_linen", "#e3d8c6", tile=0.25, sheen=0.4))
    curtain((603, 1062), (603, 1098), lined, z0=1, z1=H - 4, pleats=6, amp=3.5)
    curtain((603, 1262), (603, 1298), lined, z0=1, z1=H - 4, pleats=6, amp=3.5)
    box("curtain track", 599, 1058, H - 3, 607, 1302, H, m.cab_white)
    plant("fern_02", 342, 1014, 0, h=55)


def _lid_bm():
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Diagonal((0.35, 0.46, 0.03, 1)))
    for v in bm.verts:
        if v.co.y < 0:
            v.co.x *= 0.72
    return bm


def wc(m, cx, cy, face, bidet=False):
    """Wall-hung rimless pan or bidet in white ceramic; its back is on the group's +Y side."""
    g = group("bidet" if bidet else "wc", cx, cy, face)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Diagonal((0.36, 0.54, 0.30, 1)))
    for v in bm.verts:
        if v.co.y < 0:
            v.co.x *= 0.86
        if v.co.z < 0:
            v.co.x *= 0.8
            v.co.y = v.co.y * 0.8 + 0.03
    ob = link(_finish("pan", bm, m.ceramic))
    ob.parent = g
    ob.location = Vector((0, 0, 0.255))
    bv = ob.modifiers.new("round", "BEVEL")
    bv.width = 0.085
    bv.segments = 8
    bv.limit_method = "NONE"
    for p in ob.data.polygons:
        p.use_smooth = True
    if not bidet:
        lid = link(_finish("lid", _lid_bm(), m.ceramic))
        lid.parent = g
        lid.location = Vector((0, -0.005, 0.418))
        lb = lid.modifiers.new("round", "BEVEL")
        lb.width = 0.012
        lb.segments = 4
        for p in lid.data.polygons:
            p.use_smooth = True
    else:
        cyl("bidet tap", 0, 18, 40, 45, 1.6, mat=m.brass, parent=g, world=False)
    return g


def vanity(m, x0, y0, x1, y1, basin_c, top_mat=None):
    """Wall-hung oak vanity with a ceramic vessel basin."""
    top_mat = top_mat or m.oak
    box("vanity", x0, y0, 52, x1, y1, 82, m.oak, 0.4)
    box("vanity top", x0, y0, 82, x1, y1, 85, top_mat, 0.3)
    bx, by = basin_c
    bowl("basin", bx, by, 98, 20, 16, 13, m.ceramic, 0.9)
    disc("basin foot", bx, by, 85, 86, 12, 9, m.ceramic, 32)


def wall_tap(m, x, y, z, direction):
    """A brass wall spout from a small plate; direction is where it points (plan)."""
    dx, dy = direction
    tube("spout", [(x, y, z), (x + dx * 18, y + dy * 18, z)], 1.1, m.brass)
    if dx == 0:
        box("tap plate", x - 3.5, min(y, y - dy), z - 3.5, x + 3.5, max(y, y - dy), z + 3.5, m.brass, 0.2)
    else:
        box("tap plate", min(x, x - dx), y - 3.5, z - 3.5, max(x, x - dx), y + 3.5, z + 3.5, m.brass, 0.2)


def towel_rail(m, x0, y0, x1, y1, z, towel=None):
    tube("towel rail", [(x0, y0, z), (x1, y1, z)], 0.9, m.brass)
    if towel is not None:
        if abs(y1 - y0) < 1:
            box("towel", x0 + 3, y0 - 2.5, z - 55, x1 - 3, y0 + 2.5, z + 1, towel, 1.2)
        else:
            box("towel", x0 - 2.5, y0 + 3, z - 55, x0 + 2.5, y1 - 3, z + 1, towel, 1.2)


def shower(m, x, y, z, arm_dir):
    """Exposed brass shower: mixer plate, riser, arm and a round rain head."""
    dx, dy = arm_dir
    if dx:
        box("mixer plate", min(x, x + dx * 1.2), y - 7, 98, max(x, x + dx * 1.2), y + 7, 112, m.brass, 0.3)
    else:
        box("mixer plate", x - 7, min(y, y + dy * 1.2), 98, x + 7, max(y, y + dy * 1.2), 112, m.brass, 0.3)
    rx, ry = x + dx * 4, y + dy * 4
    tube("riser", [(rx, ry, 112), (rx, ry, z)], 1.0, m.brass)
    tube("shower arm", [(rx, ry, z), (x + dx * 34, y + dy * 34, z)], 0.9, m.brass)
    disc("rain head", x + dx * 34, y + dy * 34, z - 1.5, z, 12, 12, m.brass, 40, 0.2)
    ball("mixer handle", x + dx * 3.5, y + dy * 3.5, 105, 2.2, m.brass)


def bathroom1(m):
    """En-suite: oak vanity and round mirror, walk-in shower behind glass, WC and bidet moved
    10 left as the review asks, and a tall cupboard housing the boiler and washer."""
    x0, y0, x1, y1 = R["bath1"]
    vanity(m, 418, y0, 490, 836, (454, 812))
    wall_tap(m, 454, y0, 104, (0, 1))
    mirror_round(m, 454, y0, 150, 30, "s")
    area(454, 806, 186, 50, 10, 16, 3000, role="mirror")
    plant("ceramic_vase_04", 481, 808, 85, h=14)
    box("soap", 424, 806, 85, 432, 812, 87, m.glaze, 0.4)
    box("cistern box", 383, 962, 0, 524, 982, 112, m.tile1)
    box("cistern ledge", 382, 960, 112, 525, 982, 114, m.stone, 0.2)
    wc(m, 443.5, 935, "n")
    wc(m, 503, 935, "n", bidet=True)
    plant("potted_plant_04", 400, 970, 114, h=20)
    plant("ceramic_vase_02", 515, 972, 114, h=16)
    box("flush plate", 435, 961.4, 88, 452, 962, 102, m.brass, 0.2)
    box("utility tall", x0, 922, 0, 382, y1, 236, m.carcass)
    box("utility front", 382, 923, 8, 383.8, 981, 120, m.oak, 0.1)
    box("utility front", 382, 923, 121, 383.8, 981, 236, m.oak, 0.1)
    box("utility pull", 383.8, 930, 100, 385, 932, 116, m.brass, 0.2)
    box("utility top", x0, 922, 236, 382, y1, H, m.wall_bath)
    box("shower glass", 523.5, y0, 0, 524.5, 893, 200, m.clear)
    box("shower glass", 527.5, 889, 0, 528.5, y1, 200, m.clear)
    box("glass profile", 523, y0, 0, 525, y0 + 2, 200, m.brass)
    box("glass profile", 527, y1 - 2, 0, 529, y1, 200, m.brass)
    box("glass rail", 523, y0, 199, 529, y1, 200.5, m.brass)
    box("drain", 529, 797, -0.2, 588, 802, 0.05, m.steel)
    shower(m, x1, 850, 210, (-1, 0))
    box("niche shelf", 560, 972, 120, 600, 982, 121.5, m.stone)
    cyl("bottle", 572, 977, 121.5, 141.5, 2.8, mat=color("amber bottle", srgb("#8a5a2b"), 0.1, coat=1))
    cyl("bottle", 584, 977, 121.5, 139, 2.6, mat=m.glaze)
    towel_rail(m, 495, 794, 519, 794, 125, m.terry)
    plant("wicker_basket_02", 402, 898, 0, h=34)
    for x, y in ((400, 860), (566, 850), (566, 930)):
        downlight(m, x, y, 7)


def bathroom2(m):
    x0, y0, x1, y1 = R["bath2"]
    box("shower glass", x0, 851.5, 0, 112, 852.5, 200, m.clear)
    box("shower glass", 97, 856.5, 0, x1, 857.5, 200, m.clear)
    box("glass rail", x0, 851, 199, x1, 858, 200.5, m.brass)
    box("drain", 16, 788, -0.2, 21, 847, 0.05, m.steel)
    shower(m, 93, y0, 210, (0, 1))
    box("niche shelf", 138, y0, 120, 174, y0 + 10, 121.5, m.stone)
    cyl("bottle", 150, y0 + 5, 121.5, 141, 2.8, mat=color("amber bottle", srgb("#8a5a2b"), 0.1, coat=1))
    box("cistern box", x0, 885, 0, x0 + 18, 1005, 112, m.tile2)
    box("cistern ledge", x0, 884, 112, x0 + 20, 1006, 114, m.stone, 0.2)
    wc(m, x0 + 18 + 27, 915, "e")
    wc(m, x0 + 18 + 27, 976, "e", bidet=True)
    plant("ceramic_vase_01", x0 + 10, 950, 114, h=18)
    vanity(m, 13, 1031, 173, y1, (93, 1052))
    wall_tap(m, 93, y1, 104, (0, -1))
    box("mirror", 50, y1 - 2.5, 112, 136, y1 - 0.5, 190, m.mirror, 0.4)
    box("mirror frame", 48, y1 - 2.0, 110, 138, y1 - 0.3, 192, m.brass, 0.3)
    area(93, 1066, 196, 70, 8, 14, 3000, role="mirror")
    plant("potted_plant_04", 150, 1058, 85, h=20)
    box("towels", 22, 1036, 85, 52, 1066, 97, m.terry_clay, 1.5)
    towel_rail(m, 173, 1000, 173, 1024, 120, m.terry)
    for x, y in ((93, 815), (93, 960), (93, 1050)):
        downlight(m, x, y, 7)


def balcony_a(m):
    rug(200, -128, 380, -38, rug_pic("outdoor rug", GEN / "rug_stripes.png", 200, -128, 380, -38), t=0.6,
        name="outdoor rug", z=-2)
    plant("outdoor_table_chair_set_01", 290, -84, -2, h=86, face="e")
    box("bench", 470, -77, 30, 720, -27, 34, m.oak, 0.5)
    for x in (480, 595, 710):
        box("bench leg", x - 3, -73, -2, x + 3, -31, 30, m.oak, 0.3)
    for x in (505, 565, 625, 685):
        soft(group("bench cushion", x, -52, "s", 34), "cushion", (0, 0, 4), (58, 48, 9), m.linen, puff=0.06, edge=3)
    pillow(520, -36, 50, "s", m.linen_rust, size=44, lean=-12)
    pillow(690, -36, 50, "s", m.linen_ochre, size=44, lean=-12, turn=-10)
    plant("pachira_aquatica_01", 6, -100, -2, h=150, variant=1)
    plant("potted_plant_02", 170, -122, -2, h=80)
    plant("planter_pot_clay", 430, -118, -2, h=34)
    plant("anthurium_botany_01", 430, -118, 26, h=38)
    plant("potted_plant_01", 735 - 12, -120, -2, h=70)
    for x in (100, 400, 650):
        box("wall light", x - 6, -32, 205, x + 6, -25, 222, m.black, 0.5)
        point(x, -36, 212, 12, 2700, 3, "outdoor")


def balcony_b(m):
    plant("folding_wooden_stool", 690, 935, -2, h=45)
    plant("folding_wooden_stool", 735, 870, -2, h=45, face="w")
    disc("bistro table", 712, 900, 68, 70, 28, 28, m.oak, 32, 0.2)
    cyl("bistro post", 712, 900, -2, 68, 2.2, mat=m.black)
    disc("bistro foot", 712, 900, -2, 0, 20, 20, m.black, 32)
    plant("ceramic_vase_03", 712, 900, 70, h=22)
    box("lounger frame", 645, 1185, -2, 705, 1300, 14, m.oak, 0.5)
    soft(group("lounger", 675, 1242, "s", 14), "cushion", (0, 0, 5), (58, 112, 10), m.linen, puff=0.05, edge=3)
    pillow(675, 1192, 32, "s", m.linen_ochre, size=40, lean=-30, turn=180)
    plant("planter_pot_clay", 752, 1060, -2, h=40)
    plant("potted_plant_02", 752, 1060, 30, h=60)
    plant("potted_plant_01", 748, 815, -2, h=80)
    box("wall light", 635, 1179, 205, 642, 1191, 222, m.black, 0.5)
    point(646, 1185, 212, 10, 2700, 3, "outdoor")


def build(doors=None):
    m = M()
    build_shell(m)
    angles = dict(DOOR_OPEN)
    angles.update(doors or {})
    for tag in SC["doors"]:
        door(m, tag, angles[tag])
    for fn in (kitchen, dining, living, storage, hall, bedroom1, bedroom2, bathroom1, bathroom2, balcony_a, balcony_b):
        fn(m)
    return m
