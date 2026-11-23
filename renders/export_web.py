"""Export everything the browser editor needs as GLB: the shell, the kitchen in every upper/handle
combination, curtains per window, and one model per item kind and variant.

Usage: blender -b --factory-startup --disable-autoexec --python export_web.py -- <out_dir>

Materials are placeholders named for their role ("wall:living", "slot:fabric", "kitchen:fronts"),
so the editor can recolour them live from the configuration. Scanned models keep their own
textures, shrunk to 512 px. Items are exported at the origin facing down the sheet; size-driven
items (rugs, art, plants, decor, ledges) at a reference size the editor scales.
"""
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import configured as C  # noqa: E402
import design as D  # noqa: E402
from catalog import DEFAULT_FINISHES, HANDLES, KINDS, UPPERS  # noqa: E402

OUT = Path(sys.argv[sys.argv.index("--") + 1:][0]).resolve()
(OUT / "models").mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene

REF_SIZE = {"rug": (100, 100), "art": (50, 70), "plant": (0, 100), "decor": (0, 24), "cistern_wall": (100, 20),
            "bistro_set": (0, 86)}
REF_Z = {"pendant": 160}


def clear():
    for o in list(scene.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    D.LIGHTS.clear()


def realize():
    """Turn collection instances (scans) into real objects so they export."""
    inst = [o for o in scene.objects if o.instance_type == "COLLECTION" and o.instance_collection]
    if not inst:
        return
    bpy.ops.object.select_all(action="DESELECT")
    for o in inst:
        o.select_set(True)
    bpy.context.view_layer.objects.active = inst[0]
    bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)


def shrink_images(px=512):
    for im in bpy.data.images:
        if im.size[0] > px or im.size[1] > px:
            s = px / max(im.size)
            im.scale(max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s)))


def export(name):
    realize()
    for o in list(scene.objects):          # lights and the portal helpers stay out of the web model
        if o.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(o, do_unlink=True)
    path = OUT / "models" / f"{name}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_apply=True, export_lights=False,
                              export_cameras=False, export_image_format="JPEG", export_jpeg_quality=78,
                              export_yup=True, use_visible=False)
    clear()
    return path.name


manifest = {"shell": None, "kitchen": {}, "curtains": {}, "items": {}, "ref_size": REF_SIZE, "ref_z": REF_Z}
fin = json.loads(json.dumps(DEFAULT_FINISHES))
clear()

# shell and fixed parts
m = C.Mats(fin, export=True)
C.build_shell(m)
D.storage(m)
C.bathrooms_fixed(m)
C.fixed_lights(m)
shrink_images()
manifest["shell"] = export("shell")

# kitchen in every combination of uppers and handles
for u in UPPERS:
    for h in HANDLES:
        f = json.loads(json.dumps(fin))
        f["kitchen"]["uppers"], f["kitchen"]["handles"] = u, h
        m = C.Mats(f, export=True)
        C.kitchen(m)
        manifest["kitchen"][f"{u}|{h}"] = export(f"kitchen__{UPPERS.index(u)}_{HANDLES.index(h)}")

# curtains, one file per window
for w in C.CURTAINS:
    f = json.loads(json.dumps(fin))
    for k in f["curtains"]:
        f["curtains"][k]["on"] = k == w
    m = C.Mats(f, export=True)
    C.curtains(m)
    manifest["curtains"][w] = export(f"curtain_{w}")

# items
m = C.Mats(fin, export=True)
for kind, spec in KINDS.items():
    manifest["items"][kind] = {}
    for i, variant in enumerate(spec["variants"]):
        it = {"id": f"x{kind}{i}", "kind": kind, "variant": variant, "x": 0, "y": 0, "rot": 0,
              "z": REF_Z.get(kind, 0), "room": "bath1" if spec["cat"] == "Bathroom" else "living"}
        if kind in REF_SIZE:
            it["size"] = list(REF_SIZE[kind])
        try:
            C.BUILDERS[kind](m, it)
            shrink_images()
            manifest["items"][kind][variant] = export(f"{kind}__{i}")
        except Exception as e:
            print("export skipped", kind, variant, repr(e))
            clear()

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
print("exported", sum(len(v) for v in manifest["items"].values()), "item models")
