"""Cameras, light moods and render settings for the warm scheme (design.py).

Usage:
  blender -b --factory-startup --disable-autoexec --python shoot.py -- \
      --views living_day kitchen_day --samples 1024 --res 3000 2000 --out out_warm

One Blender process builds the apartment once and renders every view asked for (views must
share a mood). Stills are two-point perspective (level camera, lens shift), panoramas are
equirectangular for the tour, and cutaway views clip everything above a plane.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402

scene = bpy.context.scene

# camera (plan cm, height), target, lens mm, vertical shift, mood, exposure offset
VIEWS = {
    "living_day": dict(cam=(108, 372, 116), look=(600, 60, 108), lens=18, shift=-0.08, mood="day"),
    "living_dusk": dict(cam=(694, 336, 120), look=(170, 10, 112), lens=19, shift=-0.03, mood="dusk"),
    "kitchen_day": dict(cam=(405, 115, 120), look=(0, 470, 110), lens=19, shift=-0.03, mood="day"),
    "hall": dict(cam=(252, 1300, 140), look=(252, 0, 130), lens=19, shift=-0.05, mood="day", ev=0.2,
                 roles=dict(down=0.8)),
    "bedroom1": dict(cam=(705, 742, 140), look=(420, 430, 112), lens=18, shift=-0.05, mood="day", ev=0.2),
    "bedroom2": dict(cam=(345, 1250, 130), look=(610, 1110, 112), lens=17, shift=-0.06, mood="day", ev=0.2,
                     roles=dict(pendant=0.0)),
    "bath1": dict(cam=(372, 806, 150), look=(612, 905, 112), lens=16, shift=-0.07, mood="day", ev=0.0,
                  roles=dict(down=0.6, mirror=1.0)),
    "bath2": dict(cam=(168, 905, 150), look=(30, 1070, 108), lens=15, shift=-0.08, mood="day", ev=0.1,
                  roles=dict(down=1.0, mirror=1.2)),
    "balcony_a": dict(cam=(40, -125, 138), look=(700, -40, 110), lens=20, shift=-0.05, mood="dusk", outside=True),
    "balcony_b": dict(cam=(742, 1350, 140), look=(690, 800, 112), lens=20, shift=-0.04, mood="dusk", outside=True),
    "cutaway": dict(cam=(1500, 2350, 1500), look=(360, 620, 0), lens=55, mood="day", cut=150, outside=True, ev=-0.6),
    "topplan": dict(cam=(370, 620, 2500), look=(370, 620, 0), ortho=1650, mood="day", cut=150, outside=True, ev=-0.6),
}
PANOS = {
    "pano_living": dict(cam=(372, 250, 150), mood="day"),
    "pano_dining": dict(cam=(205, 440, 150), mood="day"),
    "pano_hall": dict(cam=(250, 1215, 150), mood="day", ev=0.2, roles=dict(down=0.8)),
    "pano_bedroom1": dict(cam=(520, 660, 150), mood="day", ev=0.2),
    "pano_bedroom2": dict(cam=(460, 1185, 150), mood="day", ev=0.2, roles=dict(pendant=0.0)),
    "pano_bath1": dict(cam=(468, 875, 150), mood="day", ev=0.2, roles=dict(down=0.6, mirror=1.0)),
    "pano_bath2": dict(cam=(95, 960, 150), mood="day", ev=0.1, roles=dict(down=1.0, mirror=1.2)),
    "pano_balcony": dict(cam=(390, -86, 150), mood="dusk", outside=True),
}
ALL = {**VIEWS, **PANOS}

# light balance per mood: role multipliers; "day" leaves the warm lamps glowing softly
MOODS = {
    "day": dict(hdri="kloofendal_48d_partly_cloudy_puresky", strength=1.0, limit=6.0, rot=200, sun=4.2, sun_k=5400,
                sun_az=55, sun_el=30, ev=2.75, wb=4000, tint=-14,
                roles=dict(table=0.45, pendant=0.15, down=0.0, strip=0.45, mirror=0.5, outdoor=0.0)),
    "golden": dict(hdri="industrial_sunset_02_puresky", strength=1.1, limit=10000, rot=40, sun=0.0, sun_k=3800,
                   sun_az=0, sun_el=0, ev=1.0, wb=4600, tint=-6,
                   roles=dict(table=1.0, pendant=1.0, down=0.6, strip=1.0, mirror=1.0, outdoor=1.0)),
    "dusk": dict(hdri="belfast_sunset_puresky", strength=0.4, limit=10000, rot=150, sun=0.0, sun_k=3800,
                 sun_az=0, sun_el=0, ev=1.0, wb=4300, tint=-6,
                 roles=dict(table=1.25, pendant=1.15, down=0.45, strip=1.1, mirror=1.0, outdoor=1.0)),
}


def P(x, y, z=0.0):
    return Vector((x / 100, -y / 100, z / 100))


def world(mood):
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
    mp.inputs["Rotation"].default_value[2] = math.radians(mood["rot"])
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(kit.ASSETS / "hdri" / f"{mood['hdri']}.hdr"), check_existing=True)
    cap = nt.nodes.new("ShaderNodeVectorMath")
    cap.operation = "MINIMUM"
    cap.inputs[1].default_value = (mood["limit"],) * 3
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = mood["strength"]
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    nt.links.new(env.outputs[0], cap.inputs[0])
    nt.links.new(cap.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    if mood["sun"]:
        import design
        li = bpy.data.lights.new("sun", "SUN")
        li.energy = mood["sun"]
        li.angle = math.radians(1.2)
        li.color = design.kelvin(mood["sun_k"])
        ob = bpy.data.objects.new("sun", li)
        scene.collection.objects.link(ob)
        # azimuth in the plan: 0 = toward the top of the sheet (the sea), 90 = to the right
        az, el = math.radians(mood["sun_az"]), math.radians(mood["sun_el"])
        to_sun = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        ob.rotation_euler = to_sun.to_track_quat("Z", "Y").to_euler()


def portals():
    """Guide Cycles' sky sampling through every window: most interior noise goes."""
    SC = kit.SC
    LW, XL = SC["living_w"], SC["x_lower"]
    specs = [("n", *SC["w1"], 0, kit.HEAD, 0), ("e", *SC["w2"], LW, kit.HEAD, 0), ("e", *SC["w3"], LW, kit.HEAD, 0),
             ("e", *SC["w5"], XL, kit.HEAD, 0), ("e", *SC["w4"], XL, 215, 115)]
    for kind, a, b, wpos, head, z0 in specs:
        li = bpy.data.lights.new("portal", "AREA")
        li.shape = "RECTANGLE"
        li.cycles.is_portal = True
        ob = bpy.data.objects.new("portal", li)
        scene.collection.objects.link(ob)
        li.size, li.size_y = (b - a) / 100, (head - z0) / 100
        if kind == "n":
            ob.location = P((a + b) / 2, 2, (head + z0) / 2)
            ob.rotation_euler = (math.radians(-90), 0, 0)
        else:
            ob.location = P(wpos - 2, (a + b) / 2, (head + z0) / 2)
            ob.rotation_euler = (math.radians(90), 0, math.radians(90))


def balance(mood, override=None):
    import design
    roles = dict(mood["roles"])
    roles.update(override or {})
    for ob, role, watts in design.LIGHTS:
        ob.data.energy = watts * roles.get(role, 1.0)
        ob.hide_render = ob.data.energy <= 0


def camera(v, pano=False):
    cam = bpy.data.cameras.new("cam")
    cam.clip_start = 0.05
    cam.clip_end = 1000
    ob = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(ob)
    a = P(*v["cam"])
    ob.location = a
    if pano:
        cam.type = "PANO"
        cam.panorama_type = "EQUIRECTANGULAR"
        ob.rotation_euler = (math.pi / 2, 0, 0)        # level, facing the top of the sheet
    elif v.get("ortho"):
        cam.type = "ORTHO"
        cam.ortho_scale = v["ortho"] / 100
        ob.rotation_euler = (0, 0, 0)
    else:
        cam.lens = v["lens"]
        cam.sensor_width = 36
        cam.shift_y = v.get("shift", 0.0)
        d = P(*v["look"]) - a
        if v.get("cut") or v.get("tilt"):               # a bird's-eye view tilts; interiors stay level
            ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        else:
            ob.rotation_euler = (math.pi / 2, 0, math.atan2(-d.x, d.y))
    scene.camera = ob
    return ob


def cut_above(z_cut):
    """Clip the model at z_cut: everything above turns transparent; cut solids show a dark
    section where their insides would be. Scans and curtains get the clip only."""
    open_names = ("curtain", "glass", "sea", "rail glass", "juliet glass", "shower glass")
    capped = set()
    for ob in scene.collection.objects:
        if ob.type == "MESH" and not any(ob.name.startswith(n) for n in open_names):
            for s in ob.material_slots:
                if s.material:
                    capped.add(s.material.name)
    for mat in bpy.data.materials:
        nt = mat.node_tree
        if nt is None:
            continue
        for out in [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"]:
            if not out.inputs["Surface"].links:
                continue
            src = out.inputs["Surface"].links[0].from_socket
            n, l = nt.nodes, nt.links
            geo = n.new("ShaderNodeNewGeometry")
            sep = n.new("ShaderNodeSeparateXYZ")
            l.new(geo.outputs["Position"], sep.inputs[0])
            gt = n.new("ShaderNodeMath")
            gt.operation = "GREATER_THAN"
            gt.inputs[1].default_value = z_cut / 100
            l.new(sep.outputs["Z"], gt.inputs[0])
            shader = src
            if mat.name in capped:
                capd = n.new("ShaderNodeBsdfDiffuse")
                capd.inputs[0].default_value = (0.045, 0.043, 0.042, 1)
                mx = n.new("ShaderNodeMixShader")
                l.new(geo.outputs["Backfacing"], mx.inputs[0])
                l.new(src, mx.inputs[1])
                l.new(capd.outputs[0], mx.inputs[2])
                shader = mx.outputs[0]
            tr = n.new("ShaderNodeBsdfTransparent")
            mx2 = n.new("ShaderNodeMixShader")
            l.new(gt.outputs[0], mx2.inputs[0])
            l.new(shader, mx2.inputs[1])
            l.new(tr.outputs[0], mx2.inputs[2])
            l.new(mx2.outputs[0], out.inputs["Surface"])
    for ob in scene.objects:
        if ob.type == "LIGHT" and ob.data.type != "SUN" and ob.location.z * 100 > z_cut:
            ob.hide_render = True


def backdrop():
    """For cutaways: a soft warm-grey ground instead of the sea, like a model on a table."""
    import design
    bpy.data.objects["sea"].hide_render = True
    design.box("ground", -3000, -3000, -33, 4000, 4000, -31, design.color("ground", design.srgb("#ddd8cf"), 0.9))


def settings(a, v, mood, pano):
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = a.pano_res if pano else a.res
    if v.get("ortho"):
        r.resolution_x = r.resolution_y = a.res[1]
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "16"
    c = scene.cycles
    kit.use_gpu(scene)
    c.samples = a.pano_samples if pano else a.samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = a.noise
    c.adaptive_min_samples = min(64, c.samples)
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    for attr, val in (("denoising_prefilter", "ACCURATE"), ("denoising_quality", "HIGH")):
        try:
            setattr(c, attr, val)
        except (AttributeError, TypeError):
            pass
    c.max_bounces = 16
    c.diffuse_bounces = 7
    c.glossy_bounces = 5
    c.transmission_bounces = 10
    c.transparent_max_bounces = 24
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 12
    c.blur_glossy = 0.8
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = mood["ev"] + v.get("ev", 0.0) + a.ev
    vs.use_white_balance = True
    vs.white_balance_temperature = a.wb or mood["wb"]
    vs.white_balance_tint = a.tint if a.tint is not None else mood.get("tint", 0.0)


def custom_view(c):
    """Turn the editor's camera into a view. With level on, the camera is held level and the
    framing is kept with a lens shift, the way an architectural photographer keeps walls upright."""
    (x, y, z), (tx, ty, tz) = c["pos"], c["target"]
    lens = float(c.get("lens", 20))
    outside = y < -25 or (x > 635 and y > 780)
    v = dict(cam=(x, y, z), look=(tx, ty, tz), lens=lens, mood=c.get("mood", "day"), outside=outside,
             pano=bool(c.get("pano")), ev=float(c.get("ev", 0.0)))
    if c.get("level", True) and not v["pano"]:
        pitch = math.atan2(tz - z, math.hypot(tx - x, ty - y))
        v["shift"] = max(-0.6, min(0.6, math.tan(pitch) * lens / 36))
        v["look"] = (tx, ty, z)
    elif not v["pano"]:
        v["cut"] = None
        v["tilt"] = True
    if z > 280 and not v["pano"]:                        # from above: a cut-away of the whole flat
        v.update(cut=150, outside=True, tilt=True, look=(tx, ty, tz), ev=v["ev"] - 0.6)
        v.pop("shift", None)
    elif v["mood"] == "day" and not outside:
        v["roles"] = {"down": 0.6, "mirror": 1.0}           # inner rooms get their lights on
    name = c.get("name", "custom")
    ALL[name] = v
    return name


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--views", nargs="*", default=[])
    p.add_argument("--samples", type=int, default=1024)
    p.add_argument("--pano-samples", type=int, default=768)
    p.add_argument("--res", type=int, nargs=2, default=(3000, 2000))
    p.add_argument("--pano-res", type=int, nargs=2, default=(8192, 4096))
    p.add_argument("--noise", type=float, default=0.006)
    p.add_argument("--ev", type=float, default=0.0)
    p.add_argument("--wb", type=float, default=None)
    p.add_argument("--tint", type=float, default=None)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--save-blend", type=Path, default=None)
    p.add_argument("--config", type=Path, default=None, help="build from a configurator layout (catalog.py format)")
    p.add_argument("--cam", type=Path, default=None, help="a camera from the editor: JSON with pos, target, lens")
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cam:
        a.views = [custom_view(json.loads(a.cam.read_text()))]
    keys = {(ALL[nm]["mood"], ALL[nm].get("cut"), ALL[nm].get("outside", False)) for nm in a.views}
    if len(keys) > 1:
        sys.exit(f"views must share mood, cut and inside/outside in one process: {keys}")
    mood_name, cut, outside = keys.pop()
    mood = dict(MOODS[mood_name])
    if cut:                      # a high sun, so cut walls don't stripe the floors with shadow
        mood.update(sun_el=62, sun_az=35)
    kit.GLASS_DIM[0] = 0.92 if outside else (0.5 if mood_name == "day" else 0.85)
    import design
    if a.config:
        import configured
        configured.build_from_config(json.loads(a.config.read_text()))
    else:
        design.build()
    world(mood)
    if not outside:
        portals()
    balance(mood)
    if cut:
        cut_above(cut)
        backdrop()
    if a.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=str(a.save_blend))
    for nm in a.views:
        v = ALL[nm]
        pano = nm.startswith("pano_") or v.get("pano", False)
        for ob in [o for o in scene.objects if o.type == "CAMERA"]:
            bpy.data.objects.remove(ob, do_unlink=True)
        camera(v, pano)
        balance(mood, v.get("roles"))
        settings(a, v, mood, pano)
        scene.render.filepath = str(a.out / f"{nm}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", nm, flush=True)


main()
