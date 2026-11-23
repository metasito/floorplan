#!/usr/bin/env python3
"""Local server for the Unit 13 configurator: serves the editor and renders layouts with Blender.

Usage: .venv/bin/python configurator/server.py [port]      then open http://localhost:8013

POST /api/render takes the layout and the editor's camera, queues a Cycles render (one at a time,
in the order asked) and finishes it with renders/post.py. Saved layouts live in layouts/.
"""
import datetime
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
RENDERS_SRC = HERE.parent / "renders"
OUT = HERE / "renders"
LAYOUTS = HERE / "layouts"
OUT.mkdir(exist_ok=True)
LAYOUTS.mkdir(exist_ok=True)
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"

QUALITY = {   # label: (resolution, samples, noise threshold)
    "preview": ((1200, 800), 96, 0.03),
    "standard": ((2100, 1400), 384, 0.012),
    "final": ((3000, 2000), 768, 0.008),
    "360": ((4096, 2048), 512, 0.012),
}

jobs = {}
order = []
queue = Queue()
lock = threading.Lock()


def save_job(j):
    (OUT / j["id"] / "job.json").write_text(json.dumps({k: v for k, v in j.items() if not k.startswith("_")}))


def load_jobs():
    for d in sorted(OUT.iterdir(), key=lambda p: p.stat().st_mtime):
        f = d / "job.json"
        if f.exists():
            j = json.loads(f.read_text())
            if j["status"] in ("queued", "running"):
                j["status"], j["stage"] = "stopped", "stopped when the server closed"
            jobs[j["id"]] = j
            order.append(j["id"])


def worker():
    while True:
        jid = queue.get()
        j = jobs.get(jid)
        if not j or j["status"] != "queued":
            continue
        d = OUT / jid
        (res, samples, noise) = QUALITY[j["quality"]]
        pano = j["quality"] == "360"
        cmd = [BLENDER, "-b", "--factory-startup", "--disable-autoexec", "--python", str(RENDERS_SRC / "shoot.py"),
               "--", "--config", str(d / "config.json"), "--cam", str(d / "cam.json"), "--out", str(d),
               "--noise", str(noise)]
        cmd += ["--pano-samples", str(samples), "--pano-res", *map(str, res)] if pano else \
            ["--samples", str(samples), "--res", *map(str, res)]
        with lock:
            j["status"], j["stage"], j["started"] = "running", "building the apartment", time.time()
            save_job(j)
        log = open(d / "blender.log", "w")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        j["_proc"] = p
        for line in p.stdout:
            log.write(line)
            m = re.search(r"Sample (\d+)/(\d+)", line)
            with lock:
                if m:
                    j["stage"] = "rendering"
                    j["progress"] = round(int(m.group(1)) / int(m.group(2)), 3)
                elif "Denois" in line:
                    j["stage"] = "denoising"
        p.wait()
        log.close()
        with lock:
            j.pop("_proc", None)
            png = d / f"{j['name']}.png"
            if j["status"] == "cancelled":
                pass
            elif p.returncode == 0 and png.exists():
                j["stage"] = "finishing"
                post = subprocess.run([sys.executable, str(RENDERS_SRC / "post.py"), str(d), str(d)],
                                      capture_output=True, text=True)
                jpg = d / f"{j['name']}.jpg"
                j["image"] = f"renders/{jid}/{jpg.name if jpg.exists() else png.name}"
                j["thumb"] = f"renders/{jid}/web/{jpg.name}" if (d / "web" / jpg.name).exists() else j["image"]
                j["status"], j["progress"], j["stage"] = "done", 1.0, "done"
                if post.returncode:
                    j["note"] = "finishing step failed; showing the raw render"
            else:
                j["status"], j["stage"] = "failed", "failed: see blender.log"
            j["seconds"] = round(time.time() - j["started"])
            save_job(j)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api") else "max-age=60")
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/jobs":
            with lock:
                return self._json([{k: v for k, v in jobs[i].items() if not k.startswith("_")} for i in order][::-1])
        if u.path == "/api/layouts":
            return self._json(sorted(p.stem for p in LAYOUTS.glob("*.json")))
        if u.path == "/api/layout":
            name = parse_qs(u.query).get("name", [""])[0]
            f = LAYOUTS / f"{safe(name)}.json"
            return self._json(json.loads(f.read_text())) if f.exists() else self._json({"error": "not found"}, 404)
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/layout":
            b = self._body()
            name = safe(b.get("name") or "layout")
            (LAYOUTS / f"{name}.json").write_text(json.dumps(b["config"], indent=1))
            return self._json({"saved": name})
        if u.path == "/api/render":
            b = self._body()
            q = b.get("quality", "preview")
            if q not in QUALITY:
                return self._json({"error": f"unknown quality {q}"}, 400)
            jid = datetime.datetime.now().strftime("%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
            d = OUT / jid
            d.mkdir(parents=True)
            cam = dict(b["camera"])
            cam["name"] = "render"
            cam["mood"] = b.get("mood", "day")
            cam["pano"] = q == "360"
            (d / "config.json").write_text(json.dumps(b["config"]))
            (d / "cam.json").write_text(json.dumps(cam))
            j = {"id": jid, "name": "render", "quality": q, "mood": cam["mood"], "label": b.get("label", ""),
                 "status": "queued", "progress": 0.0, "stage": "waiting", "created": datetime.datetime.now().isoformat()}
            with lock:
                jobs[jid] = j
                order.append(jid)
                save_job(j)
            queue.put(jid)
            return self._json({"id": jid})
        if u.path == "/api/cancel":
            jid = self._body().get("id")
            with lock:
                j = jobs.get(jid)
                if j and j["status"] in ("queued", "running"):
                    j["status"], j["stage"] = "cancelled", "cancelled"
                    if j.get("_proc"):
                        j["_proc"].terminate()
                    save_job(j)
            return self._json({"ok": True})
        return self._json({"error": "unknown"}, 404)


def safe(name):
    return re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()[:60] or "layout"


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8013
    load_jobs()
    threading.Thread(target=worker, daemon=True).start()
    ThreadingHTTPServer.request_queue_size = 256     # the editor asks for ~100 models at once
    ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Unit 13 configurator on http://localhost:{port}", flush=True)
    srv.serve_forever()
