# Unit 13 – apartment planner

Plan and design our apartment (Unit 13, 87 m², two bedrooms, two bathrooms, two balconies):

- **3D editor in the browser.** Move, turn, swap and recolour furniture, pick wall, floor, kitchen and
  bathroom finishes, walk through the rooms, and save layouts so we can compare options.
- **Photoreal renders.** One click in the editor renders the current view in Blender: a still or a
  360° panorama, in day, dusk or golden-hour light.
- **Floor plan drawings.** An A3 PDF at 1:50, PNGs, and a DXF for architects and contractors, all
  generated from the measured dimensions.

Everything runs on your own computer, on Mac or Windows. Nothing is uploaded anywhere.

---

## First-time setup (once per computer)

You need three free programs. Install them like any other app and accept the defaults.

| | Mac | Windows |
|---|---|---|
| **Python** | [python.org/downloads](https://www.python.org/downloads/) | [python.org/downloads](https://www.python.org/downloads/): tick **"Add python.exe to PATH"** on the first screen |
| **Blender** (only needed for renders) | [blender.org/download](https://www.blender.org/download/), then drag it into Applications | [blender.org/download](https://www.blender.org/download/), or `winget install BlenderFoundation.Blender` |
| **Git** (to get the project and share layouts) | already installed: type `git` in Terminal once and accept the prompt | [git-scm.com](https://git-scm.com/download/win) |

Then download the project.

**Mac:** open Terminal and run:
```sh
cd ~ && git clone https://github.com/metasito/floorplan.git
```
**Windows:** open PowerShell and run:
```powershell
cd ~; git clone https://github.com/metasito/floorplan.git
```

## Start the editor

| Mac | Windows |
|---|---|
| Open the `floorplan/configurator` folder in Finder and double-click **`start.command`**. The first time, macOS may say it can't be opened: right-click it, choose **Open**, then **Open** again. | Open the `floorplan\configurator` folder and double-click **`start.bat`**. If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**. |

The first start takes a minute or two while it installs what it needs. After that it starts at once.
The editor then opens in your browser at **http://localhost:8013**.

Leave the black window open while you work: closing it stops the editor.

## Using the editor

**Views** (top bar): **3D** to orbit the whole flat, **Plan** to look from above, **Walk** to stand inside
a room at eye height. **Cut walls** slices the top off the walls so you can see in.

**Furniture tab:** click a piece to add it where you're looking. Click any piece in the model to select
it, then drag the arrows to move it or change its variant and colours in the panel.

| Key | Does |
|---|---|
| R | turn the selected piece 90° |
| Delete | remove it |
| Cmd+D (Mac) / Ctrl+D (Windows) | duplicate it |
| Cmd+Z (Mac) / Ctrl+Z (Windows) | undo |
| Esc | deselect |

**Rooms tab:** wall colours, floors, kitchen fronts and worktop, bathroom tiles, balcony floors.

**Layouts tab:** give the current design a name and save it, or load one saved earlier. Your work in
progress is also kept in the browser automatically between sessions.

**Render tab:** frame the shot inside the white rectangle, choose a light mood and quality, and click
**Render this view**. Renders queue up and appear in the list when done. You can keep editing
meanwhile. Use Walk view for interior photos and 3D view for a cut-away of the whole flat.

How long a render takes depends on the computer. The times shown in the editor are from a recent Mac.
On a laptop with built-in graphics, expect about 4× longer (a Preview takes ~4 minutes).
Start with **Preview** and use **Final** only for the shots you want to keep.

Finished renders are saved in `configurator/renders/`.

## Sharing designs between us

Saved layouts are small files in `configurator/layouts/`, and git carries them between our computers.

After saving a layout you want to share, run this in the `floorplan` folder (Terminal on Mac,
PowerShell on Windows):
```sh
git add configurator/layouts
git commit -m "Layout: living room with corner sofa"
git push
```
To get the other person's layouts and any updates:
```sh
git pull
```
Then reopen the **Layouts** tab.

Renders are not shared through git because they're large. Send the images you like directly.

---

## For tinkering (optional)

Run these from the `floorplan` folder. Use `.venv/bin/python` on Mac or `.venv\Scripts\python` on
Windows. The `.venv` folder is created the first time you start the editor.

| What | Command |
|---|---|
| Redraw the floor plan (PDF, PNG, DXF) after changing dimensions in `build_floorplan.py` | `python build_floorplan.py` |
| Render every view of the warm scheme, stills and panoramas (takes hours) | `python renders/batch.py warm` |
| Render the seven alternative styles (modern, boho, …) | `python renders/batch.py styles out 256 1920 1200` |
| Lay out the catalogue PDF from finished renders | `python renders/make_catalogue.py renders/out_warm` |

What's where:

- `build_floorplan.py`: the plan. Every wall comes from the measured dimensions at the top.
- `configurator/`: the browser editor (`index.html`, `app.js`) and its small local server (`server.py`).
- `renders/`: the Blender side. `catalog.py` lists every furniture piece and finish, `design.py` builds
  the warm scheme, `shoot.py` sets up cameras and light, and `post.py` does the photo finishing.
- `renders/out_warm/`: a finished set of renders, a catalogue PDF with indicative prices, and a
  presentation page with a 360° tour.

Blender is found automatically. If you installed it somewhere unusual, set the `BLENDER` environment
variable to the full path of the Blender program.

## Troubleshooting

| Problem | Fix |
|---|---|
| Windows: `python` opens the Microsoft Store or says "not found" | Reinstall Python from python.org with **"Add python.exe to PATH"** ticked, then delete the `.venv` folder and start again. |
| Mac: `python3` asks to install developer tools | Install Python from python.org instead, then delete the `.venv` folder and start again. |
| A render says *failed* | Open `blender.log` in that render's folder under `configurator/renders/`. The last lines say why. If it says Blender wasn't found, install Blender and restart the editor. |
| The editor window says "address already in use" | The editor is already running in another window. Use that one, or close it first. |
| Renders are very slow | The line starting *Cycles device* in `blender.log` says which device was used (for example *Cycles device: HIP (AMD Radeon)*). "CPU" means no usable graphics card was found. Use Preview quality. |

## Notes

- Dimensions come from a photographed plan and are marked where scaled. Check on site before
  ordering anything made to measure.
- Ceiling height (270 cm), door heads and window heads are assumptions. The plan doesn't give them.
- Furniture models and textures are CC0 from [Poly Haven](https://polyhaven.com). The art and rug
  patterns are generated by `renders/make_art_warm.py`.
- Prices in the catalogue are indicative 2026 mid-market ranges, not quotes.
