#!/usr/bin/env python3
"""Batch renders in Blender, on Mac and Windows alike (replaces render_all.sh / render_all_warm.sh).

Usage:
  python renders/batch.py warm [out_dir]
      Final renders of the warm scheme: every still and 360° panorama, into out_dir
      (default renders/out_warm/raw). Takes hours: one Blender process per light mood.
  python renders/batch.py styles <out_dir> <samples> <width> <height> [extra args]
      Every style from render_interiors.py, from the lounge and the dining views.

Blender is found automatically; set the BLENDER environment variable to override.
"""
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_blender():
    """$BLENDER if set, else blender on PATH, else the standard install location for this OS."""
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    if shutil.which("blender"):
        return shutil.which("blender")
    if sys.platform == "darwin":
        return "/Applications/Blender.app/Contents/MacOS/Blender"
    if sys.platform == "win32":
        found = sorted(Path(os.environ.get("ProgramFiles", r"C:\Program Files")).glob("Blender Foundation/Blender*/blender.exe"),
                       key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)])
        if found:
            return str(found[-1])    # newest version
    return "blender"


def run(script, args, log=None, show=r"Traceback|Error|rendered|skipped"):
    """One Blender process; prints (and logs) only the lines that matter."""
    cmd = [find_blender(), "-b", "--factory-startup", "--disable-autoexec", "--python", str(HERE / script), "--", *args]
    head = f"=== {time.strftime('%H:%M:%S')} {' '.join(args)}"
    print(head, flush=True)
    if log:
        log.write(head + "\n")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        if re.search(show, line):
            print(line, end="", flush=True)
            if log:
                log.write(line)
    return p.wait()


def warm(out=None):
    out = Path(out or HERE / "out_warm" / "raw")
    out.mkdir(parents=True, exist_ok=True)
    still = ["--samples", "768", "--noise", "0.008", "--res", "3000", "2000"]
    pano = ["--pano-samples", "512", "--noise", "0.012", "--pano-res", "4096", "2048"]
    batches = [   # views in one process share one build and one light mood
        (["living_day", "kitchen_day", "hall", "bedroom1", "bedroom2", "bath1", "bath2"], still),
        (["living_dusk"], still),
        (["balcony_a", "balcony_b"], still),
        (["cutaway", "topplan"], still),
        (["pano_living", "pano_dining", "pano_hall", "pano_bedroom1", "pano_bedroom2", "pano_bath1", "pano_bath2"], pano),
        (["pano_balcony"], pano),
    ]
    with open(out / "render.log", "a", encoding="utf-8") as log:
        for views, settings in batches:
            run("shoot.py", ["--out", str(out), "--views", *views, *settings], log)
        log.write(f"=== {time.strftime('%H:%M:%S')} all done\n")


def styles(out, samples, w, h, *extra):
    Path(out).mkdir(parents=True, exist_ok=True)
    for style in ["modern", "minimal", "scandinavian", "industrial", "midcentury", "boho", "traditional"]:
        for view in ["lounge", "dining"]:
            run("render_interiors.py", ["--style", style, "--view", view, "--samples", samples,
                                        "--res", w, h, "--out", str(Path(out) / f"{style}_{view}.png"), *extra])


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "warm":
        warm(*sys.argv[2:3])
    elif len(sys.argv) >= 6 and sys.argv[1] == "styles":
        styles(*sys.argv[2:])
    else:
        sys.exit(__doc__)
