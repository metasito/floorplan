"""Photoreal interior renders of Unit 13 in Blender Cycles, one furnished scheme per style.

Walls, openings, kitchen and furniture footprints all come from scene.json, which
export_scene.py derives from build_floorplan.py, so the renders follow the drawing.

Usage:
  blender -b --factory-startup --disable-autoexec --python render_interiors.py -- \
      --style modern --view lounge --samples 256 --res 1920 1200 --out out/modern_lounge.png

Assumed, because the source plan does not give them: ceiling height 270, door and window
heads 240, internal doors 210, and the sea itself, which is illustrative.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
SC = json.loads((HERE / "scene.json").read_text())
DIMS = json.loads((HERE / "texture_dims.json").read_text())

H = 270            # ceiling, assumed
HEAD = 240         # window and balcony door heads, assumed
DOOR_H = 210       # internal doors, assumed
EYE = 135

scene = bpy.context.scene
for o in list(bpy.data.objects):      # the factory scene's cube, camera and light
    bpy.data.objects.remove(o, do_unlink=True)


# ---------------------------------------------------------------- coordinates
def P(x, y, z=0.0):
    """Plan centimetres (y down the sheet) to Blender metres."""
    return Vector((x / 100, -y / 100, z / 100))


FACE = {"s": 0, "n": 180, "e": 90, "w": -90}   # models face -Y, which is plan south


def link(ob):
    scene.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------- materials
def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    return m, nt, nt.nodes.new("ShaderNodeOutputMaterial")


def color(name, rgb, rough=0.5, metal=0.0, coat=0.0, sheen=0.0):
    m, nt, out = new_mat(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Sheen Weight"].default_value = sheen
    nt.links.new(b.outputs[0], out.inputs[0])
    return m


def glow(name, rgb, strength):
    m, nt, out = new_mat(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*rgb, 1)
    e.inputs[1].default_value = strength
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs[0].default_value = (rgb[0] * 0.8, rgb[1] * 0.8, rgb[2] * 0.8, 1)
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(d.outputs[0], add.inputs[0])
    nt.links.new(e.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    return m


def _image(path, non_color=False):
    im = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def pbr(name, tex, tile=None, tint=(1, 1, 1), val=1.0, sat=1.0, hue=0.5, rough=None, rough_mul=1.0,
        normal=1.0, rot=0, metal=0.0, sheen=0.0, coat=0.0):
    """Scanned material at its real-world scale. UVs are in metres, from cube_uv()."""
    tile = tile or DIMS[tex][0] / 1000
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    b = n.new("ShaderNodeBsdfPrincipled")
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1)
    mp.inputs["Rotation"].default_value[2] = math.radians(rot)
    l.new(tc.outputs["UV"], mp.inputs["Vector"])
    root = ASSETS / "textures" / tex

    d = n.new("ShaderNodeTexImage")
    d.image = _image(root / "diffuse.jpg")
    l.new(mp.outputs[0], d.inputs["Vector"])
    hs = n.new("ShaderNodeHueSaturation")
    hs.inputs["Hue"].default_value = hue
    hs.inputs["Saturation"].default_value = sat
    hs.inputs["Value"].default_value = val
    l.new(d.outputs[0], hs.inputs["Color"])
    mul = n.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = tint
    l.new(hs.outputs[0], mul.inputs[0])
    l.new(mul.outputs[0], b.inputs["Base Color"])

    if rough is None:
        r = n.new("ShaderNodeTexImage")
        r.image = _image(root / "rough.jpg", True)
        l.new(mp.outputs[0], r.inputs["Vector"])
        rm = n.new("ShaderNodeMath")
        rm.operation = "MULTIPLY"
        rm.use_clamp = True
        rm.inputs[1].default_value = rough_mul
        l.new(r.outputs[0], rm.inputs[0])
        l.new(rm.outputs[0], b.inputs["Roughness"])
    else:
        b.inputs["Roughness"].default_value = rough

    t = n.new("ShaderNodeTexImage")
    t.image = _image(root / "normal.jpg", True)
    l.new(mp.outputs[0], t.inputs["Vector"])
    nm = n.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nm.inputs["Strength"].default_value = normal
    l.new(t.outputs[0], nm.inputs["Color"])
    l.new(nm.outputs[0], b.inputs["Normal"])

    b.inputs["Metallic"].default_value = metal
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Coat Weight"].default_value = coat
    l.new(b.outputs[0], out.inputs[0])
    return m


def picture(name, path, w_m, h_m, x0=None, y0=None, rough=0.7):
    """An image laid over a w x h metre area; x0, y0 place it for world-space meshes."""
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    b = n.new("ShaderNodeBsdfPrincipled")
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / w_m, 1 / h_m, 1)
    if x0 is None:
        mp.inputs["Location"].default_value = (0.5, 0.5, 0)
    else:
        mp.inputs["Location"].default_value = (-x0 / w_m, -y0 / h_m, 0)
    l.new(tc.outputs["UV"], mp.inputs["Vector"])
    d = n.new("ShaderNodeTexImage")
    d.image = _image(path)
    d.extension = "EXTEND"
    l.new(mp.outputs[0], d.inputs["Vector"])
    l.new(d.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    l.new(b.outputs[0], out.inputs[0])
    return m


GLASS_DIM = [0.44]     # share of the view each pane passes to the camera; set per style


def glass_mat(view_dim=None):
    """Window glass. Light enters at full strength; only the camera sees it dimmed, as a
    photographer's exposure blend would, so the sea is not lost to a burnt-out window."""
    view_dim = GLASS_DIM[0] if view_dim is None else view_dim
    m, nt, out = new_mat("window glass")
    n, l = nt.nodes, nt.links
    tr = n.new("ShaderNodeBsdfTransparent")
    lp = n.new("ShaderNodeLightPath")
    a = n.new("ShaderNodeMath")
    a.operation = "MULTIPLY"
    a.inputs[1].default_value = 1 - view_dim
    l.new(lp.outputs["Is Camera Ray"], a.inputs[0])
    s = n.new("ShaderNodeMath")
    s.operation = "SUBTRACT"
    s.inputs[0].default_value = 1
    l.new(a.outputs[0], s.inputs[1])
    l.new(s.outputs[0], tr.inputs[0])
    mirror = n.new("ShaderNodeBsdfPrincipled")
    mirror.inputs["Metallic"].default_value = 1
    mirror.inputs["Roughness"].default_value = 0
    mirror.inputs["Base Color"].default_value = (0.9, 0.95, 0.95, 1)
    f = n.new("ShaderNodeFresnel")
    f.inputs["IOR"].default_value = 1.5
    # Panes are closed boxes. Without this, rays leaving a pane meet total internal
    # reflection and the window turns into a mirror that also shuts out the daylight.
    geo = n.new("ShaderNodeNewGeometry")
    front = n.new("ShaderNodeMath")
    front.operation = "SUBTRACT"
    front.inputs[0].default_value = 1
    l.new(geo.outputs["Backfacing"], front.inputs[1])
    fac = n.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    l.new(f.outputs[0], fac.inputs[0])
    l.new(front.outputs[0], fac.inputs[1])
    mix = n.new("ShaderNodeMixShader")
    l.new(fac.outputs[0], mix.inputs[0])
    l.new(tr.outputs[0], mix.inputs[1])
    l.new(mirror.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs[0])
    return m


def sheer_mat(name, rgb, opacity=0.55):
    m, nt, out = new_mat(name)
    n, l = nt.nodes, nt.links
    tl = n.new("ShaderNodeBsdfTranslucent")
    tl.inputs[0].default_value = (*rgb, 1)
    df = n.new("ShaderNodeBsdfDiffuse")
    df.inputs[0].default_value = (*rgb, 1)
    tr = n.new("ShaderNodeBsdfTransparent")
    a = n.new("ShaderNodeMixShader")
    a.inputs[0].default_value = 0.5
    l.new(tl.outputs[0], a.inputs[1])
    l.new(df.outputs[0], a.inputs[2])
    b = n.new("ShaderNodeMixShader")
    b.inputs[0].default_value = opacity
    l.new(tr.outputs[0], b.inputs[1])
    l.new(a.outputs[0], b.inputs[2])
    l.new(b.outputs[0], out.inputs[0])
    return m


def sea_mat():
    m, nt, out = new_mat("sea")
    n, l = nt.nodes, nt.links
    tc = n.new("ShaderNodeTexCoord")
    bump_in = None
    for scale, stretch, amp in ((0.9, 2.6, 1.0), (5.5, 2.0, 0.35)):
        mp = n.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (scale, scale * stretch, 1)
        l.new(tc.outputs["Object"], mp.inputs["Vector"])
        nz = n.new("ShaderNodeTexNoise")
        nz.inputs["Detail"].default_value = 7
        nz.inputs["Roughness"].default_value = 0.55
        l.new(mp.outputs[0], nz.inputs["Vector"])
        g = n.new("ShaderNodeMath")
        g.operation = "MULTIPLY"
        g.inputs[1].default_value = amp
        l.new(nz.outputs[0], g.inputs[0])
        if bump_in is None:
            bump_in = g
        else:
            add = n.new("ShaderNodeMath")
            add.operation = "ADD"
            l.new(bump_in.outputs[0], add.inputs[0])
            l.new(g.outputs[0], add.inputs[1])
            bump_in = add
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.35
    l.new(bump_in.outputs[0], bump.inputs["Height"])
    b = n.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.01, 0.13, 0.2, 1)
    b.inputs["Roughness"].default_value = 0.06
    b.inputs["IOR"].default_value = 1.33
    l.new(bump.outputs[0], b.inputs["Normal"])
    # atmospheric haze toward the horizon
    cam = n.new("ShaderNodeCameraData")
    rng = n.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value = 2500
    rng.inputs["From Max"].default_value = 42000
    l.new(cam.outputs["View Distance"], rng.inputs["Value"])
    hz = n.new("ShaderNodeEmission")
    hz.inputs[0].default_value = (0.70, 0.82, 0.93, 1)
    hz.inputs[1].default_value = 0.42
    mix = n.new("ShaderNodeMixShader")
    l.new(rng.outputs[0], mix.inputs[0])
    l.new(b.outputs[0], mix.inputs[1])
    l.new(hz.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs[0])
    return m


# ---------------------------------------------------------------- mesh helpers
def cube_uv(bm):
    """Cube-project UVs in metres, so scanned materials land at true scale without seams."""
    uv = bm.loops.layers.uv.verify()
    bm.normal_update()
    for f in bm.faces:
        n = f.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            c = lp.vert.co
            lp[uv].uv = (c.x, c.y) if axis == 2 else (c.x, c.z) if axis == 1 else (c.y, c.z)


def _finish(name, bm, mat, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.update()
    return bpy.data.objects.new(name, me)


def bevelled(ob, width, segments=2):
    if width:
        m = ob.modifiers.new("bevel", "BEVEL")
        m.width = width / 100
        m.segments = segments
        m.limit_method = "ANGLE"
    return ob


def boxes(name, items, mat, bevel=0.0):
    """Boxes in plan cm: (x0, y0, z0, x1, y1, z1), joined into one world-space object."""
    bm = bmesh.new()
    for x0, y0, z0, x1, y1, z1 in items:
        lo, hi = P(min(x0, x1), max(y0, y1), min(z0, z1)), P(max(x0, x1), min(y0, y1), max(z0, z1))
        size = hi - lo
        T = Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*size, 1))
        bmesh.ops.create_cube(bm, size=1, matrix=T)
    cube_uv(bm)
    return bevelled(link(_finish(name, bm, mat)), bevel)


def box(name, x0, y0, z0, x1, y1, z1, mat, bevel=0.0):
    return boxes(name, [(x0, y0, z0, x1, y1, z1)], mat, bevel)


def lbox(parent, name, x0, y0, z0, x1, y1, z1, mat, bevel=0.0):
    """A box in a parent's local cm, in Blender axes: front is -Y."""
    bm = bmesh.new()
    lo, hi = Vector((x0, y0, z0)) / 100, Vector((x1, y1, z1)) / 100
    T = Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*(hi - lo), 1))
    bmesh.ops.create_cube(bm, size=1, matrix=T)
    cube_uv(bm)
    ob = link(_finish(name, bm, mat))
    ob.parent = parent
    return bevelled(ob, bevel)


def soft(parent, name, c, size, mat, tilt=0.0, puff=0.13, edge=3.0):
    """An upholstered cushion: rounded, slightly swollen, with a little natural unevenness."""
    bm = bmesh.new()
    sc = Vector(size) / 100
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Diagonal((*sc, 1)))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
    cube_uv(bm)
    ob = link(_finish(name, bm, mat, smooth=True))
    ob.parent = parent
    ob.location = Vector(c) / 100
    ob.rotation_euler.x = math.radians(tilt)
    bv = ob.modifiers.new("bevel", "BEVEL")
    bv.width = edge / 100
    bv.segments = 3
    bv.limit_method = "ANGLE"
    sb = ob.modifiers.new("subsurf", "SUBSURF")
    sb.levels = sb.render_levels = 1
    cs = ob.modifiers.new("cast", "CAST")
    cs.cast_type = "SPHERE"
    cs.factor = puff
    tx = bpy.data.textures.get("wrinkle") or bpy.data.textures.new("wrinkle", "CLOUDS")
    tx.noise_scale = 0.16
    dp = ob.modifiers.new("wrinkle", "DISPLACE")
    dp.texture = tx
    dp.strength = 0.012
    dp.mid_level = 0.5
    dp.texture_coords = "GLOBAL"
    return ob


def cyl(name, x, y, z0, z1, r0, r1=None, mat=None, parent=None, segs=32, world=True):
    """A cylinder or cone. Plan cm, or a parent's local cm with world=False."""
    r1 = r0 if r1 is None else r1
    bm = bmesh.new()
    h = (z1 - z0) / 100
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r0 / 100, radius2=r1 / 100, depth=h)
    for f in bm.faces:
        f.smooth = len(f.verts) == 4          # round sides, flat caps
    cube_uv(bm)
    ob = link(_finish(name, bm, mat))
    ob.location = (P(x, y) if world else Vector((x, y, 0)) / 100) + Vector((0, 0, (z0 + z1) / 200))
    if parent:
        ob.parent = parent
    return ob


def ball(name, x, y, z, r, mat, squash=1.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=r / 100)
    cube_uv(bm)
    ob = link(_finish(name, bm, mat, smooth=True))
    ob.location = P(x, y, z)
    ob.scale.z = squash
    return ob


def tube(name, pts, r, mat):
    """A round bar through plan-cm points (x, y, z)."""
    c = bpy.data.curves.new(name, "CURVE")
    c.dimensions = "3D"
    c.bevel_depth = r / 100
    c.bevel_resolution = 3
    c.use_fill_caps = True
    s = c.splines.new("POLY")
    s.points.add(len(pts) - 1)
    for sp, p in zip(s.points, pts):
        sp.co = (*P(*p), 1)
    c.materials.append(mat)
    return link(bpy.data.objects.new(name, c))


def group(name, x, y, face="s", z=0.0):
    e = link(bpy.data.objects.new(name, None))
    e.location = P(x, y, z)
    e.rotation_euler.z = math.radians(FACE.get(face, 0) if isinstance(face, str) else face)
    return e


# ---------------------------------------------------------------- scanned models
_models = {}


def _load(name):
    if name in _models:
        return _models[name]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ASSETS / "models" / name / f"{name}.gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    coll = bpy.data.collections.new(name)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    coll.instance_offset = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
    _models[name] = (coll, (hi - lo) * 100)
    return _models[name]


def place(name, x, y, z=0.0, face="s", w=None, d=None, h=None, scale=None, stretch=False):
    """Put a scanned model on the plan, centred on x, y, sized by whichever of w, d, h is given.
    w and d are the model's own width and depth, before it is turned to face its direction."""
    coll, size = _load(name)
    want = [(w, size.x, 0), (d, size.y, 1), (h, size.z, 2)]
    if scale is not None:
        s = [scale] * 3
    elif stretch:
        s = [(t / n if t else 1.0) for t, n, _ in want]
    else:
        k = next(t / n for t, n, _ in want if t)
        s = [k] * 3
    ob = link(bpy.data.objects.new(name, None))
    ob.instance_type = "COLLECTION"
    ob.instance_collection = coll
    ob.scale = s
    ob.location = P(x, y, z)
    ob.rotation_euler.z = math.radians(FACE.get(face, 0) if isinstance(face, str) else face)
    return ob, size.z * s[2]


def hang(name, x, y, bottom, cable_mat, **kw):
    """A pendant with its lowest point at `bottom`; a cable makes up any gap to the ceiling."""
    ob, height = place(name, x, y, bottom, **kw)
    if bottom + height < H:
        tube("cable", [(x, y, bottom + height - 2), (x, y, H)], 0.35, cable_mat)
    return ob


# ---------------------------------------------------------------- the apartment
def window_h(x0, x1, y_out, y_in, frame, glass, leaves=2):
    """A glazed door or window in a wall running along x."""
    w = (x1 - x0) / leaves
    y0, y1 = y_out + 7, y_in - 7
    ym0, ym1 = y0 - 1, y1 + 1
    bars = [(x0, ym0, 0, x1, ym1, 3), (x0, ym0, HEAD - 5, x1, ym1, HEAD),
            (x0, ym0, 0, x0 + 5, ym1, HEAD), (x1 - 5, ym0, 0, x1, ym1, HEAD)]
    for i in range(leaves):
        a, b = x0 + i * w, x0 + (i + 1) * w
        bars += [(a + 1, y0, 3, a + 7, y1, HEAD - 5), (b - 7, y0, 3, b - 1, y1, HEAD - 5),
                 (a + 7, y0, 3, b - 7, y1, 11), (a + 7, y0, HEAD - 13, b - 7, y1, HEAD - 5)]
    boxes("frame", bars, frame, 0.15)
    box("glass", x0 + 3, (y0 + y1) / 2 - 0.4, 3, x1 - 3, (y0 + y1) / 2 + 0.4, HEAD - 5, glass)


def window_v(y0, y1, x_in, x_out, frame, glass, leaves=2):
    """A glazed door or window in a wall running along y."""
    w = (y1 - y0) / leaves
    x0, x1 = x_in + 7, x_out - 7
    xm0, xm1 = x0 - 1, x1 + 1
    bars = [(xm0, y0, 0, xm1, y1, 3), (xm0, y0, HEAD - 5, xm1, y1, HEAD),
            (xm0, y0, 0, xm1, y0 + 5, HEAD), (xm0, y1 - 5, 0, xm1, y1, HEAD)]
    for i in range(leaves):
        a, b = y0 + i * w, y0 + (i + 1) * w
        bars += [(x0, a + 1, 3, x1, a + 7, HEAD - 5), (x0, b - 7, 3, x1, b - 1, HEAD - 5),
                 (x0, a + 7, 3, x1, b - 7, 11), (x0, a + 7, HEAD - 13, x1, b - 7, HEAD - 5)]
    boxes("frame", bars, frame, 0.15)
    box("glass", (x0 + x1) / 2 - 0.4, y0 + 3, 3, (x0 + x1) / 2 + 0.4, y1 - 3, HEAD - 5, glass)


def shell(floor, wall, ceiling, skirt=None, frame=None, door=None, ironmongery=None, skirt_h=9, rail=None):
    frame = frame or color("frame", (0.03, 0.03, 0.035), 0.4, 0.4)
    door = door or color("door", (0.82, 0.81, 0.79), 0.45)
    ironmongery = ironmongery or color("handle", (0.55, 0.55, 0.56), 0.3, 1)
    rail = rail or frame
    glass = glass_mat()
    W1, W2 = SC["w1"], SC["w2"]
    W3, W4, W5 = SC["w3"], SC["w4"], SC["w5"]
    LW, XL = SC["living_w"], SC["x_lower"]

    walls = [(*b[:2], 0, *b[2:], H) for b in SC["walls"]]
    walls += [(*b[:2], 0, *b[2:], H) for b in SC["columns"]]
    # lintels over the openings the plan cuts full height
    walls += [(W1[0], -25, HEAD, W1[1], 0, H), (LW, W2[0], HEAD, 750, W2[1], H), (LW, W3[0], HEAD, 750, W3[1], H),
              (XL, W4[0], HEAD, XL + 25, W4[1], H), (XL, W5[0], HEAD, XL + 25, W5[1], H)]
    openings = [("x", 311, 323, *SC["d1"]), ("x", 311, 323, *SC["d3"]), ("x", 177, 189, *SC["d4"]),
                ("y", SC["y_store_wall"], SC["y_store_wall"] + 12, *SC["d5"]),
                ("y", 778, 790, *SC["d2"]), ("x", -30, 0, *SC["d0"])]
    leaves, handles = [], []
    for kind, a, b, c, e in openings:
        m = (a + b) / 2
        if kind == "x":
            walls.append((a, c, DOOR_H, b, e, H))
            leaves.append((m - 2, c + 1, 0.5, m + 2, e - 1, DOOR_H - 0.5))
            handles.append((m - 6, e - 9, 104, m + 6, e - 7, 106))
        else:
            walls.append((c, a, DOOR_H, e, b, H))
            leaves.append((c + 1, m - 2, 0.5, e - 1, m + 2, DOOR_H - 0.5))
            handles.append((c + 7, m - 6, 104, c + 9, m + 6, 106))
    boxes("walls", walls, wall)
    boxes("door leaves", leaves, door, 0.2)
    boxes("door handles", handles, ironmongery, 0.2)

    # structure: slab, floor finish, ceiling, and the balcony above
    box("slab", -56, -150, -30, 780, 1390, -4, color("slab", (0.5, 0.5, 0.5), 0.8))
    box("floor", -30, -25, -4, 760, 1365, 0, floor)      # one piece: overlapping coplanar faces go black
    box("ceiling", -56, -150, H, 780, 1390, H + 30, ceiling)

    # Balcony A
    bx0, by0, bx1, by1 = SC["bal_a"]
    bal = pbr("balcony tile", "large_grey_tiles", val=1.15, sat=0.4)
    box("balcony floor", bx0, by0, -4, bx1, by1 + 1, -1, bal)
    rail_glass = glass_mat(0.9)
    rx0, ry0, rx1 = bx0, by0 + 8, bx1 - 8
    box("rail glass", rx0, ry0 - 0.6, 2, rx1, ry0 + 0.6, 108, rail_glass)
    box("rail glass", rx1 - 0.6, ry0, 2, rx1 + 0.6, by1, 108, rail_glass)
    box("rail top", rx0, ry0 - 2, 108, rx1 + 2, ry0 + 2, 111, rail, 0.2)
    box("rail top", rx1 - 2, ry0, 108, rx1 + 2, by1, 111, rail, 0.2)

    window_h(W1[0], W1[1], -25, 0, frame, glass)
    window_v(W2[0], W2[1], LW, 750, frame, glass)
    window_v(W3[0], W3[1], LW, 750, frame, glass)
    window_v(W4[0], W4[1], XL, XL + 25, frame, glass, 1)
    window_v(W5[0], W5[1], XL, XL + 25, frame, glass)
    # Juliet rail outside W2
    y0, y1 = W2[0] - 13, W2[1] + 13
    bars = [(755, y0, 100, 758, y1, 103), (755, y0, 12, 758, y1, 14)]
    y = y0
    while y < y1:
        bars.append((756, y, 12, 757, y + 1, 100))
        y += 11
    boxes("juliet rail", bars, rail)

    if skirt is not None:
        items = []
        t = 1.4
        for x0, y0, x1, y1 in SC["skirting"]:
            if abs(y1 - y0) < 0.01:
                items.append((min(x0, x1), y0 - t, 0, max(x0, x1), y0 + t, skirt_h))
            else:
                items.append((x0 - t, min(y0, y1), 0, x0 + t, max(y0, y1), skirt_h))
        boxes("skirting", items, skirt, 0.15)

    # sea, far below the assumed upper-floor balcony
    bm = bmesh.new()
    size = 45000
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size, matrix=Matrix.Translation((0, 0, -18)))
    cube_uv(bm)
    link(_finish("sea", bm, sea_mat()))


def portal(a, b, kind):
    """Guides Cycles' sampling through a window, which removes most interior noise."""
    li = bpy.data.lights.new("portal", "AREA")
    li.shape = "RECTANGLE"
    try:
        li.cycles.is_portal = True
    except AttributeError:
        return
    ob = link(bpy.data.objects.new("portal", li))
    li.size, li.size_y = (b - a) / 100, HEAD / 100
    if kind == "n":                       # emits into the room, toward -Y
        ob.location = P((a + b) / 2, -6, HEAD / 2)
        ob.rotation_euler = (math.radians(-90), 0, 0)
    else:                                 # emits into the room, toward -X
        ob.location = P(SC["living_w"] + 6, (a + b) / 2, HEAD / 2)
        ob.rotation_euler = (math.radians(90), 0, math.radians(90))


def fill(watts):
    """A large soft ceiling bounce, unseen by camera and reflections: the photographer's fill."""
    if not watts:
        return
    li = bpy.data.lights.new("fill", "AREA")
    li.shape = "RECTANGLE"
    li.size, li.size_y = 6.0, 3.2
    li.energy = watts
    li.color = (1.0, 0.86, 0.72)
    ob = link(bpy.data.objects.new("fill", li))
    ob.location = P(340, 200, H - 6)
    ob.visible_camera = False
    ob.visible_glossy = False


def lamp(x, y, z, watts=25, rgb=(1.0, 0.72, 0.46), radius=6):
    li = bpy.data.lights.new("lamp", "POINT")
    li.energy = watts
    li.color = rgb
    li.shadow_soft_size = radius / 100
    ob = link(bpy.data.objects.new("lamp", li))
    ob.location = P(x, y, z)


# ---------------------------------------------------------------- kitchen
def _handle(items, kind, x, y0, y1, z0, z1, drawer, mat_knob, low=False):
    yc = (y0 + y1) / 2
    z = (z0 + z1) / 2 if drawer else (z0 + 8 if low else z1 - 8)
    if kind == "bar":
        items.append((x, yc - 9, z - 0.6, x + 2.2, yc + 9, z + 0.6))
    elif kind == "knob":
        ball("knob", x + 1.6, yc, z, 1.5, mat_knob)


def _front(fronts, frames, x, y0, y1, z0, z1, shaker):
    fronts.append((x, y0 + 0.2, z0 + 0.2, x + 1.2 if shaker else x + 2, y1 - 0.2, z1 - 0.2))
    if shaker:
        s = 6.5
        ya, yb, za, zb = y0 + 0.2, y1 - 0.2, z0 + 0.2, z1 - 0.2
        frames += [(x + 1, ya, za, x + 2.4, ya + s, zb), (x + 1, yb - s, za, x + 2.4, yb, zb),
                   (x + 1, ya + s, za, x + 2.4, yb - s, za + s), (x + 1, ya + s, zb - s, x + 2.4, yb - s, zb)]


def kitchen(front, top, splash, handle_mat, plinth=None, handle="bar", uppers="cab", upper=None, shelf=None,
            hood="flat", hood_mat=None, shaker=False, tall=None, led=True, top_h=4):
    """The 510 run on the left wall. Unit order and widths are the source's, moved along the
    wall. The first unit is drawn as the tall fridge: the source does not name its appliances."""
    k = SC["kitchen_shift"]
    start, end = 256 - k, 766 - k           # 77, 587
    y_tall = start + 60
    steel = color("steel", (0.62, 0.62, 0.63), 0.28, 1)
    plinth = plinth or front
    tall = tall or front
    upper = upper or front
    black_glass = color("black glass", (0.012, 0.012, 0.014), 0.06, coat=1)
    zt = 88 + top_h

    box("plinth", 0, start, 0, 52, end, 10, plinth)
    box("carcass", 0, y_tall, 10, 58, end, 88, color("carcass", (0.2, 0.2, 0.2), 0.6))
    fronts, frames, handles = [], [], []
    units = [(137, 197, "door"), (197, 257, "drawers"), (257, 321, "door"), (321, 407, "double"),
             (407, 467, "door"), (467, 527, "oven"), (527, 587, "drawers")]
    for y0, y1, kind in units:
        if kind == "door":
            _front(fronts, frames, 58, y0, y1, 10, 88, shaker)
            _handle(handles, handle, 60, y0, y1, 10, 88, False, handle_mat)
        elif kind == "double":
            m = (y0 + y1) / 2
            for a, b in ((y0, m), (m, y1)):
                _front(fronts, frames, 58, a, b, 10, 88, shaker)
                _handle(handles, handle, 60, a, b, 10, 88, False, handle_mat)
        elif kind == "drawers":
            for a, b in ((10, 36), (36, 62), (62, 88)):
                _front(fronts, frames, 58, y0, y1, a, b, shaker)
                _handle(handles, handle, 60, y0, y1, a, b, True, handle_mat)
        elif kind == "oven":
            _front(fronts, frames, 58, y0, y1, 10, 30, shaker)
            _handle(handles, handle, 60, y0, y1, 10, 30, True, handle_mat)
            box("oven", 58, y0 + 0.3, 30.3, 60, y1 - 0.3, 87.7, black_glass, 0.1)
            box("oven handle", 60, y0 + 6, 79, 62.5, y1 - 6, 80.5, steel, 0.3)
            box("oven strip", 60, y0 + 2, 82.5, 60.2, y1 - 2, 87, steel)
    # tall fridge column
    n_base = len(fronts)
    for a, b in ((10, 92), (92, 216)):
        _front(fronts, frames, 58, start, y_tall, a, b, shaker)
        _handle(handles, handle, 60, start, y_tall, a, b, True, handle_mat)
    box("fridge carcass", 0, start, 10, 58, y_tall, 216, tall)
    boxes("fronts", fronts[:n_base], front, 0.08)
    boxes("tall fronts", fronts[n_base:], tall, 0.08)
    if frames:
        boxes("front frames", frames, front, 0.08)
    if handles:
        boxes("handles", handles, handle_mat, 0.15)

    # worktop, cut round the sink
    sx0, sy0, sx1, sy1 = 10, 327, 52, 401
    boxes("worktop", [(0, y_tall, 88, 62, sy0, zt), (0, sy1, 88, 62, end, zt),
                      (0, sy0, 88, sx0, sy1, zt), (sx1, sy0, 88, 62, sy1, zt)], top, 0.12)
    box("splashback", 0, y_tall, zt, 1.2, end, 150, splash)

    # sink
    d = 72
    boxes("sink", [(sx0, sy0, d, sx1, sy1, d + 0.4), (sx0, sy0, d, sx0 + 0.4, sy1, zt + 0.1),
                   (sx1 - 0.4, sy0, d, sx1, sy1, zt + 0.1), (sx0, sy0, d, sx1, sy0 + 0.4, zt + 0.1),
                   (sx0, sy1 - 0.4, d, sx1, sy1, zt + 0.1)], steel)
    ty = (sy0 + sy1) / 2
    cyl("tap base", 5, ty, zt, zt + 3, 2.2, mat=steel)
    arc = [(5, ty, zt + 2), (5, ty, zt + 26)]
    for i in range(1, 13):
        t = math.pi * i / 12
        arc.append((14 - 9 * math.cos(t), ty, zt + 26 + 9 * math.sin(t)))
    arc.append((23, ty, zt + 22))
    tube("tap", arc, 1.0, steel)

    # hob
    hy0, hy1 = 649 - k, 705 - k
    box("hob", 5, hy0, zt, 56, hy1, zt + 0.5, black_glass, 0.1)
    ring = color("hob ring", (0.12, 0.12, 0.12), 0.5)
    for cx, cy, r in ((18, hy0 + 15, 10), (43, hy0 + 15, 7.5), (18, hy0 + 42, 8), (43, hy0 + 42, 9)):
        cyl("ring", cx, cy, zt + 0.5, zt + 0.53, r, mat=ring)
        cyl("ring", cx, cy, zt + 0.5, zt + 0.54, r - 0.5, mat=black_glass)

    hood_mat = hood_mat or steel
    if uppers == "cab":
        z0, z1 = 150, 216
        up, upf, upfr, uph = [], [], [], []
        for a, b in ((137, 197), (197, 257), (257, 321), (321, 364), (364, 407), (407, 467), (527, 587)):
            up.append((0, a, z0, 33, b, z1))
            _front(upf, upfr, 33, a, b, z0, z1, shaker)
            _handle(uph, handle, 35, a, b, z0, z1, False, handle_mat, low=True)
        boxes("upper carcass", up, upper)
        boxes("upper fronts", upf, upper, 0.08)
        if upfr:
            boxes("upper frames", upfr, upper, 0.08)
        if uph:
            boxes("upper handles", uph, handle_mat, 0.15)
        if led:
            box("under light", 26, 137, z0 - 0.3, 29, 467, z0, glow("led", (1, 0.85, 0.68), 2.6))
    elif uppers == "shelf":
        shelf = shelf or top
        boxes("shelves", [(0, 137, 158, 27, 467, 162), (0, 137, 196, 27, 467, 200)], shelf, 0.15)
    if hood == "flat":
        box("hood", 0, hy0 - 1, 150, 40, hy1 + 1, 216, hood_mat, 0.2)
    elif hood == "chimney":
        box("hood canopy", 0, hy0 - 6, 158, 50, hy1 + 6, 164, hood_mat, 0.2)
        box("hood chimney", 0, hy0 + 14, 164, 28, hy1 - 14, H, hood_mat, 0.2)
    elif hood == "mantle":
        box("hood mantle", 0, hy0 - 5, 165, 48, hy1 + 5, 216, hood_mat, 0.3)
        box("hood shelf", 0, hy0 - 8, 216, 52, hy1 + 8, 220, hood_mat, 0.5)
        box("hood rail", 44, hy0 - 6, 165, 49, hy1 + 6, 169, handle_mat, 0.3)


# ---------------------------------------------------------------- upholstery and tables
def leg_pos(w, d, inset):
    return [(s * (w / 2 - inset), t * (d / 2 - inset)) for s in (-1, 1) for t in (-1, 1)]


def sofa(cx, cy, w, d, face, fabric, leg, legs="block", seat=42, back=80, arm=13, n=3, cushions=True):
    """A sofa to the plan's footprint: w along its back, d front to back."""
    g = group("sofa", cx, cy, face)
    lh = 15 if legs in ("taper", "metal") else 6
    if legs == "taper":
        for x, y in leg_pos(w, d, 10):
            cyl("leg", x, y, 0, lh, 1.2, 2.3, leg, g, world=False)
    elif legs == "metal":
        for sx in (-1, 1):
            c = sx * (w / 2 - 10)
            lbox(g, "leg", c - 1, -d / 2 + 4, 0, c + 1, d / 2 - 4, 2, leg, 0.2)
            lbox(g, "leg", c - 1, -d / 2 + 4, 0, c + 1, -d / 2 + 6, lh, leg, 0.2)
            lbox(g, "leg", c - 1, d / 2 - 6, 0, c + 1, d / 2 - 4, lh, leg, 0.2)
    else:
        lbox(g, "plinth", -w / 2 + 6, -d / 2 + 6, 0, w / 2 - 6, d / 2 - 6, lh, leg, 0.2)
    base_top = seat - 15
    lbox(g, "base", -w / 2, -d / 2 + 2, lh, w / 2, d / 2, base_top, fabric, 2.5)
    soft(g, "back", (0, d / 2 - 8, (lh + back) / 2), (w, 16, back - lh), fabric, puff=0.03, edge=5)
    for sx in (-1, 1):
        soft(g, "arm", (sx * (w / 2 - arm / 2), 2, (lh + seat + 18) / 2), (arm, d - 4, seat + 18 - lh), fabric, puff=0.03, edge=5)
    inner = w - 2 * arm
    cw = inner / n
    for i in range(n):
        cx_ = -inner / 2 + cw * (i + 0.5)
        soft(g, "seat", (cx_, -d / 2 + (d - 16) / 2 + 1, seat - 6), (cw - 0.6, d - 17, 17), fabric, puff=0.06, edge=4.5)
        if cushions:
            soft(g, "back cushion", (cx_, d / 2 - 22, seat + 18), (cw - 0.6, 19, back - seat - 2), fabric, tilt=-9, puff=0.1, edge=5)
    return g


def pillow(cx, cy, z, face, mat, size=45, lean=-22):
    g = group("pillow", cx, cy, face, z)
    soft(g, "pillow", (0, 0, 0), (size, 15, size), mat, tilt=lean, puff=0.24, edge=5)


def table(x, y, w, d, top, leg, kind="square", h=75, thick=4):
    box("table top", x, y, h - thick, x + w, y + d, h, top, 0.25)
    if kind == "sled":
        for lx in (x + 16, x + w - 16):
            boxes("table leg", [(lx - 2, y + 6, 0, lx + 2, y + d - 6, 3), (lx - 2, y + 6, 0, lx + 2, y + 10, h - thick),
                                (lx - 2, y + d - 10, 0, lx + 2, y + d - 6, h - thick),
                                (lx - 2, y + 6, h - thick - 3, lx + 2, y + d - 6, h - thick)], leg, 0.2)
    elif kind == "taper":
        for sx, sy in ((x + 9, y + 9), (x + w - 9, y + 9), (x + 9, y + d - 9), (x + w - 9, y + d - 9)):
            cyl("table leg", sx, sy, 0, h - thick, 1.4, 3, leg)
    else:
        lt = 2.5 if kind == "thin" else 3.5
        i = 6
        boxes("table leg", [(ax, ay, 0, ax + 2 * lt, ay + 2 * lt, h - thick)
                            for ax in (x + i, x + w - i - 2 * lt) for ay in (y + i, y + d - i - 2 * lt)], leg, 0.15)


def chair(cx, cy, face, seat, frame, kind="min"):
    g = group("chair", cx, cy, face)
    if kind == "metal":
        for x, y in leg_pos(42, 42, 2):
            lbox(g, "leg", x - 1, y - 1, 0, x + 1, y + 1, 44, frame, 0.15)
        lbox(g, "seat", -22, -21, 44, 22, 21, 47, seat, 0.5)
        lbox(g, "upright", -21, 19, 44, -19, 21, 84, frame, 0.15)
        lbox(g, "upright", 19, 19, 44, 21, 21, 84, frame, 0.15)
        lbox(g, "back", -21, 19.2, 68, 21, 20.8, 83, seat, 0.4)
        return g
    if kind == "mid":
        for x, y in leg_pos(44, 42, 4):
            leg = cyl("leg", x, y, 0, 42, 1.0, 1.7, frame, g, world=False)
            leg.rotation_euler = (math.radians(4 if y < 0 else -4), math.radians(-4 if x < 0 else 4), 0)
        soft(g, "seat", (0, 0, 45), (46, 44, 6), seat, puff=0.05, edge=2.4)
        soft(g, "back", (0, 20, 69), (43, 5, 24), seat, tilt=-9, puff=0.05, edge=2)
        lbox(g, "upright", -14, 19, 42, -12.5, 21, 62, frame, 0.3)
        lbox(g, "upright", 12.5, 19, 42, 14, 21, 62, frame, 0.3)
        return g
    for x, y in leg_pos(44, 42, 3):
        cyl("leg", x, y, 0, 43, 1.0, 1.4, frame, g, world=False)
    lbox(g, "seat", -22, -21, 43, 22, 21, 46, seat, 0.9)
    lbox(g, "back", -21, 19, 66, 21, 21, 82, seat, 0.9)
    for x in (-19, 19):
        cyl("upright", x, 20, 46, 72, 0.9, 0.9, frame, g, world=False)
    return g


def chairs(fn):
    """Six chairs in the plan's positions round the table: fn(cx, cy, face)."""
    tx, ty = SC["table"][:2]
    for a, b in ((7, 52), (70, 115), (127, 173)):
        cx = tx + (a + b) / 2
        fn(cx, ty - 17.5, "s")
        fn(cx, ty + 100, "n")


def rug(x0, y0, x1, y1, mat):
    box("rug", x0, y0, 0, x1, y1, 1.6, mat, 0.5)


def curtain(a, b, mat, z0=1, z1=None, pleats=9, amp=4.5, rod=None):
    """Pleated curtain between plan points a and b."""
    z1 = z1 or H - 3
    (ax, ay), (bx, by) = a, b
    length = math.hypot(bx - ax, by - ay)
    tx, ty = (bx - ax) / length, (by - ay) / length
    nx, ny = -ty, tx
    n = pleats * 10
    bm = bmesh.new()
    rows = []
    for z in (z0, z1):
        row = []
        for i in range(n + 1):
            t = i / n
            off = amp * math.sin(t * math.pi * 2 * pleats) * (1.0 if z == z1 else 1.12)
            row.append(bm.verts.new(P(ax + (bx - ax) * t + nx * off, ay + (by - ay) * t + ny * off, z)))
        rows.append(row)
    for i in range(n):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
    cube_uv(bm)
    link(_finish("curtain", bm, mat, smooth=True))
    if rod:
        box("curtain track", ax - 3 * tx, ay - 3 * ty, H - 3, bx + 3 * tx + 1, by + 3 * ty + 1, H, rod)


def art(x, y, z, w, h, wall, path, frame=None, depth=3):
    """A framed picture; (x, y) is on the wall face and z is its centre. wall is the way it faces."""
    g = group("art", x, y, wall, z)
    mat = picture(f"art {Path(path).stem}", path, w / 100, h / 100)
    lbox(g, "canvas", -w / 2, -depth, -h / 2, w / 2, 0, h / 2, mat)
    if frame:
        t = 2
        lbox(g, "frame", -w / 2 - t, -depth - 0.6, -h / 2 - t, -w / 2, 0, h / 2 + t, frame, 0.1)
        lbox(g, "frame", w / 2, -depth - 0.6, -h / 2 - t, w / 2 + t, 0, h / 2 + t, frame, 0.1)
        lbox(g, "frame", -w / 2, -depth - 0.6, -h / 2 - t, w / 2, 0, -h / 2, frame, 0.1)
        lbox(g, "frame", -w / 2, -depth - 0.6, h / 2, w / 2, 0, h / 2 + t, frame, 0.1)
    return g


def stack(x, y, z, palette, seed=2, n=3):
    """Books lying flat, as on a coffee table."""
    rng = random.Random(seed)
    for i in range(n):
        w, d, t = rng.uniform(22, 30), rng.uniform(16, 21), rng.uniform(2, 3.5)
        box("book", x - w / 2, y - d / 2, z, x + w / 2, y + d / 2, z + t, palette[i % len(palette)], 0.1)
        z += t
    return z


def table_lamp(x, y, z, shade, base):
    cyl("lamp body", x, y, z, z + 24, 6.5, 3.5, base)
    cyl("lamp shade", x, y, z + 22, z + 48, 16, 11, shade)
    lamp(x, y, z + 34, 12)


def flat_tv(x0, x1, y, z0, z1):
    box("tv", x0, y - 3.5, z0, x1, y, z1, color("tv", (0.006, 0.006, 0.007), 0.08, coat=1), 0.2)


# ---------------------------------------------------------------- plan furniture positions
TX, TY, TW, TD = SC["table"]
TC = (TX + TW / 2, TY + TD / 2)                 # table centre
SOFA = (592, 80.5, 216, 81)                     # x 484-700, y 40-121, back to the balcony wall
SOFA2 = (456, 197, 160, 80)                     # x 416-496, y 117-277, facing the coffee table
SIDE = (446, 76)                                # x 416-476, y 45-107
COFFEE = (604.5, 215)                           # x 555-654, y 185-245
TV_Y = 382                                      # bedroom 1 wall


def wall_panel(name, kind, a, b, mat, z0=0, z1=H, t=1.0):
    """A finish applied to a wall face: n = balcony wall, w = kitchen wall, s = bedroom wall."""
    if kind == "n":
        box(name, a, 0, z0, b, t, z1, mat)
    elif kind == "w":
        box(name, 0, a, z0, t, b, z1, mat)
    elif kind == "s":
        box(name, a, TV_Y - t, z0, b, TV_Y, z1, mat)


GEN = ASSETS / "generated"


def curtains(mat, rod=None, **kw):
    """Curtains parked either side of the balcony door W1 and window W2."""
    curtain((92, 5), (142, 5), mat, rod=rod, **kw)
    curtain((446, 5), (528, 5), mat, rod=rod, **kw)
    curtain((717, 50), (717, 94), mat, rod=rod, **kw)
    curtain((717, 246), (717, 300), mat, rod=rod, **kw)


# ---------------------------------------------------------------- the seven schemes
def style_modern():
    wall = color("wall", (0.86, 0.86, 0.85), 0.55)
    black = color("black steel", (0.018, 0.018, 0.02), 0.38, 0.6)
    oak = pbr("oak", "white_oak_veneer", tile=0.9, sat=0.75, val=0.98)
    shell(pbr("floor", "interior_tiles", val=0.92, sat=0.25, rough_mul=0.7, rot=45), wall, color("ceiling", (0.9, 0.9, 0.9), 0.6),
          skirt=color("skirt", (0.85, 0.85, 0.84), 0.5), frame=black, door=color("door", (0.84, 0.84, 0.83), 0.4))
    wall_panel("media wall", "s", 311, 725, pbr("media wall", "black_oak_veneer", tile=0.9, val=0.75, rot=90))
    marble = pbr("marble", "marble_01", rough=0.18, sat=0.3, val=1.1)
    graphite = color("graphite", (0.035, 0.037, 0.04), 0.38, coat=0.1)
    kitchen(graphite, marble, marble, black, handle="none", uppers="cab", upper=oak, tall=oak, hood="flat", hood_mat=graphite)
    table(TX, TY, TW, TD, oak, black, "sled")
    chairs(lambda x, y, f: place("dining_chair_02", x, y, face=f, d=50))
    for x in (TC[0] - 58, TC[0], TC[0] + 58):
        hang("modern_ceiling_lamp_01", x, TC[1], 148, black, h=78)
        lamp(x, TC[1], 158, 14)
    fabric = pbr("sofa fabric", "cotton_jersey", tile=0.26, sat=0.0, val=0.62, sheen=0.5, normal=2.5)
    sofa(*SOFA, "s", fabric, black, "metal")
    sofa(*SOFA2, "e", fabric, black, "metal", n=2)
    cush = pbr("cushion", "poly_wool_herringbone", tile=0.3, sat=0.0, val=0.35, sheen=0.4)
    cush2 = pbr("cushion light", "rough_linen", tile=0.3, sat=0.1, val=1.0, sheen=0.4)
    pillow(530, 92, 64, "s", cush)
    pillow(652, 92, 64, "s", cush2)
    pillow(458, 241, 64, "e", cush2)
    rug(470, 128, 716, 298, pbr("rug", "poly_wool_herringbone", tile=0.45, sat=0.1, val=0.55))
    place("coffee_table_round_01", *COFFEE, w=92)
    stack(COFFEE[0] - 8, COFFEE[1] + 4, 34.8, [color("b1", (0.02, 0.02, 0.02), 0.4), color("b2", (0.75, 0.74, 0.7), 0.5)])
    cyl("side table", *SIDE, 0, 50, 22, mat=black)
    table_lamp(*SIDE, 50, glow("shade", (1.0, 0.86, 0.68), 0.14), black)
    place("modern_wooden_cabinet", 587, 356, face="n", w=244, d=38, h=52, stretch=True)
    flat_tv(530, 660, 381, 92, 165)
    place("ceramic_vase_03", TC[0] + 6, TC[1], 75, h=34)
    place("ceramic_vase_02", 500, 356, 52, h=26)
    art(662, 1, 150, 90, 120, "s", GEN / "art_modern.png", black)
    curtains(sheer_mat("sheer", (0.86, 0.86, 0.85), 0.5), black)
    place("potted_plant_01", 92, 34, h=125)


def style_minimal():
    wall = color("wall", (0.86, 0.845, 0.815), 0.6)
    shell(pbr("floor", "plastered_wall_02", sat=0.35, val=1.25, tint=(0.96, 0.93, 0.88), rough_mul=0.6),
          wall, color("ceiling", (0.88, 0.875, 0.86), 0.6), skirt=None,
          frame=color("frame", (0.8, 0.79, 0.77), 0.4), door=wall)
    oak = pbr("oak", "white_oak_veneer", tile=0.9, sat=0.6, val=1.7)
    plaster = color("cabinet", (0.83, 0.815, 0.785), 0.42)
    top = color("worktop", (0.8, 0.79, 0.76), 0.28)
    kitchen(plaster, top, top, plaster, handle="none", uppers="none", hood="none", led=False, top_h=2.5)
    table(TX, TY, TW, TD, oak, oak, "thin", thick=3)
    pale = pbr("pale linen", "rough_linen", tile=0.3, sat=0.15, val=1.25)
    chairs(lambda x, y, f: chair(x, y, f, oak, oak, "min"))
    fabric = pbr("sofa fabric", "curly_teddy_natural", tile=0.2, sat=0.3, val=1.0, sheen=0.4, normal=0.8)
    sofa(*SOFA, "s", fabric, oak, "block", seat=38, back=68, arm=10, cushions=False)
    sofa(*SOFA2, "e", fabric, oak, "block", seat=38, back=68, arm=10, n=2, cushions=False)
    pillow(640, 96, 58, "s", pale, 50)
    box("coffee table", COFFEE[0] - 50, COFFEE[1] - 30, 22, COFFEE[0] + 50, COFFEE[1] + 30, 26, oak, 0.2)
    box("coffee base", COFFEE[0] - 30, COFFEE[1] - 18, 0, COFFEE[0] + 30, COFFEE[1] + 18, 22, plaster, 0.1)
    place("ceramic_vase_02", TC[0], TC[1], 75, h=30)
    place("ceramic_vase_04", COFFEE[0] + 22, COFFEE[1] - 4, 26, h=26)
    box("low bench", 449, 352, 28, 725, 381, 32, oak, 0.2)
    curtains(sheer_mat("sheer", (0.9, 0.885, 0.85), 0.42), amp=3)


def style_scandinavian():
    wall = color("wall", (0.87, 0.865, 0.84), 0.6)
    shell(pbr("floor", "wood_floor", sat=0.45, val=2.3, tint=(1.0, 0.95, 0.88), rot=90, rough_mul=0.85), wall,
          color("ceiling", (0.9, 0.89, 0.875), 0.6), skirt=color("skirt", (0.85, 0.84, 0.82), 0.5),
          frame=color("frame", (0.84, 0.83, 0.81), 0.4), door=color("door", (0.84, 0.83, 0.81), 0.45))
    oak = pbr("oak", "oak_veneer_01", tile=1.0, sat=0.7, val=1.1)
    tile = pbr("tile", "long_white_tiles", rough=0.2, sat=0.2, val=1.05)
    front = color("front", (0.82, 0.815, 0.79), 0.42)
    black = color("black", (0.02, 0.02, 0.022), 0.45)
    kitchen(front, oak, tile, oak, handle="knob", uppers="shelf", shelf=oak, hood="chimney",
            hood_mat=color("hood", (0.82, 0.81, 0.79), 0.42), led=False)
    for i, y in enumerate((150, 195, 240, 285)):
        place(("ceramic_vase_01", "ceramic_vase_02", "ceramic_vase_04", "ceramic_vase_02")[i], 13, y, 162, h=20)
    place("wooden_bowl_01", 13, 350, 162, w=26)
    table(TX, TY, TW, TD, oak, oak, "taper")
    chairs(lambda x, y, f: place("painted_wooden_chair_01", x, y, face=f, d=48))
    paper = glow("paper", (1.0, 0.93, 0.84), 0.14)
    for x in (TC[0] - 40, TC[0] + 40):
        ball("paper globe", x, TC[1], 178, 20, paper)
        tube("cable", [(x, TC[1], 198), (x, TC[1], H)], 0.3, black)
        lamp(x, TC[1], 178, 12)
    fabric = pbr("sofa fabric", "rough_linen", tile=0.24, sat=0.3, val=0.9, tint=(1.0, 0.95, 0.88), sheen=0.5, normal=3)
    sofa(*SOFA, "s", fabric, oak, "taper", arm=11)
    sofa(*SOFA2, "e", fabric, oak, "taper", arm=11, n=2)
    mustard = pbr("cushion mustard", "cotton_jersey", tile=0.3, tint=(0.82, 0.58, 0.2), val=1.2, sat=0.2)
    sage = pbr("cushion sage", "cotton_jersey", tile=0.3, tint=(0.5, 0.58, 0.48), val=1.2, sat=0.2)
    white = pbr("cushion teddy", "curly_teddy_natural", tile=0.17, sat=0.3, val=1.2, normal=0.8)
    pillow(528, 92, 64, "s", mustard)
    pillow(575, 92, 64, "s", white)
    pillow(658, 92, 64, "s", sage)
    pillow(458, 248, 64, "e", white)
    rug(468, 128, 716, 300, pbr("rug", "curly_teddy_natural", tile=0.22, sat=0.35, val=1.15, normal=0.7))
    table(COFFEE[0] - 50, COFFEE[1] - 30, 100, 60, oak, oak, "taper", h=40, thick=3)
    place("ceramic_vase_01", COFFEE[0] + 26, COFFEE[1], 40, h=24)
    place("wicker_basket_02", 470, 330, h=26, face="w")
    place("side_table_01", *SIDE, w=55)
    table_lamp(*SIDE, 55, glow("shade", (1.0, 0.88, 0.72), 0.14), color("lamp base", (0.8, 0.79, 0.76), 0.5))
    box("media bench", 470, 346, 30, 705, 381, 34, oak, 0.2)
    boxes("media bench legs", [(476, 350, 0, 480, 354, 30), (695, 350, 0, 699, 354, 30),
                               (476, 372, 0, 480, 376, 30), (695, 372, 0, 699, 376, 30)], oak)
    flat_tv(530, 650, 381, 80, 150)
    place("ceramic_vase_02", 500, 362, 34, h=24)
    place("ceramic_vase_04", 680, 362, 34, h=28)
    place("potted_plant_02", 92, 34, h=78)
    place("potted_plant_01", 288, 416, h=112)
    art(662, 1, 150, 70, 100, "s", GEN / "art_scandi.png", oak)
    curtains(sheer_mat("sheer", (0.9, 0.89, 0.86), 0.5))


def style_industrial():
    brick = pbr("brick", "red_brick_03", normal=1.3, val=0.9)
    plaster = pbr("wall", "brushed_concrete", val=2.5, sat=0.25)
    black = color("black steel", (0.02, 0.02, 0.022), 0.42, 0.7)
    concrete = pbr("ceiling", "brushed_concrete", val=2.2, sat=0.2)
    shell(pbr("floor", "concrete_floor_02", val=1.5, sat=0.4, rough_mul=0.7, coat=0.15), plaster, concrete,
          skirt=None, frame=black, door=color("door", (0.04, 0.04, 0.043), 0.4), ironmongery=black)
    wall_panel("brick", "w", 0, SC["y_store_wall"], brick, t=1.5)
    wall_panel("brick", "n", 0, SC["w1"][0], brick, t=1.5)
    wall_panel("brick", "n", SC["w1"][1], 725, brick, t=1.5)
    steel = color("brushed steel", (0.6, 0.6, 0.61), 0.3, 1)
    matte = color("matte black", (0.022, 0.022, 0.024), 0.5)
    kitchen(matte, steel, steel, steel, handle="bar", uppers="shelf", shelf=pbr("shelf", "wood_table_001", val=0.75), hood="chimney")
    boxes("shelf brackets", [(0, y, 150, 2, y + 2, 200) for y in (150, 300, 450)], black)
    for i, y in enumerate((165, 215, 265)):
        place(("ceramic_vase_02", "ceramic_vase_04", "brass_vase_01")[i], 13, y, 162, h=22)
    place("WoodenTable_01", TC[0], TC[1], w=TW, d=TD, h=75, stretch=True)
    wood = pbr("chair seat", "wood_table_001", tile=0.8, val=0.7)
    chairs(lambda x, y, f: chair(x, y, f, wood, black, "metal"))
    for x in (TC[0] - 56, TC[0] + 56):
        hang("hanging_industrial_lamp", x, TC[1], 158, black, h=112)
        lamp(x, TC[1], 170, 16)
    leather = pbr("leather", "fabric_leather_02", tile=0.8, val=1.05, rough_mul=0.8)
    sofa(*SOFA, "s", leather, black, "metal", arm=12)
    sofa(*SOFA2, "e", leather, black, "metal", arm=12, n=2)
    wool = pbr("cushion", "poly_wool_herringbone", tile=0.3, sat=0.2, val=0.5, sheen=0.3)
    pillow(528, 92, 64, "s", wool)
    pillow(458, 248, 64, "e", wool)
    rug(470, 128, 716, 298, pbr("rug", "hessian_230", tile=0.4, val=0.62, sat=0.6))
    place("industrial_coffee_table", *COFFEE, w=100, d=62, h=42, stretch=True)
    place("side_table_01", *SIDE, w=55)
    place("industrial_pipe_lamp", SIDE[0], SIDE[1], 55, h=44)
    place("drawer_cabinet", 650, 356, face="n", w=114, d=38, h=150, stretch=True)
    place("steel_frame_shelves_01", 385, 356, face="n", h=190)
    box("media bench", 455, 348, 42, 590, 381, 46, pbr("bench", "wood_table_001", val=0.75), 0.2)
    flat_tv(462, 586, 381, 72, 142)
    place("potted_plant_02", 92, 34, h=78)
    # exposed services, typical of a converted loft
    tube("conduit", [(0, 325, H - 16), (725, 325, H - 16)], 3.0, black)
    tube("conduit", [(30, 0, H - 9), (30, 587, H - 9)], 1.5, black)


def style_midcentury():
    wall = color("wall", (0.84, 0.825, 0.78), 0.55)
    walnut = pbr("walnut", "american_walnut_veneer", tile=0.9, val=1.0, sat=1.1)
    shell(pbr("floor", "rectangular_parquet", sat=0.85, val=0.98, rough_mul=0.8), wall, color("ceiling", (0.88, 0.87, 0.84), 0.6),
          skirt=walnut, frame=color("frame", (0.05, 0.035, 0.025), 0.45), door=walnut)
    wall_panel("accent wall", "s", 311, 725, color("olive", (0.21, 0.26, 0.17), 0.65))
    brass = color("brass", (0.8, 0.58, 0.28), 0.28, 1)
    tile = pbr("tile", "long_white_tiles", rough=0.12, tint=(0.25, 0.46, 0.46), sat=0.3)
    kitchen(walnut, color("worktop", (0.84, 0.82, 0.77), 0.3), tile, brass, handle="knob", uppers="cab", upper=walnut,
            hood="flat", hood_mat=color("hood", (0.84, 0.82, 0.77), 0.4), led=True)
    table(TX, TY, TW, TD, walnut, walnut, "taper", thick=3.5)
    ochre = pbr("seat", "cotton_jersey", tile=0.35, tint=(0.8, 0.52, 0.14), sat=0.2, val=1.2, sheen=0.4)
    chairs(lambda x, y, f: chair(x, y, f, ochre, walnut, "mid"))
    black = color("black", (0.02, 0.02, 0.02), 0.45)
    for x in (TC[0] - 36, TC[0] + 36):
        hang("modern_ceiling_lamp_01", x, TC[1], 150, black, h=85)
        lamp(x, TC[1], 162, 14)
    teal = pbr("sofa fabric", "cotton_jersey", tile=0.26, tint=(0.14, 0.34, 0.36), sat=0.25, val=1.35, sheen=0.6, normal=2.5)
    sofa(*SOFA, "s", teal, walnut, "taper", seat=41, back=76, arm=9)
    place("mid_century_lounge_chair", 456, 165, face="e", d=92)
    place("modern_arm_chair_01", 460, 252, face="e", d=88)
    rust = pbr("cushion", "velour_velvet", tile=0.3, tint=(0.62, 0.24, 0.1), sat=0.3, val=1.3)
    pillow(530, 92, 62, "s", rust)
    pillow(654, 92, 62, "s", ochre)
    rug(476, 128, 716, 298, pbr("rug", "wool_boucle", tile=0.5, tint=(0.8, 0.72, 0.58), sat=0.3, val=1.1))
    place("modern_coffee_table_01", *COFFEE, face=90, d=112)
    place("modern_wooden_cabinet", 587, 356, face="n", w=244, d=38, h=56, stretch=True)
    flat_tv(530, 650, 381, 92, 160)
    place("ceramic_vase_01", 494, 356, 56, h=30)
    place("brass_vase_01", 684, 356, 56, h=34)
    place("side_table_tall_01", *SIDE, h=58)
    table_lamp(*SIDE, 58, glow("shade", (1.0, 0.82, 0.58), 0.14), brass)
    art(662, 1, 150, 80, 100, "s", GEN / "art_mid.png", walnut)
    place("potted_plant_01", 92, 40, h=125)
    place("potted_plant_02", 286, 416, h=80)
    curtains(sheer_mat("curtain", (0.82, 0.76, 0.62), 0.72), brass)


def style_boho():
    plaster = pbr("wall", "clay_plaster", tint=(1.0, 0.88, 0.74), val=3.2, sat=0.5)
    shell(pbr("floor", "wood_floor_worn", sat=0.85, val=1.7, rot=90), plaster, color("ceiling", (0.9, 0.87, 0.81), 0.6),
          skirt=None, frame=color("frame", (0.13, 0.08, 0.05), 0.5), door=color("door", (0.32, 0.4, 0.34), 0.5))
    wall_panel("accent wall", "s", 311, 725, pbr("terracotta", "clay_plaster", tint=(0.85, 0.42, 0.26), val=2.6, sat=0.6))
    oak = pbr("oak", "oak_veneer_01", sat=1.0, val=0.85)
    sage = color("sage", (0.42, 0.5, 0.39), 0.5)
    tile = pbr("zellige", "long_white_tiles", rough=0.14, tint=(0.75, 0.6, 0.42), sat=0.4)
    brass = color("brass", (0.8, 0.58, 0.28), 0.3, 1)
    kitchen(sage, oak, tile, brass, handle="knob", uppers="shelf", shelf=oak, hood="chimney", hood_mat=sage, shaker=True, led=False)
    for i, y in enumerate((150, 195, 240, 285)):
        place(("ceramic_vase_04", "potted_plant_04", "brass_vase_01", "ceramic_vase_02")[i], 13, y, 162, h=22)
    place("potted_plant_04", 13, 300, 200, h=20)
    place("wicker_basket_02", 13, 360, 200, face="e", h=22)
    place("wooden_table_02", TC[0], TC[1], w=TW, d=TD, h=75, stretch=True)
    chairs(lambda x, y, f: place("painted_wooden_chair_02", x, y, face=f, h=92))
    place("wicker_basket_01", TC[0], TC[1], 75, w=36)
    rattan = pbr("rattan", "hessian_230", tile=0.16, tint=(0.8, 0.6, 0.36), val=1.1)
    for x in (TC[0] - 46, TC[0] + 46):
        cyl("rattan shade", x, TC[1], 158, 188, 26, 7, rattan, segs=48)
        tube("cable", [(x, TC[1], 188), (x, TC[1], H)], 0.3, color("cord", (0.1, 0.07, 0.05), 0.7))
        lamp(x, TC[1], 170, 14)
    place("vintage_day_bed", SOFA[0], SOFA[1] - 1, w=205)
    natural = pbr("sofa fabric", "hessian_230", tile=0.4, tint=(0.95, 0.85, 0.68), val=1.15, sat=0.5, sheen=0.3)
    sofa(*SOFA2, "e", natural, oak, "taper", n=2, arm=11)
    place("throw_pillows_01", 456, 205, 60, face="e", w=95)
    rug(468, 128, 716, 302, picture("kilim", GEN / "kilim.png", 2.48, 1.74, 4.68, -3.02, rough=0.9))
    place("WoodenTable_01", *COFFEE, w=118)
    place("side_table_01", *SIDE, w=55)
    table_lamp(*SIDE, 55, rattan, color("lamp base", (0.55, 0.3, 0.17), 0.5))
    place("wicker_basket_02", 700, 150, h=30, face="w")
    place("potted_plant_02", 92, 34, h=95)
    place("potted_plant_01", 345, 345, h=135)
    place("potted_plant_02", 288, 416, h=85)
    place("potted_plant_01", 716, 28, h=130)
    place("potted_plant_02", 400, 40, h=80, face="e")
    place("modern_wooden_cabinet", 610, 356, face="n", w=230, d=38, h=56, stretch=True)
    place("ceramic_vase_04", 540, 356, 56, h=30)
    place("wicker_basket_01", 660, 356, 56, w=36)
    art(590, 381, 160, 100, 100, "n", GEN / "art_boho.png", oak)
    curtains(sheer_mat("curtain", (0.88, 0.78, 0.6), 0.65), brass)


def style_traditional():
    wall = color("wall", (0.73, 0.71, 0.62), 0.55)
    trim = color("trim", (0.84, 0.82, 0.76), 0.4)
    gold = color("brass", (0.78, 0.58, 0.28), 0.25, 1)
    shell(pbr("floor", "herringbone_parquet", val=0.72, sat=0.9, rough_mul=1.15, coat=0.06), wall,
          color("ceiling", (0.88, 0.87, 0.83), 0.6), skirt=trim, frame=trim, door=trim, ironmongery=gold, skirt_h=18,
          rail=color("iron", (0.03, 0.03, 0.03), 0.4, 0.5))
    # dado rail, cornice and wall panels
    w = SC["living_w"]
    cornice = [(0, 0, H - 12, w, 4, H), (0, 0, H - 12, 4, SC["y_store_wall"], H), (w - 4, 0, H - 12, w, 382, H),
               (311, 378, H - 12, w, 382, H), (307, 382, H - 12, 311, 600, H)]
    boxes("cornice", cornice, trim, 0.6)
    frames = []
    for a, b in ((470, 560), (570, 640), (650, 720), (319, 380), (392, 460)):
        y = 380.2
        for z0, z1 in ((28, 88), (104, 232)):
            frames += [(a, y, z0, b, y + 1.8, z0 + 2.4), (a, y, z1 - 2.4, b, y + 1.8, z1),
                       (a, y, z0, a + 2.4, y + 1.8, z1), (b - 2.4, y, z0, b, y + 1.8, z1)]
    boxes("wall panels", frames, trim, 0.4)
    box("dado", 311, 379.6, 94, w, 382, 98, trim, 0.4)
    marble = pbr("marble", "marble_01", rough=0.16, sat=0.4, val=1.1)
    cream = color("cream", (0.74, 0.7, 0.6), 0.4)
    kitchen(cream, marble, marble, gold, handle="knob", uppers="cab", upper=cream, hood="mantle", hood_mat=cream, shaker=True)
    place("wooden_table_02", TC[0], TC[1], w=TW, d=TD, h=76, stretch=True)
    chairs(lambda x, y, f: place("dining_chair_02", x, y, face=f, d=50))
    hang("Chandelier_01", TC[0], TC[1], 176, gold, h=74)
    lamp(TC[0], TC[1], 205, 26, radius=14)
    hang("Chandelier_02", 590, 200, 186, gold, h=70)
    lamp(590, 200, 215, 22, radius=14)
    place("Sofa_01", SOFA[0], SOFA[1], w=205)
    place("ArmChair_01", 456, 158, face="e", w=76)
    place("ArmChair_01", 456, 252, face="e", w=76)
    velvet = pbr("velvet", "velour_velvet", tile=0.3, tint=(0.3, 0.05, 0.08), sat=0.3, val=0.6, sheen=0.5)
    pillow(530, 92, 66, "s", velvet)
    pillow(655, 92, 66, "s", velvet)
    place("gothic_coffee_table", *COFFEE, w=88)
    rug(470, 128, 716, 300, picture("persian", GEN / "persian.png", 2.46, 1.72, 4.70, -3.00, rough=0.9))
    place("ClassicConsole_01", 426, 352, face="n", w=150)
    place("ornate_mirror_01", 426, 381, 112, face="n", h=115)
    place("mantel_clock_01", 426, 350, 92.5, face="n", h=20)
    place("brass_vase_01", 366, 350, 92.5, h=38)
    place("vintage_cabinet_01", 684, 352, face="n", w=78, d=40, h=205, stretch=True)
    place("side_table_tall_01", *SIDE, h=62)
    table_lamp(*SIDE, 62, glow("shade", (1.0, 0.84, 0.62), 0.14), gold)
    place("fancy_picture_frame_01", 662, 3, 160, face="s", w=90)
    heavy = pbr("drape", "velour_velvet", tile=0.3, tint=(0.3, 0.05, 0.08), sat=0.3, val=0.8, sheen=0.5)
    curtains(heavy, gold, pleats=8, amp=5.5)
    place("potted_plant_02", 92, 34, h=80)


# exposure, white balance: dark finishes need more exposure, warm ones less correction
LOOK = {"modern": (2.8, 7300, 4), "minimal": (2.15, 7500, 5), "scandinavian": (2.8, 7500, 6),
        "industrial": (3.3, 7200, 30), "midcentury": (3.0, 7100, 10), "boho": (3.1, 7200, 26),
        "traditional": (2.55, 6900, 2)}

STYLES = {"modern": style_modern, "minimal": style_minimal, "scandinavian": style_scandinavian,
          "industrial": style_industrial, "midcentury": style_midcentury, "boho": style_boho,
          "traditional": style_traditional}

# camera in plan cm, the point it looks toward, lens in mm, vertical shift
VIEWS = {
    "lounge": dict(cam=(716, 332), look=(250, 8), lens=17, shift=-0.09),
    "dining": dict(cam=(118, 580), look=(262, 0), lens=18, shift=-0.07),
}


def camera(view, eye=EYE):
    v = VIEWS[view]
    cam = bpy.data.cameras.new("cam")
    cam.lens = v["lens"]
    cam.sensor_width = 36
    cam.shift_y = v["shift"]
    cam.clip_end = 100000
    ob = link(bpy.data.objects.new("cam", cam))
    a, b = P(*v["cam"], eye), P(*v["look"], eye)
    ob.location = a
    d = b - a
    ob.rotation_euler = (math.pi / 2, 0, math.atan2(-d.x, d.y))
    scene.camera = ob


def world(hdri, rot, strength, limit):
    w = bpy.data.worlds.new("sky")
    scene.world = w
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value[2] = math.radians(rot)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = _image(ASSETS / "hdri" / f"{hdri}.hdr")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    cap = nt.nodes.new("ShaderNodeVectorMath")
    cap.operation = "MINIMUM"
    cap.inputs[1].default_value = (limit, limit, limit)
    nt.links.new(env.outputs[0], cap.inputs[0])
    nt.links.new(cap.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])


def settings(a):
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = a.res
    r.resolution_percentage = 100
    r.filepath = str(a.out)
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    c = scene.cycles
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    c.device = "GPU"
    c.samples = a.samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.012
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.max_bounces = 14
    c.diffuse_bounces = 8
    c.glossy_bounces = 4
    c.transparent_max_bounces = 12
    c.transmission_bounces = 6
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 25
    v = scene.view_settings
    v.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            v.look = look
            break
        except TypeError:
            continue
    v.exposure = a.exposure
    v.use_white_balance = True
    v.white_balance_temperature = a.wb


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--style", choices=STYLES, required=True)
    p.add_argument("--view", choices=VIEWS, default="lounge")
    p.add_argument("--samples", type=int, default=256)
    p.add_argument("--res", type=int, nargs=2, default=(1920, 1200))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--exposure", type=float, default=None)
    p.add_argument("--hdri", default="kloofendal_48d_partly_cloudy_puresky")
    p.add_argument("--sun", type=float, default=0.0, help="sky rotation in degrees")
    p.add_argument("--strength", type=float, default=1.0)
    p.add_argument("--no-portal", action="store_true")
    p.add_argument("--wb", type=float, default=None, help="white balance, kelvin")
    p.add_argument("--sun-limit", type=float, default=100000, help="caps the sun disc, to spare pale fabrics")
    p.add_argument("--fill", type=float, default=None, help="ceiling fill light, watts")
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    a.exposure = LOOK[a.style][0] if a.exposure is None else a.exposure
    a.wb = LOOK[a.style][1] if a.wb is None else a.wb
    fill(LOOK[a.style][2] if a.fill is None else a.fill)
    GLASS_DIM[0] = 0.44 * 2 ** ((2.8 - a.exposure) / 2)   # same view whatever the room's exposure
    STYLES[a.style]()
    if not a.no_portal:
        portal(*SC["w1"], "n")
        portal(*SC["w2"], "e")
    world(a.hdri, a.sun, a.strength, a.sun_limit)
    camera(a.view)
    settings(a)
    bpy.ops.render.render(write_still=True)
    print("rendered", a.out)


main()
