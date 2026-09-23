"""Static server + a tiny control API so the 3D app can start the lab from its chat box.

python server.py [--port 8000]
  GET  /...              static files from the repo root (tree.json, frames/, paper.html, viewer.html, app/dist)
  GET  /api/status       {"running": bool, "mock": bool, "pid": int|null}
  POST /api/start        {"question": str, "mock": bool}  -> launches lab.py (or mock_lab.py) with that question
  POST /api/stop         touches STOP so the loop writes the paper and exits
"""
import argparse, json, os, pathlib, shutil, subprocess, sys, time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent
proc = {"p": None, "mock": False}


def load_env():
    """Load .env (KEY=VALUE lines) into os.environ without overriding what is already set."""
    p = ROOT / ".env"
    if not p.exists(): return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


def running():
    return proc["p"] is not None and proc["p"].poll() is None


def start(question, mock):
    if running():
        return 409, {"error": "a run is already in progress"}
    (ROOT / "logs").mkdir(exist_ok=True); (ROOT / "runs").mkdir(exist_ok=True)
    if (ROOT / "STOP").exists(): (ROOT / "STOP").unlink()
    if (ROOT / "tree.json").exists():   # keep the previous run, start this one clean
        shutil.move(ROOT / "tree.json", ROOT / "runs" / f"tree_{datetime.now():%H%M%S}.json")
    for f in ("paper.md", "paper.html"):
        if (ROOT / f).exists(): shutil.move(ROOT / f, ROOT / "runs" / f"{datetime.now():%H%M%S}_{f}")
    load_env()
    use_mock = bool(mock)
    if not use_mock:
        if not (ROOT / "lab.py").exists():
            return 400, {"error": "lab.py is missing; pull Muaaz's branch or tick 'mock lab'"}
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return 400, {"error": "ANTHROPIC_API_KEY not set: add it to .env next to server.py, then restart server.py"}
    if use_mock:
        cmd = [sys.executable, "-u", "mock_lab.py", "--nodes", "60", "--interval", "4", "--question", question]
    else:   # real lab: Claude Fable 5.1 via lab.py (MODEL = "claude-fable-5-1"), key + workspace from .env
        cmd = [sys.executable, "-u", "lab.py", "--question", question, "--minutes", "60"]
    print(("mock" if use_mock else "fable 5.1") + " run:", question[:80], flush=True)
    log = open(ROOT / "logs" / "run.log", "a", encoding="utf-8")
    proc["p"] = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    proc["mock"] = use_mock
    return 200, {"ok": True, "mock": use_mock, "pid": proc["p"].pid}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def log_message(self, *a):   # quiet
        pass

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers(); self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api/status"):
            return self.send_json(200, {"running": running(), "mock": proc["mock"], "pid": proc["p"].pid if proc["p"] else None,
                                        "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")), "model": "claude-fable-5-1"})
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(n) or b"{}") if n else {}
        if self.path.startswith("/api/start"):
            q = (data.get("question") or "").strip()
            if not q: return self.send_json(400, {"error": "question required"})
            return self.send_json(*start(q, bool(data.get("mock"))))
        if self.path.startswith("/api/stop"):
            (ROOT / "STOP").touch(); return self.send_json(200, {"ok": True})
        self.send_json(404, {"error": "unknown endpoint"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8000)
    port = ap.parse_args().port
    print(f"serving {ROOT} on http://localhost:{port}  (3D app: /app/dist/ after `npm run build`, dev: vite on 5173)")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
