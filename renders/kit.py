"""Shared Blender helpers for the Unit 13 renders: units, materials, meshes, scanned models.

Plan coordinates are centimetres with y running down the sheet; Blender gets metres, y up.
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


def use_gpu(scene, gpu_only=True):
    """Render on the GPU with whatever backend this machine has (Metal on Mac, OptiX/CUDA on
    NVIDIA, HIP on AMD, oneAPI on Intel); fall back to the CPU when none works."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
        except TypeError:          # backend not built for this OS
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type != "CPU" if gpu_only else True
            scene.cycles.device = "GPU"
            print(f"Cycles device: {backend} ({', '.join(d.name for d in gpus)})", flush=True)
            return
    prefs.compute_device_type = "NONE"
    scene.cycles.device = "CPU"
    print("Cycles device: CPU (no supported GPU found; renders will be slower)", flush=True)


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


