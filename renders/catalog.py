"""The configurator's vocabulary: every kind of piece, its variants and its colour slots, the
finish options for walls, floors, kitchen and bathrooms, and the default layout (the warm scheme).

Pure Python, no Blender: design.py builds from it, export_web.py turns it into GLB models, and
`python catalog.py <out.json>` writes it for the browser editor.

Coordinates are plan centimetres (x right, y down the sheet), z is height above the floor, rot is
degrees: 0 = the piece's front faces down the sheet, 90 = it faces right, 180 up, -90 left.
"""
import json
import sys

WOODS = {
    "light oak": "#c9a57d", "natural oak": "#b08356", "smoked oak": "#6f5440", "walnut": "#5b3d2b",
    "white": "#ece7de", "black": "#262422",
}
METALS = {"brushed brass": "#c8a66a", "matt black": "#222222", "chrome": "#cfd2d4", "brushed steel": "#a5a7aa"}
FABRICS = ["#ddd3c2", "#efeae1", "#c9b8a0", "#a85f3d", "#c99540", "#9aa58d", "#5d6b54", "#7b8fa1", "#3f4a5c",
           "#d9a8a0", "#8a6f5a", "#4a4440"]
PAINTS = ["#ece6dc", "#f3f0ea", "#e6dccb", "#d9c8b0", "#c3a58a", "#cfa88c", "#b9774f", "#a9b29a", "#8f9a85",
          "#9fb0b5", "#7b8fa1", "#c9c3b8", "#5c5a56"]
TILES = ["#ddd0bd", "#ece4d6", "#f2f0ea", "#a3ae96", "#7f9a8c", "#9fb3bd", "#c98a6c", "#d6c3a3", "#5f6a72"]

# kind: label, category, mount (floor/wall/ceiling/surface), z default, variants, slots {name: (type, default)}
KINDS = {
    "sofa": dict(label="Sofa", cat="Living", variants={"3-seat 216": (216, 81, 3), "2-seat 160": (160, 80, 2),
                                                       "4-seat 250": (250, 92, 4), "armchair 88": (88, 82, 1)},
                 slots={"fabric": ("fabric", "#ddd3c2"), "legs": ("wood", "light oak")}),
    "lounge_chair": dict(label="Lounge chair", cat="Living",
                         variants={"mid-century": "mid_century_lounge_chair", "wood frame": "modern_arm_chair_01"}),
    "cushion": dict(label="Cushion", cat="Living", z=66, mount="surface",
                    variants={"square 48": 48, "square 42": 42, "large 55": 55},
                    slots={"fabric": ("fabric", "#a85f3d")}),
    "throw": dict(label="Throw", cat="Living", z=63, mount="surface", variants={"folded": (26, 60)},
                  slots={"fabric": ("fabric", "#c27850")}),
    "coffee_table": dict(label="Coffee table", cat="Living",
                         variants={"oval 104": "oval", "round 90": "round", "rectangle 110": "rect"},
                         slots={"wood": ("wood", "light oak")}),
    "side_table": dict(label="Side table", cat="Living", variants={"round": "round", "square two-tier": "square"},
                       slots={"wood": ("wood", "light oak")}),
    "media_unit": dict(label="Media unit", cat="Living",
                       variants={"cane 276": (276, True), "cane 200": (200, True), "plain 240": (240, False),
                                 "plain 180": (180, False)},
                       slots={"wood": ("wood", "light oak")}),
    "tv": dict(label="TV", cat="Living", z=54, mount="surface", variants={"55 inch": 122, "65 inch": 144}),
    "floor_lamp": dict(label="Floor lamp", cat="Lighting", variants={"tripod linen": "tripod"},
                       slots={"wood": ("wood", "light oak"), "shade": ("fabric", "#efe4d2")}),
    "table_lamp": dict(label="Table lamp", cat="Lighting", z=52, mount="surface",
                       variants={"ball": "ball", "column": "cyl"},
                       slots={"base": ("paint", "#b4643e"), "shade": ("fabric", "#efe4d2")}),
    "pendant": dict(label="Pendant", cat="Lighting", z=160, mount="ceiling",
                    variants={"rattan dome": "dome", "rattan dome large": "dome_l", "rattan globe": "globe",
                              "paper globe": "paper", "white opal": "opal"}),
    "rug": dict(label="Rug", cat="Textiles", size=(200, 300),
                variants={"jute": "jute", "berber": "berber", "stripes": "stripes", "plain wool": "wool"},
                slots={"fabric": ("fabric", "#efeae1")}),
    "art": dict(label="Framed print", cat="Decor", z=150, mount="wall", size=(50, 70),
                variants={"arch": "print_arch", "olive branch": "print_olive", "shapes": "print_shapes",
                          "lines": "print_lines", "horizon": "print_horizon"},
                slots={"frame": ("wood", "light oak")}),
    "mirror": dict(label="Mirror", cat="Decor", z=150, mount="wall",
                   variants={"round 60": ("round", 30), "round 70": ("round", 35), "rectangle 86x78": ("rect", 86)},
                   slots={"frame": ("metal", "brushed brass")}),
    "plant": dict(label="Plant", cat="Plants", size=(0, 100),
                  variants={"money tree": ("pachira_aquatica_01", 0), "money tree small": ("pachira_aquatica_01", 1),
                            "leafy pot": ("potted_plant_01", None), "elephant ear": ("potted_plant_02", None),
                            "succulent": ("potted_plant_04", None), "calathea in pot": ("calathea_orbifolia_01", 0),
                            "fern": ("fern_02", 0), "anthurium in pot": ("anthurium_botany_01", 0)}),
    "decor": dict(label="Decor", cat="Decor", mount="surface", size=(0, 24),
                  variants={"vase tall": "ceramic_vase_03", "vase bottle": "ceramic_vase_01",
                            "vase round": "ceramic_vase_02", "jug": "ceramic_vase_04", "wooden bowl": "wooden_bowl_02",
                            "basket": "wicker_basket_02", "basket low": "wicker_basket_01",
                            "candlestick": "wooden_candlestick", "shell": "lambis_shell", "books": "books",
                            "fruit bowl": "fruit", "towel stack": "towels", "terracotta pot": "planter_pot_clay"}),
    "dining_table": dict(label="Dining table", cat="Dining",
                         variants={"rectangle 180x85": ("rect", 180, 85), "rectangle 160x80": ("rect", 160, 80),
                                   "round 120": ("round", 120, 120), "round 100": ("round", 100, 100)},
                         slots={"wood": ("wood", "light oak"), "runner": ("fabric", "#d9ccb6")}),
    "dining_chair": dict(label="Dining chair", cat="Dining",
                         variants={"oak spindle": "spindle", "upholstered": "dining_chair_02",
                                   "painted white": "painted_wooden_chair_01"},
                         slots={"wood": ("wood", "light oak"), "seat": ("fabric", "#d8c39c")}),
    "bed": dict(label="Bed", cat="Bedroom",
                variants={"double 180": (186, 210, 112), "double 160": (166, 210, 112), "single 90": (96, 196, 80)},
                slots={"headboard": ("fabric", "#d9ccb6"), "duvet": ("fabric", "#efeae1"),
                       "throw": ("fabric", "#c27850"), "pillows": ("fabric", "#a85f3d")}),
    "nightstand": dict(label="Nightstand", cat="Bedroom", variants={"one drawer": 50, "small": 38},
                       slots={"wood": ("wood", "light oak")}),
    "wardrobe": dict(label="Wardrobe", cat="Storage",
                     variants={"180 wide": (180, 3), "120 wide": (120, 2), "87 wide": (87, 1), "60 wide": (60, 1)},
                     slots={"fronts": ("paint", "#ebe5da"), "pulls": ("wood", "light oak")}),
    "dresser": dict(label="Chest of drawers", cat="Bedroom", variants={"122 wide": 122, "90 wide": 90},
                    slots={"wood": ("wood", "light oak")}),
    "desk": dict(label="Desk", cat="Bedroom", variants={"105 with drawers": 105, "120 plain": 120},
                 slots={"wood": ("wood", "light oak")}),
    "wall_shelf": dict(label="Wall shelf with books", cat="Storage", z=120, mount="wall",
                       variants={"100": 100, "60": 60}, slots={"wood": ("wood", "light oak")}),
    "desk_lamp": dict(label="Desk lamp", cat="Lighting", z=76, mount="surface", variants={"arm": "arm"},
                      slots={"metal": ("metal", "matt black")}),
    "hall_bench": dict(label="Hall bench", cat="Hall", variants={"110": 110, "80": 80},
                       slots={"wood": ("wood", "light oak"), "cushion": ("fabric", "#a85f3d")}),
    "hook_rail": dict(label="Hook rail", cat="Hall", z=163, mount="wall", variants={"4 hooks": 100},
                      slots={"wood": ("wood", "light oak")}),
    "wc": dict(label="WC, wall-hung", cat="Bathroom", variants={"rounded": "wc", "rounded bidet": "bidet"}),
    "cistern_wall": dict(label="Tiled cistern ledge", cat="Bathroom", size=(140, 20),
                         variants={"tiled": "tiled"}, slots={"top": ("paint", "#d9d0c2")}),
    "vanity": dict(label="Vanity with basin", cat="Bathroom",
                   variants={"72 single": (72, 46), "100 single": (100, 46), "160 long": (160, 45)},
                   slots={"wood": ("wood", "light oak"), "tap": ("metal", "brushed brass")}),
    "towel_rail": dict(label="Towel rail", cat="Bathroom", z=122, mount="wall", variants={"with towel": 26},
                       slots={"metal": ("metal", "brushed brass"), "towel": ("fabric", "#e9e1d3")}),
    "tall_cupboard": dict(label="Tall cupboard (boiler, washer)", cat="Bathroom", variants={"60x60": 60},
                          slots={"wood": ("wood", "light oak")}),
    "bistro_set": dict(label="Bistro table and chairs", cat="Outdoor", variants={"folding wood": "set"}),
    "bistro_table": dict(label="Bistro table", cat="Outdoor", variants={"round 56": 28},
                         slots={"wood": ("wood", "light oak")}),
    "stool": dict(label="Folding stool", cat="Outdoor", variants={"wood": "stool"}),
    "outdoor_bench": dict(label="Outdoor bench", cat="Outdoor", variants={"250": 250, "180": 180},
                          slots={"wood": ("wood", "light oak"), "cushion": ("fabric", "#d9ccb6")}),
    "lounger": dict(label="Lounger", cat="Outdoor", variants={"115": 115},
                    slots={"wood": ("wood", "light oak"), "cushion": ("fabric", "#d9ccb6")}),
}
CATEGORIES = ["Living", "Dining", "Lighting", "Textiles", "Decor", "Plants", "Bedroom", "Storage", "Hall",
              "Bathroom", "Outdoor"]

FLOORS = ["light oak", "natural oak", "oak herringbone", "light terrazzo", "polished concrete"]
WORKTOPS = ["oak", "white quartz", "terrazzo", "concrete"]
BATH_FLOORS = ["terrazzo", "stone", "light tile"]
BALCONY_FLOORS = ["terracotta", "grey stone", "wood decking"]
UPPERS = ["cupboards and shelves", "cupboards", "open shelves", "none"]
HANDLES = ["brass knobs", "black bars", "oak knobs", "handleless"]
MOODS = ["day", "dusk", "golden"]

DEFAULT_FINISHES = {
    "floor": "light oak",
    "walls": {"living": "#ece6dc", "hall": "#ece6dc", "storage": "#ece6dc", "bed1": "#ece6dc",
              "bed2": "#ece6dc", "bath1": "#ece5da", "bath2": "#ece5da"},
    "accents": {"living_tv": {"on": True, "color": "#c3a58a"}, "bed1_head": {"on": True, "color": "#a9b29a"},
                "bed2_band": {"on": True, "color": "#d0ad94"}},
    "ceiling": "#f1eee8", "skirting": "#ebe5db", "doors": "#eee9e0", "door_handles": "matt black",
    "frames": "#3c3f42",
    "kitchen": {"fronts": "#8f9a85", "uppers": "cupboards and shelves", "upper_color": "#ebe5da",
                "worktop": "oak", "splash": "#ece4d6", "handles": "brass knobs"},
    "bath1": {"tiles": "#ddd0bd", "floor": "terrazzo", "fittings": "brushed brass"},
    "bath2": {"tiles": "#a3ae96", "floor": "terrazzo", "fittings": "brushed brass"},
    "balconies": "terracotta",
    "curtains": {"W1": {"on": True, "style": "sheer", "color": "#eee6d8"},
                 "W2": {"on": True, "style": "sheer", "color": "#eee6d8"},
                 "W3": {"on": True, "style": "linen", "color": "#e3d8c6"},
                 "W5": {"on": True, "style": "linen", "color": "#e3d8c6"}},
}


def _items():
    L = []

    def add(kind, variant, x, y, rot=0, z=None, room="", slots=None, size=None):
        it = {"id": f"i{len(L) + 1}", "kind": kind, "variant": variant, "x": x, "y": y, "rot": rot,
              "z": KINDS[kind].get("z", 0) if z is None else z, "room": room}
        if slots:
            it["slots"] = slots
        if size:
            it["size"] = list(size)
        L.append(it)

    # living room
    add("sofa", "3-seat 216", 592, 81, 0, room="living")
    add("sofa", "2-seat 160", 456, 197, 90, room="living")
    add("cushion", "square 48", 522, 88, 0, 66, "living", {"fabric": "#a85f3d"})
    add("cushion", "square 48", 566, 90, 8, 66, "living", {"fabric": "#d9ccb6"})
    add("cushion", "square 48", 660, 88, -6, 66, "living", {"fabric": "#c99540"})
    add("cushion", "square 48", 452, 250, 90, 66, "living", {"fabric": "#9aa58d"})
    add("cushion", "square 42", 450, 150, 100, 66, "living", {"fabric": "#d9ccb6"})
    add("throw", "folded", 686, 80, 0, 63, "living")
    add("rug", "jute", 589, 221, 0, 0, "living", size=(254, 190))
    add("coffee_table", "oval 104", 604.5, 215, 0, room="living")
    add("decor", "books", 586.5, 221, 0, 40, "living")
    add("decor", "vase bottle", 628.5, 211, 0, 40, "living", size=(0, 24))
    add("decor", "shell", 586.5, 219, 0, 47, "living", size=(0, 16))
    add("side_table", "round", 446, 76, 0, room="living")
    add("table_lamp", "ball", 446, 72, 0, 52, "living")
    add("floor_lamp", "tripod linen", 698, 150, 0, room="living")
    add("media_unit", "cane 276", 587, 364.5, 180, room="living")
    add("tv", "55 inch", 567, 367.5, 180, 54, "living")
    add("decor", "vase round", 480, 364, 0, 50, "living", size=(0, 26))
    add("decor", "books", 668, 364, 0, 50, "living")
    add("plant", "elephant ear", 700, 364, 0, 50, "living", size=(0, 34))
    add("art", "arch", 565, 40, 0, 158, "living")
    add("plant", "money tree", 84, 40, 0, 0, "living", size=(0, 165))
    add("decor", "basket", 470, 330, -90, 0, "living", size=(0, 30))
    # dining
    add("dining_table", "rectangle 180x85", 238, 242.5, 0, room="living")
    for cx in (177.5, 240.5, 298):
        add("dining_chair", "oak spindle", cx, 186, 0, room="living")
        add("dining_chair", "oak spindle", cx, 299, 180, room="living")
    add("decor", "vase tall", 208, 242.5, 0, 75.3, "living", size=(0, 30))
    add("decor", "fruit bowl", 263, 242.5, 0, 75.3, "living", size=(0, 30))
    add("decor", "candlestick", 183, 248.5, 0, 75.3, "living", size=(0, 22))
    add("pendant", "rattan dome", 196, 242.5, 0, 160, "living")
    add("pendant", "rattan dome", 280, 242.5, 0, 160, "living")
    # hall
    add("wardrobe", "180 wide", 90, 1118, 0, room="hall")
    add("wardrobe", "180 wide", 90, 1330, 180, room="hall")
    add("hall_bench", "110", 245, 1340, 180, room="hall")
    add("hook_rail", "4 hooks", 245, 1358.5, 180, 163, "hall")
    add("mirror", "round 60", 245, 1360, 180, 212, "hall")
    add("rug", "jute", 250, 935, 0, 0, "hall", size=(76, 290))
    add("art", "olive branch", 189, 1020, 90, 150, "hall", size=(40, 54))
    add("art", "lines", 189, 820, 90, 150, "hall", size=(40, 54))
    add("plant", "leafy pot", 290, 1106, 0, 0, "hall", size=(0, 95))
    # main bedroom
    add("rug", "berber", 525, 585, 0, 0, "bed1", size=(230, 230))
    add("bed", "double 180", 523.5, 509.5, 0, room="bed1")
    for cx, lx in ((395.5, 389.5), (651.5, 657.5)):
        add("nightstand", "one drawer", cx, 420, 0, room="bed1")
        add("table_lamp", "column", lx, 424, 0, 52, "bed1", {"base": "#e7dfd2"})
    add("decor", "books", 645, 424, 0, 52, "bed1")
    add("decor", "jug", 408, 414, 0, 52, "bed1", size=(0, 18))
    add("art", "shapes", 480, 394, 0, 160, "bed1")
    add("art", "olive branch", 567, 394, 0, 160, "bed1")
    add("wardrobe", "87 wide", 486.5, 749, 180, room="bed1", slots={"fronts": "#c9a57d"})
    add("dresser", "122 wide", 661, 741, 180, room="bed1")
    add("mirror", "round 70", 661, 760, 180, 140, "bed1")
    add("decor", "vase tall", 616, 742, 0, 80, "bed1", size=(0, 28))
    add("plant", "leafy pot", 706, 740, 0, 80, "bed1", size=(0, 40))
    add("pendant", "rattan dome large", 523.5, 545, 0, 200, "bed1")
    add("plant", "calathea in pot", 704, 692, 0, 0, "bed1", size=(0, 70))
    # bedroom two
    add("rug", "stripes", 477.5, 1167.5, 0, 0, "bed2", size=(165, 125))
    add("bed", "single 90", 499, 1046.5, -90, room="bed2",
        slots={"headboard": "#d9ccb6", "duvet": "#efe8dc", "throw": "#9fac92", "pillows": "#c99540"})
    add("nightstand", "small", 588, 1119.5, 0, room="bed2")
    add("table_lamp", "ball", 590, 1122, 0, 50, "bed2", {"base": "#e7dfd2"})
    add("decor", "jug", 580, 1108, 0, 50, "bed2", size=(0, 16))
    add("wardrobe", "180 wide", 413, 1330, 180, room="bed2")
    add("desk", "105 with drawers", 555.5, 1335, 180, room="bed2")
    add("wall_shelf", "100", 556, 1349, 180, 120, "bed2")
    add("desk_lamp", "arm", 520, 1345, 180, 76, "bed2")
    add("dining_chair", "oak spindle", 549, 1296, 0, room="bed2")
    add("decor", "books", 532, 1340, 0, 76, "bed2")
    add("plant", "succulent", 594, 1336, 0, 76, "bed2", size=(0, 20))
    add("art", "horizon", 450, 994, 0, 150, "bed2", size=(60, 42))
    add("pendant", "paper globe", 466, 1170, 0, 205, "bed2")
    add("plant", "fern", 342, 1014, 0, 0, "bed2", size=(0, 55))
    # en-suite
    add("vanity", "72 single", 454, 813, 0, room="bath1")
    add("mirror", "round 60", 454, 790, 0, 150, "bath1")
    add("cistern_wall", "tiled", 453.5, 972, 180, room="bath1", size=(141, 20))
    add("wc", "rounded", 443.5, 935, 180, room="bath1")
    add("wc", "rounded bidet", 503, 935, 180, room="bath1")
    add("plant", "succulent", 400, 970, 0, 114, "bath1", size=(0, 20))
    add("decor", "vase round", 515, 972, 0, 114, "bath1", size=(0, 16))
    add("decor", "jug", 481, 808, 0, 85, "bath1", size=(0, 14))
    add("tall_cupboard", "60x60", 352.5, 952, 90, room="bath1")
    add("towel_rail", "with towel", 507, 794, 0, 122, "bath1")
    add("decor", "basket", 402, 898, 0, 0, "bath1", size=(0, 34))
    # bathroom two
    add("cistern_wall", "tiled", 19, 945, 90, room="bath2", size=(120, 18))
    add("wc", "rounded", 55, 915, 90, room="bath2")
    add("wc", "rounded bidet", 55, 976, 90, room="bath2")
    add("vanity", "160 long", 93, 1053.5, 180, room="bath2")
    add("mirror", "rectangle 86x78", 93, 1076, 180, 151, "bath2")
    add("decor", "towel stack", 37, 1051, 0, 85, "bath2")
    add("towel_rail", "with towel", 173, 1012, -90, 120, "bath2")
    add("plant", "succulent", 150, 1058, 0, 85, "bath2", size=(0, 20))
    add("decor", "vase bottle", 20, 950, 0, 114, "bath2", size=(0, 18))
    # balcony A
    add("rug", "stripes", 290, -83, 0, -2, "bal_a", size=(180, 90))
    add("bistro_set", "folding wood", 290, -84, 90, -2, "bal_a", size=(0, 86))
    add("outdoor_bench", "250", 595, -52, 180, -2, "bal_a")
    add("cushion", "square 42", 520, -36, 180, 50, "bal_a", {"fabric": "#a85f3d"})
    add("cushion", "square 42", 690, -36, 170, 50, "bal_a", {"fabric": "#c99540"})
    add("plant", "money tree small", 6, -100, 0, -2, "bal_a", size=(0, 150))
    add("plant", "elephant ear", 170, -122, 0, -2, "bal_a", size=(0, 80))
    add("plant", "anthurium in pot", 430, -118, 0, -2, "bal_a", size=(0, 60))
    add("plant", "leafy pot", 723, -120, 0, -2, "bal_a", size=(0, 70))
    # balcony B
    add("bistro_table", "round 56", 712, 900, 0, -2, "bal_b")
    add("stool", "wood", 690, 935, 0, -2, "bal_b")
    add("stool", "wood", 735, 870, -90, -2, "bal_b")
    add("decor", "vase tall", 712, 900, 0, 70, "bal_b", size=(0, 22))
    add("lounger", "115", 675, 1242, 0, -2, "bal_b")
    add("plant", "elephant ear", 752, 1060, 0, -2, "bal_b", size=(0, 90))
    add("plant", "leafy pot", 748, 815, 0, -2, "bal_b", size=(0, 80))
    return L


DEFAULT_CONFIG = {"name": "Warm Mediterranean", "finishes": DEFAULT_FINISHES, "items": _items(), "mood": "day"}


def catalog_json():
    kinds = {}
    for k, v in KINDS.items():
        kinds[k] = {"label": v["label"], "cat": v["cat"], "mount": v.get("mount", "floor"), "z": v.get("z", 0),
                    "variants": list(v["variants"]), "size": v.get("size"),
                    "slots": {s: {"type": t, "default": d} for s, (t, d) in v.get("slots", {}).items()}}
    return {"kinds": kinds, "categories": CATEGORIES, "woods": WOODS, "metals": METALS,
            "palettes": {"fabric": FABRICS, "paint": PAINTS, "tile": TILES}, "floors": FLOORS,
            "worktops": WORKTOPS, "bath_floors": BATH_FLOORS, "balcony_floors": BALCONY_FLOORS,
            "uppers": UPPERS, "handles": HANDLES, "moods": MOODS}


if __name__ == "__main__":
    out = {"catalog": catalog_json(), "default": DEFAULT_CONFIG}
    with open(sys.argv[1], "w") as f:
        json.dump(out, f)
    print("items", len(DEFAULT_CONFIG["items"]), "kinds", len(KINDS))
