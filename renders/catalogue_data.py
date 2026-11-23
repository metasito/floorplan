"""Words, palette and pieces for the Unit 13 warm-scheme catalogue (PDF and web).

Prices are indicative 2026 mid-market retail ranges in EUR, before delivery, installation and
appliances. They are for budgeting a scheme like this, not quotes for specific products.
"""

TITLE = "Apartment Unit 13"
SUBTITLE = "Warm Mediterranean, on an everyday budget"
AREA = "87.32 m² interior · 17.95 m² balconies · 2 bedrooms · 2 bathrooms"

CONCEPT = [
    "Sea light does most of the work. Walls are a warm, chalky white; one light oak floor runs "
    "unbroken through every dry room, so the hall, kitchen and living room read as one open space "
    "and the 87 m² feel larger.",
    "Colour comes from the earth, not from paint charts: a clay limewash behind the TV, sage behind "
    "the main bed and on the kitchen fronts, terracotta and ochre in the textiles, terracotta tiles "
    "outside. Texture does the rest: linen, jute, rattan, cane and glazed zellige-look tiles.",
    "Everything shown is a standard, widely available kind of piece. The only made-to-measure item "
    "is the kitchen, and it is flat-pack with painted fronts.",
]

PALETTE = [
    ("Warm white", "#ece6dc", "walls, trim, built-ins"),
    ("Clay limewash", "#c3a58a", "living room TV wall"),
    ("Sage limewash", "#a9b29a", "behind the main bed"),
    ("Kitchen sage", "#8f9a85", "kitchen fronts"),
    ("Terracotta", "#b4643e", "cushions, pots, balcony tiles"),
    ("Ochre", "#c99540", "accents"),
    ("Light oak", "#c9a57d", "floor, tables, joinery"),
    ("Oatmeal linen", "#ddd3c2", "sofas, bed, curtains"),
    ("Brushed brass", "#c8a66a", "taps, knobs, mirrors"),
    ("Anthracite", "#3c3f42", "window frames (existing)"),
]

MATERIALS = [
    ("Floors", "Light oak-look engineered board or laminate in every dry room; terrazzo-look porcelain in "
               "the bathrooms; terracotta tiles on both balconies."),
    ("Walls", "Warm white matt emulsion; mineral limewash on the two accent walls; a clay band to 105 cm "
              "in bedroom 2."),
    ("Kitchen", "Painted sage fronts with brass knobs, oak worktop, cream zellige-look splashback, open oak "
                "shelves, warm LED under the cupboards."),
    ("Bathrooms", "10 × 10 glazed zellige-look tiles: sand in the en-suite, sage in bathroom 2. Oak vanities, "
                  "white vessel basins, brushed-brass fittings, walk-in showers behind glass."),
    ("Light", "Warm 2700 K throughout: rattan and paper pendants, linen-shaded lamps, small recessed "
              "downlights in the hall, kitchen and bathrooms."),
]

ROOMS = [
    dict(key="living", title="Living room", images=["living_day", "living_dusk"],
         text="The plan's L-shaped seating faces the TV wall; the doors to Balcony A and the window to the "
              "right bring the sea in. The clay limewash wall warms the room in the evening.",
         items=[("3-seat sofa", "oatmeal linen, oak legs, 216 cm", 900, 1400),
                ("2-seat sofa", "matching, 160 cm", 700, 1000),
                ("Jute rug", "200 × 300", 180, 320),
                ("Coffee table", "oak, rounded, 104 × 64", 220, 380),
                ("Media unit", "oak with cane fronts, 276 cm", 400, 650),
                ("Side table, floor lamp, table lamp", "oak tripod, linen shades, terracotta base", 230, 400),
                ("Sheer linen curtains", "four panels on ceiling tracks", 250, 400),
                ("Cushions, throw, ceramics, plants", "", 250, 450)]),
    dict(key="kitchen", pano="pano_dining", title="Kitchen and dining", images=["kitchen_day"],
         text="The full 5.1 m run as revision C: unit order unchanged, moved toward the balcony to end at the "
              "storage. Open oak shelves over the sink keep it light; the oak table sits between kitchen and "
              "living room.",
         items=[("Kitchen run, 5.1 m", "sage painted fronts, brass knobs, oak worktop", 4500, 7000),
                ("Zellige-look splashback", "about 3 m², cream", 150, 300),
                ("Ceramic sink and bridge tap", "brushed brass", 300, 500),
                ("Open shelves and LED strips", "oak, 2700 K", 150, 300),
                ("Dining table", "oak, 180 × 85, rounded corners", 550, 900),
                ("Six dining chairs", "oak, paper-cord seats", 600, 1000),
                ("Two rattan pendants", "", 120, 240)]),
    dict(key="hall", pano="pano_hall", title="Entrance and hall", images=["hall"],
         text="From the front door the corridor runs straight to the sea. Wardrobes either side of the "
              "entrance take coats and shoes; the storage now opens off the corridor, like the other rooms.",
         items=[("Built-in wardrobes", "2 × 180 cm, warm white, oak pulls", 1200, 2000),
                ("Bench, hook rail, round mirror", "oak and brass", 250, 450),
                ("Jute runner", "76 × 290", 60, 120),
                ("Storage shelving and baskets", "", 150, 300),
                ("Prints and frames", "", 80, 160)]),
    dict(key="bedroom1", pano="pano_bedroom1", title="Main bedroom", images=["bedroom1"],
         text="A calm sage wall behind the bed, oak and linen everywhere else. The en-suite opens off this "
              "room; the cut-down wardrobe sits by its door and a dresser takes the far wall.",
         items=[("Upholstered bed", "180 × 200, oatmeal linen headboard", 500, 900),
                ("Two nightstands", "oak, one drawer", 200, 360),
                ("Bedding and throw", "white linen, terracotta waffle", 200, 350),
                ("Berber-style rug", "230 × 230", 200, 380),
                ("Wardrobe and dresser", "oak, 87 cm and 122 cm", 600, 1000),
                ("Rattan pendant, lamps, mirror", "", 200, 350),
                ("Linen curtains and sage limewash", "", 160, 300)]),
    dict(key="bedroom2", pano="pano_bedroom2", title="Bedroom two", images=["bedroom2"],
         text="A guest room that works as a study: single bed along the wall, a desk under a shelf, and the "
              "glazed door to Balcony B. The clay band to 105 cm makes it cosy without darkening it.",
         items=[("Single bed", "90 × 190, upholstered", 250, 450),
                ("Desk with drawers and shelf", "oak", 250, 400),
                ("Wardrobes", "3 modules, warm white", 600, 1000),
                ("Rug, paper pendant, lamps", "flat-weave stripe", 150, 260),
                ("Bedding, curtains, clay paint", "", 180, 320)]),
    dict(key="baths", title="Bathrooms", images=["bath1", "bath2"],
         text="The en-suite keeps the revised layout, with WC and bidet moved 10 cm left to clear the shower "
              "glass, and a tall oak cupboard housing boiler and washer. Bathroom 2 repeats the recipe in sage.",
         items=[("Tiles, both bathrooms", "zellige-look walls, terrazzo-look floors", 1200, 2200),
                ("Two oak vanities and basins", "wall-hung, brass wall taps", 900, 1600),
                ("Two walk-in showers", "glass panels, brass rain sets", 1200, 2000),
                ("Wall-hung WCs and bidets", "with concealed frames", 1400, 2400),
                ("Mirrors, rails, accessories", "brass", 300, 600),
                ("Tall utility cupboard", "boiler and washer, oak fronts", 300, 500)]),
    dict(key="balconies", title="Balconies", images=["balcony_a", "balcony_b"],
         text="Balcony A, off the living room, is for the sea: a bistro table by the doors and a cushioned "
              "bench along the wall. Balcony B, off bedroom 2, has a lounger and a small table.",
         items=[("Folding bistro sets", "two", 200, 380),
                ("Bench and lounger with cushions", "oak, outdoor linen", 450, 750),
                ("Outdoor rug, planters, plants", "terracotta", 250, 450),
                ("Wall lights", "five, black", 150, 300)]),
]

PANOS = [
    ("pano_living", "Living room"), ("pano_dining", "Kitchen and dining"), ("pano_hall", "Entrance"),
    ("pano_bedroom1", "Main bedroom"), ("pano_bath1", "En-suite"), ("pano_bedroom2", "Bedroom two"),
    ("pano_bath2", "Bathroom two"), ("pano_balcony", "Balcony, evening"),
]

CAPTIONS = {
    "living_day": "Living room toward the sea, morning",
    "living_dusk": "Living room at dusk",
    "kitchen_day": "Kitchen and dining",
    "hall": "From the front door: the corridor runs to the sea",
    "bedroom1": "Main bedroom",
    "bedroom2": "Bedroom two and Balcony B",
    "bath1": "En-suite",
    "bath2": "Bathroom two",
    "balcony_a": "Balcony A, evening",
    "balcony_b": "Balcony B",
    "cutaway": "The whole apartment, cut at 1.5 m",
    "topplan": "3D plan",
}

NOTE = ("Prices are indicative 2026 mid-market retail ranges in euros, before delivery, installation and "
        "appliances. Renders are illustrations of the scheme on the revised plan (rev D); ceiling height "
        "270 cm and the view are assumed. Check all dimensions on site.")


def totals():
    lo = sum(i[2] for r in ROOMS for i in r["items"])
    hi = sum(i[3] for r in ROOMS for i in r["items"])
    return lo, hi
