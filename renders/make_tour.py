#!/usr/bin/env python3
"""Build the presentation page: renders, palette, pieces and prices, and a linked 360° tour.

Usage: python make_tour.py <finished_dir> <pannellum.css>     (needs Pillow)
Writes <finished_dir>/site/index.html with img/ and pano/ beside it. The page body has no
<html>/<head> wrapper: it is published as an Artifact, which adds the skeleton.

Hotspot directions come from plan coordinates, so the arrows sit in the real doorways:
panoramas are rendered facing the top of the sheet (yaw 0), yaw grows to the right.
"""
import html
import json
import math
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogue_data as D  # noqa: E402

SRC = Path(sys.argv[1])
CSS = Path(sys.argv[2]).read_text()
SITE = SRC / "site"
(SITE / "img").mkdir(parents=True, exist_ok=True)
(SITE / "pano").mkdir(parents=True, exist_ok=True)

EYE = 150
SPOTS = {   # pano id: (camera x, y), initial yaw, [(target scene, label, (x, y, z))]
    "pano_living": ((372, 250), -25, [("pano_balcony", "Balcony", (294, -10, 110)),
                                       ("pano_dining", "Kitchen and dining", (205, 440, 95)),
                                       ("pano_hall", "Hall", (250, 820, 115))]),
    "pano_dining": ((205, 440), 25, [("pano_living", "Living room", (372, 250, 95)),
                                      ("pano_balcony", "Balcony", (250, -10, 110)),
                                      ("pano_hall", "Hall", (250, 800, 115)),
                                      ("pano_bedroom1", "Main bedroom", (317, 645, 110))]),
    "pano_hall": ((250, 1215), 0, [("pano_dining", "Kitchen and dining", (250, 700, 115)),
                                    ("pano_bedroom2", "Bedroom two", (317, 1235, 110)),
                                    ("pano_bath2", "Bathroom two", (183, 923, 110))]),
    "pano_bedroom1": ((520, 660), 0, [("pano_dining", "Living area", (317, 645, 110)),
                                       ("pano_bath1", "En-suite", (378, 784, 110))]),
    "pano_bath1": ((468, 875), 95, [("pano_bedroom1", "Main bedroom", (378, 784, 110))]),
    "pano_bedroom2": ((460, 1185), 90, [("pano_hall", "Hall", (317, 1235, 110))]),
    "pano_bath2": ((95, 960), -178, [("pano_hall", "Hall", (183, 923, 110))]),
    "pano_balcony": ((390, -86), 40, [("pano_living", "Living room", (294, 0, 110))]),
}


def yaw_pitch(cam, target):
    dx, dy = target[0] - cam[0], target[1] - cam[1]
    yaw = math.degrees(math.atan2(dx, -dy))
    pitch = math.degrees(math.atan2(target[2] - EYE, math.hypot(dx, dy)))
    return round(yaw, 1), round(pitch, 1)


def export(name, folder, size):
    src = SRC / f"{name}.jpg"
    if not src.exists():
        return None
    dst = SITE / folder / f"{name}.jpg"
    im = Image.open(src)
    im.thumbnail((size, size))
    im.save(dst, quality=86, optimize=True, progressive=True)
    return f"{folder}/{name}.jpg"


stills = {}
for nm in D.CAPTIONS:
    big = export(nm, "img", 2400)
    if big:
        thumb = SITE / "img" / f"{nm}_s.jpg"
        im = Image.open(SITE / big)
        im.thumbnail((1100, 1100))
        im.save(thumb, quality=82, optimize=True, progressive=True)
        stills[nm] = (f"img/{nm}_s.jpg", big)
panos = {}
for nm, label in D.PANOS:
    p = export(nm, "pano", 4096)
    if p:
        panos[nm] = (p, label)

scenes = {}
for nm, (path, label) in panos.items():
    cam, yaw0, links = SPOTS[nm]
    hs = []
    for target, text, pt in links:
        if target in panos:
            y, p = yaw_pitch(cam, pt)
            hs.append({"pitch": p, "yaw": y, "type": "scene", "text": text, "sceneId": target})
    scenes[nm] = {"title": label, "panorama": path, "yaw": yaw0, "pitch": -4, "hfov": 105, "hotSpots": hs}
first = "pano_living" if "pano_living" in scenes else next(iter(scenes), None)
tour_cfg = {"default": {"firstScene": first, "sceneFadeDuration": 700, "autoLoad": True, "compass": False,
                        "showZoomCtrl": True, "mouseZoom": False, "hfov": 105, "minHfov": 50, "maxHfov": 120},
            "scenes": scenes}


def esc(s):
    return html.escape(s, quote=True)


def eur(v):
    return f"€{v:,.0f}".replace(",", " ")


def figure(nm, cls=""):
    if nm not in stills:
        return ""
    s, b = stills[nm]
    cap = esc(D.CAPTIONS.get(nm, ""))
    return (f'<figure class="shot {cls}"><button class="zoom" type="button" data-full="{b}" data-cap="{cap}" '
            f'aria-label="Enlarge: {cap}"><img src="{s}" alt="{cap}" loading="lazy" width="1100" height="733"></button>'
            f'<figcaption>{cap}</figcaption></figure>')


TOUR_FOR = {"living": "pano_living", "baths": "pano_bath1", "balconies": "pano_balcony"}
TOUR_TEXT = {"baths": "Look around the en-suite in 360°", "balconies": "Stand on the balcony in 360°"}

rooms_html = []
for r in D.ROOMS:
    lo = sum(i[2] for i in r["items"])
    hi = sum(i[3] for i in r["items"])
    items = "".join(
        f'<li><span class="piece"><b>{esc(n)}</b>{f"<small>{esc(s)}</small>" if s else ""}</span>'
        f'<span class="price">{eur(a)}–{eur(b)}</span></li>' for n, s, a, b in r["items"])
    figs = "".join(figure(nm) for nm in r["images"])
    scene = r.get("pano") or TOUR_FOR.get(r["key"])
    pano_btn = ""
    if scene in panos:
        pano_btn = (f'<button class="to-tour" type="button" data-scene="{scene}">'
                    f'{TOUR_TEXT.get(r["key"], "Look around this room in 360°")}</button>')
    rooms_html.append(f'''
<article class="room" id="{r["key"]}">
  <div class="room-media">{figs}</div>
  <div class="room-text">
    <h3>{esc(r["title"])}</h3>
    <p>{esc(r["text"])}</p>
    {pano_btn}
    <ul class="pieces">{items}</ul>
    <p class="room-total"><span>Room total</span><span>{eur(lo)}–{eur(hi)}</span></p>
  </div>
</article>''')

palette_html = "".join(
    f'<li><span class="chip" style="background:{h}"></span><b>{esc(n)}</b><code>{h.upper()}</code><small>{esc(u)}</small></li>'
    for n, h, u in D.PALETTE)
materials_html = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in D.MATERIALS)
budget_rows = "".join(
    f'<tr><th scope="row"><a href="#{r["key"]}">{esc(r["title"])}</a></th>'
    f'<td>{eur(sum(i[2] for i in r["items"]))}–{eur(sum(i[3] for i in r["items"]))}</td></tr>' for r in D.ROOMS)
tlo, thi = D.totals()
scene_chips = "".join(
    f'<button type="button" class="scene-chip" data-scene="{nm}" aria-pressed="false">{esc(label)}</button>'
    for nm, (_, label) in panos.items())
hero = stills.get("living_dusk", stills.get("living_day", ("", "")))[1]
concept_html = "".join(f"<p>{esc(p)}</p>" for p in D.CONCEPT)

page = f'''<title>Unit 13 Warm Scheme</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=Manrope:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
{CSS}
/* Layout: a printed interiors brief. Wide image plates, a narrow text column beside each,
   figures set in mono like a drawing's annotations. */
:root {{
  --bg: #f1efeb; --surface: #e7e3dc; --ink: #24211e; --muted: #6e675f; --rule: #d3cdc4;
  --accent: #5d6b54; --accent-ink: #f4f2ee; --warm: #a4593a; --lb-ink: #e9e4dc; --lb-rule: #6d665e;
  --display: "Newsreader", Georgia, "Times New Roman", serif;
  --body: "Manrope", "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
  --wrap: 1240px;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #1b1a18; --surface: #262421; --ink: #ece7df; --muted: #a79f94; --rule: #3a3632;
  --accent: #a9b89c; --accent-ink: #1b1a18; --warm: #d38a67; color-scheme: dark }} }}
:root[data-theme="dark"] {{
  --bg: #1b1a18; --surface: #262421; --ink: #ece7df; --muted: #a79f94; --rule: #3a3632;
  --accent: #a9b89c; --accent-ink: #1b1a18; --warm: #d38a67; color-scheme: dark }}
* {{ box-sizing: border-box }}
body {{ background: var(--bg); color: var(--ink); font: 400 16px/1.6 var(--body); }}
.wrap {{ max-width: var(--wrap); margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
h1, h2, h3 {{ font-family: var(--display); font-weight: 400; text-wrap: balance; margin: 0; letter-spacing: -0.01em }}
h2 {{ font-size: clamp(30px, 4vw, 44px); line-height: 1.1 }}
h3 {{ font-size: clamp(26px, 3vw, 34px); line-height: 1.15 }}
p {{ margin: 0 }}
.label {{ font: 500 12px/1.4 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted) }}
a {{ color: inherit }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px }}

header.top {{ border-bottom: 1px solid var(--rule) }}
header.top .wrap {{ display: flex; flex-wrap: wrap; gap: 8px 24px; justify-content: space-between; align-items: baseline; padding-block: 14px }}
header.top nav {{ display: flex; flex-wrap: wrap; gap: 4px 18px }}
header.top nav a {{ text-decoration: none; font-size: 14px; color: var(--muted) }}
header.top nav a:hover {{ color: var(--ink) }}
.brand {{ font: 500 13px/1.4 var(--mono); letter-spacing: 0.06em }}

.hero {{ margin-top: 24px }}
.hero img {{ display: block; width: 100%; max-width: 100%; height: auto; aspect-ratio: 3 / 2; max-height: 78vh; object-fit: cover; border-radius: 4px }}
.hero-text {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 24px 48px; padding-block: 28px 8px; align-items: end }}
.hero-text h1 {{ font-size: clamp(40px, 6.5vw, 84px); line-height: 0.98 }}
.hero-text h1 em {{ font-style: italic; color: var(--warm) }}
.facts {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 24px; margin: 0 }}
.facts div {{ border-top: 1px solid var(--rule); padding-top: 8px; min-width: 0 }}
.facts dt {{ font: 500 11px/1.4 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted) }}
.facts dd {{ margin: 2px 0 0; font: 500 19px/1.3 var(--mono); font-variant-numeric: tabular-nums }}

section {{ padding-block: 72px 0 }}
.section-head {{ display: flex; flex-wrap: wrap; gap: 8px 24px; align-items: baseline; justify-content: space-between;
  border-top: 1px solid var(--ink); padding-top: 14px; margin-bottom: 32px }}
.section-head p {{ max-width: 60ch; color: var(--muted) }}

.scheme {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 40px 64px }}
.concept {{ display: grid; gap: 16px; font-size: 18px; line-height: 1.65; max-width: 62ch }}
.materials {{ margin: 32px 0 0; display: grid; gap: 14px }}
.materials div {{ display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 16px; border-top: 1px solid var(--rule); padding-top: 12px }}
.materials dt {{ font: 500 12px/1.6 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent) }}
.materials dd {{ margin: 0 }}
.palette {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 20px; align-content: start }}
.palette li {{ display: grid; grid-template-columns: 56px minmax(0, 1fr); column-gap: 14px; align-items: center }}
.palette .chip {{ grid-row: 1 / 4; width: 56px; height: 56px; border-radius: 50%; box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.08) }}
.palette b {{ font-weight: 600; font-size: 15px }}
.palette code {{ font: 400 12px/1.4 var(--mono); color: var(--muted) }}
.palette small {{ font-size: 13px; color: var(--muted) }}

.room {{ display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr); gap: 28px 48px; padding-block: 36px; border-top: 1px solid var(--rule) }}
.room:first-of-type {{ border-top: 0; padding-top: 0 }}
.room-media {{ display: grid; gap: 16px; align-content: start; min-width: 0 }}
.shot {{ margin: 0; min-width: 0 }}
.shot .zoom {{ display: block; width: 100%; padding: 0; border: 0; background: var(--surface); cursor: zoom-in; border-radius: 4px; overflow: hidden }}
.shot img {{ display: block; width: 100%; max-width: 100%; height: auto; aspect-ratio: 3 / 2; object-fit: cover; transition: transform .5s ease }}
.shot .zoom:hover img {{ transform: scale(1.015) }}
.shot figcaption {{ font: 400 12px/1.5 var(--mono); color: var(--muted); margin-top: 8px }}
.room-text {{ display: grid; gap: 18px; align-content: start; min-width: 0 }}
.room-text > p {{ max-width: 52ch }}
.pieces {{ list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--rule) }}
.pieces li {{ display: flex; justify-content: space-between; gap: 16px; padding-block: 10px; border-bottom: 1px solid var(--rule) }}
.piece {{ display: grid; min-width: 0 }}
.piece b {{ font-weight: 600; font-size: 15px }}
.piece small {{ color: var(--muted); font-size: 13px }}
.price {{ font: 400 13px/1.6 var(--mono); white-space: nowrap; font-variant-numeric: tabular-nums }}
.room-total {{ display: flex; justify-content: space-between; gap: 16px; font: 500 14px/1.4 var(--mono); color: var(--warm); font-variant-numeric: tabular-nums }}
.to-tour, .scene-chip {{ font: 600 14px/1 var(--body); border-radius: 999px; padding: 11px 16px; cursor: pointer; border: 1px solid var(--accent) }}
.to-tour {{ justify-self: start; background: var(--accent); color: var(--accent-ink) }}
.to-tour:hover {{ filter: brightness(1.06) }}

#viewer {{ width: 100%; max-width: 100%; aspect-ratio: 16 / 9; max-height: 80vh; border-radius: 4px; overflow: hidden; background: var(--surface) }}
.scenes {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px }}
.scene-chip {{ background: transparent; color: var(--ink); border-color: var(--rule) }}
.scene-chip[aria-pressed="true"] {{ background: var(--accent); color: var(--accent-ink); border-color: var(--accent) }}
.tour-note {{ margin-top: 12px; color: var(--muted); font-size: 14px; max-width: 70ch }}
.pnlm-hotspot-base.pnlm-scene {{ filter: drop-shadow(0 1px 3px rgb(0 0 0 / .45)) }}
.pnlm-tooltip span {{ font-family: var(--body) }}

.plans {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr); gap: 24px; align-items: start }}
.plans .square img {{ aspect-ratio: 1 / 1 }}

.budget {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 40px 64px }}
.budget > div {{ min-width: 0 }}
.budget table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums }}
.budget th, .budget td {{ text-align: left; padding: 12px 0; border-bottom: 1px solid var(--rule); font-weight: 400 }}
.budget td {{ text-align: right; font: 400 14px/1.4 var(--mono); white-space: nowrap }}
.budget th a {{ text-decoration: none }}
.budget th a:hover {{ text-decoration: underline }}
.budget tfoot th, .budget tfoot td {{ color: var(--warm); font-weight: 600; border-bottom: 0; font-size: 17px }}
.budget h3 {{ font-size: 24px; margin-bottom: 16px }}
.tips {{ display: grid; gap: 14px; margin: 0; padding-left: 20px }}
.tips li::marker {{ color: var(--warm) }}
.note {{ color: var(--muted); font-size: 13px; margin-top: 16px; max-width: 70ch }}
footer .wrap {{ padding-block: 72px 48px; color: var(--muted); font-size: 13px }}

dialog.lightbox {{ border: 0; padding: 0; max-width: 96vw; max-height: 94vh; background: transparent }}
dialog.lightbox::backdrop {{ background: rgb(12 11 10 / 0.88) }}
dialog.lightbox img {{ display: block; max-width: 96vw; max-height: 86vh; width: auto; height: auto; border-radius: 3px }}
dialog.lightbox p {{ color: var(--lb-ink); font: 400 13px/1.5 var(--mono); margin-top: 8px; display: flex; justify-content: space-between; gap: 16px }}
dialog.lightbox button {{ background: none; border: 1px solid var(--lb-rule); color: var(--lb-ink); border-radius: 999px; padding: 4px 12px; cursor: pointer; font: inherit }}

@media (max-width: 860px) {{
  .hero-text, .scheme, .room, .plans, .budget {{ grid-template-columns: minmax(0, 1fr) }}
  .palette {{ grid-template-columns: minmax(0, 1fr) }}
  #viewer {{ aspect-ratio: 4 / 3 }}
}}
@media (prefers-reduced-motion: reduce) {{ .shot img {{ transition: none }} }}
</style>

<header class="top"><div class="wrap">
  <span class="brand">UNIT 13 · REV D</span>
  <nav aria-label="Sections"><a href="#scheme">Scheme</a><a href="#rooms">Rooms</a><a href="#tour">360° tour</a><a href="#plan">Plan</a><a href="#budget">Budget</a></nav>
</div></header>

<main class="wrap">
  <div class="hero">
    <img src="{hero}" alt="Living room at dusk: linen sofas, rattan pendants over the oak table, the sea through the balcony doors" width="2400" height="1600">
  </div>
  <div class="hero-text">
    <h1>Apartment Unit 13, <em>warm and open</em></h1>
    <dl class="facts">
      <div><dt>Interior</dt><dd>87.32 m²</dd></div>
      <div><dt>Balconies</dt><dd>17.95 m²</dd></div>
      <div><dt>Rooms</dt><dd>2 bed · 2 bath</dd></div>
      <div><dt>Indicative fit-out</dt><dd>{eur(round(tlo, -3))}–{eur(round(thi, -3))}</dd></div>
    </dl>
  </div>

  <section id="scheme">
    <div class="section-head"><h2>The scheme</h2><p class="label">{esc(D.SUBTITLE)}</p></div>
    <div class="scheme">
      <div><div class="concept">{concept_html}</div><dl class="materials">{materials_html}</dl></div>
      <ul class="palette" aria-label="Palette">{palette_html}</ul>
    </div>
  </section>

  <section id="rooms">
    <div class="section-head"><h2>Room by room</h2><p>Every room on the revised plan, furnished to the plan's footprints. Click a picture to see it full size.</p></div>
    {"".join(rooms_html)}
  </section>

  <section id="tour">
    <div class="section-head"><h2>Walk through it</h2><p>Drag to look around. The arrows in the doorways take you to the next room.</p></div>
    <div id="viewer" role="region" aria-label="360 degree tour"></div>
    <div class="scenes" role="group" aria-label="Choose a room">{scene_chips}</div>
    <p class="tour-note">The view from the windows is illustrative: the plan gives no orientation, so the sun is placed to come in through the sea-side glazing.</p>
  </section>

  <section id="plan">
    <div class="section-head"><h2>The whole apartment</h2><p>Cut at 1.5 m and seen from above. One oak floor runs through every dry room.</p></div>
    <div class="plans">{figure("topplan", "square")}{figure("cutaway")}</div>
  </section>

  <section id="budget">
    <div class="section-head"><h2>What it costs</h2><p class="label">Indicative · EUR · 2026</p></div>
    <div class="budget">
      <div>
        <table><thead><tr><th scope="col" class="label">Room</th><td class="label">Range</td></tr></thead>
        <tbody>{budget_rows}</tbody>
        <tfoot><tr><th scope="row">Total</th><td>{eur(tlo)}–{eur(thi)}</td></tr></tfoot></table>
        <p class="note">{esc(D.NOTE)}</p>
      </div>
      <div>
        <h3>Where to save, where to spend</h3>
        <ul class="tips">
          <li>Spend on the sofa, the mattress and the kitchen fronts: they are touched every day.</li>
          <li>Save on dining chairs, lamps, rugs and baskets: mid-range versions look the same in the room.</li>
          <li>One floor everywhere costs less to lay and makes the flat feel bigger.</li>
          <li>Limewash two walls instead of tiling or panelling them: the warmest effect for the least money.</li>
          <li>Zellige-look ceramic gives the handmade look of real zellige at a fraction of the price.</li>
        </ul>
      </div>
    </div>
  </section>
</main>
<footer><div class="wrap">Rendered in Blender Cycles from the revised plan (rev D) with CC0 materials and models from Poly Haven. Artwork and rugs are original. Check all dimensions on site.</div></footer>

<dialog class="lightbox" id="lightbox"><img id="lb-img" alt=""><p><span id="lb-cap"></span><button type="button" id="lb-close">Close</button></p></dialog>

<script src="https://cdnjs.cloudflare.com/ajax/libs/pannellum/2.5.6/pannellum.js"></script>
<script>
(function () {{
  var cfg = {json.dumps(tour_cfg)};
  var viewer = null;
  var chips = document.querySelectorAll(".scene-chip");
  function mark(id) {{ chips.forEach(function (c) {{ c.setAttribute("aria-pressed", c.dataset.scene === id ? "true" : "false"); }}); }}
  function start() {{
    if (!window.pannellum || !cfg.default.firstScene) return;
    viewer = pannellum.viewer("viewer", cfg);
    viewer.on("scenechange", mark);
    mark(cfg.default.firstScene);
  }}
  chips.forEach(function (c) {{ c.addEventListener("click", function () {{ if (viewer) viewer.loadScene(c.dataset.scene); }}); }});
  document.querySelectorAll(".to-tour").forEach(function (b) {{
    b.addEventListener("click", function () {{
      if (viewer) viewer.loadScene(b.dataset.scene);
      document.getElementById("tour").scrollIntoView({{ behavior: "smooth", block: "start" }});
    }});
  }});
  start();
  var lb = document.getElementById("lightbox"), img = document.getElementById("lb-img"), cap = document.getElementById("lb-cap");
  document.querySelectorAll(".zoom").forEach(function (b) {{
    b.addEventListener("click", function () {{
      img.src = b.dataset.full; img.alt = b.dataset.cap; cap.textContent = b.dataset.cap;
      if (lb.showModal) lb.showModal();
    }});
  }});
  document.getElementById("lb-close").addEventListener("click", function () {{ lb.close(); }});
  lb.addEventListener("click", function (e) {{ if (e.target === lb) lb.close(); }});
}})();
</script>
'''
(SITE / "index.html").write_text(page)
print("wrote", SITE / "index.html", "stills", len(stills), "panos", len(panos))
