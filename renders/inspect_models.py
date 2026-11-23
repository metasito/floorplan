"""Report each model's size and render it from the front (-Y), to fix its facing.

Usage: blender -b --factory-startup --disable-autoexec --python inspect_models.py -- <assets_dir> <out_dir>
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

assets, out = (Path(p) for p in sys.argv[sys.argv.index("--") + 1:])
out.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
for o in list(bpy.data.objects):  # the factory scene has a cube that hides small models
    bpy.data.objects.remove(o, do_unlink=True)
sc.render.engine = "CYCLES"
sc.cycles.samples = 12
sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = 240
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = True
sc.cycles.device = "GPU"
world = bpy.data.worlds.new("w")
sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 60
sizes = {}
for path in sorted((assets / "models").glob("*/*.gltf")):
    name = path.stem
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    size = hi - lo
    centre = (lo + hi) / 2
    sizes[name] = {"size_cm": [round(v * 100, 1) for v in size], "lo_cm": [round(v * 100, 1) for v in lo]}
    r = max(size.length, 0.1) * 1.75
    # slightly raised, looking along +Y, so -Y faces the camera
    cam.location = centre + Vector((0, -r, r * 0.25))
    cam.rotation_euler = (math.atan2(r, r * 0.25), 0, 0)
    sc.render.filepath = str(out / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
(out / "sizes.json").write_text(json.dumps(sizes, indent=0))
print("inspected", len(sizes))
