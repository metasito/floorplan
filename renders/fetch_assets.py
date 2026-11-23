#!/usr/bin/env python3
"""Download the CC0 Poly Haven kit used by render_interiors.py.

Usage: python3 -I fetch_assets.py <assets_dir>
Models come as glTF (no embedded scripts), materials as JPG maps, the sky as HDR.
Already-downloaded files are skipped, so the script can be re-run safely.
"""
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = "unit13-floorplan-renders/1.0"
API = "https://api.polyhaven.com/files/"

MODELS = """
dining_chair_02 painted_wooden_chair_01 painted_wooden_chair_02 modern_arm_chair_01
mid_century_lounge_chair ArmChair_01 GreenChair_01 Sofa_01 vintage_day_bed
WoodenTable_01 wooden_table_02 painted_wooden_table modern_coffee_table_01
coffee_table_round_01 CoffeeTable_01 industrial_coffee_table gothic_coffee_table
side_table_01 side_table_tall_01 modern_ceiling_lamp_01 Chandelier_01 Chandelier_02
hanging_industrial_lamp industrial_pipe_lamp potted_plant_01 potted_plant_02
potted_plant_04 throw_pillows_01 decorative_book_set_01 wicker_basket_01
wicker_basket_02 ceramic_vase_01 ceramic_vase_02 ceramic_vase_03 ceramic_vase_04
hanging_picture_frame_01 fancy_picture_frame_01 ornate_mirror_01 ClassicConsole_01
modern_wooden_cabinet vintage_cabinet_01 drawer_cabinet steel_frame_shelves_01
wooden_display_shelves_01 mantel_clock_01 brass_vase_01 wooden_bowl_01
pachira_aquatica_01 anthurium_botany_01 calathea_orbifolia_01 fern_02 planter_pot_clay
outdoor_table_chair_set_01 lambis_shell wooden_candlestick standing_picture_frame_02
wooden_bowl_02 wooden_cutting_board lemon wine_bottles_01 book_encyclopedia_set_01
folding_wooden_stool food_pomegranate_01 metal_jug
""".split()

TEXTURES = """
interior_tiles smooth_concrete_floor wood_floor concrete_floor_02 rectangular_parquet
wood_floor_worn herringbone_parquet large_grey_tiles
plastered_wall_02 painted_plaster_wall clay_plaster red_brick_03 brushed_concrete
white_oak_veneer oak_veneer_01 american_walnut_veneer smoked_walnut_veneer
rosewood_veneer1 ash_veneer black_oak_veneer wood_table_001
marble_01 long_white_tiles terrazzo_tiles
wool_boucle curly_teddy_natural cotton_jersey hessian_230 rough_linen velour_velvet
poly_wool_herringbone brown_leather fabric_leather_02 leather_white
laminate_floor_02 plastered_wall_04 white_stucco rounded_square_tiled_wall terracotta_floor_tiles
mixed_stone_tiles knitted_fleece waffle_pique_cotton terry_cloth fabric_pattern_05 kitchen_wood
oak_veneer_05 floor_tiles_06
""".split()

HDRIS = ["kloofendal_48d_partly_cloudy_puresky", "qwantani_afternoon_puresky", "belfast_sunset_puresky",
         "industrial_sunset_02_puresky", "kloofendal_43d_clear_puresky"]

# Map names differ between assets, so each role lists the names to try in order.
ROLES = {"diffuse": ("Diffuse", "diff"), "rough": ("Rough", "rough"), "normal": ("nor_gl",)}


def api(asset):
    req = urllib.request.Request(API + asset, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get(url, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.rename(dest)


def fetch_model(root, name):
    files = api(name)["gltf"]
    res = "2k" if "2k" in files else sorted(files)[0]
    entry = files[res]["gltf"]
    base = root / "models" / name
    get(entry["url"], base / f"{name}.gltf")
    for rel, info in entry.get("include", {}).items():
        get(info["url"], base / rel)
    return name


DIMS = {}


def fetch_texture(root, name):
    req = urllib.request.Request("https://api.polyhaven.com/info/" + name, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        DIMS[name] = json.load(r).get("dimensions")
    files = api(name)
    base = root / "textures" / name
    for role, keys in ROLES.items():
        for key in keys:
            if key in files:
                res = "2k" if "2k" in files[key] else sorted(files[key])[0]
                get(files[key][res]["jpg"]["url"], base / f"{role}.jpg")
                break
        else:
            raise KeyError(f"{name}: no {role} map, has {sorted(files)}")
    return name


def fetch_hdri(root, name):
    get(api(name)["hdri"]["4k"]["hdr"]["url"], root / "hdri" / f"{name}.hdr")
    return name


def main():
    root = Path(sys.argv[1]).resolve()
    jobs = [(fetch_model, n) for n in MODELS] + [(fetch_texture, n) for n in TEXTURES] + [(fetch_hdri, n) for n in HDRIS]
    failed = []
    with ThreadPoolExecutor(8) as pool:
        futures = {pool.submit(fn, root, n): n for fn, n in jobs}
        for f, n in futures.items():
            try:
                f.result()
                print("ok", n, flush=True)
            except Exception as e:
                failed.append(n)
                print("FAILED", n, repr(e), flush=True)
    dims_path = Path(__file__).resolve().parent / "texture_dims.json"
    old = json.loads(dims_path.read_text()) if dims_path.exists() else {}
    old.update({k: v for k, v in DIMS.items() if v})
    dims_path.write_text(json.dumps(old, indent=0))
    print(f"done: {len(jobs) - len(failed)} of {len(jobs)}; failed: {failed}")


if __name__ == "__main__":
    main()
