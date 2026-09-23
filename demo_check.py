"""Phase D: demo readiness. python demo_check.py   (make demo-check)"""
import json, os, pathlib, shutil, subprocess, sys, time, urllib.request
from datetime import datetime

for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

ROOT = pathlib.Path(__file__).resolve().parent
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def age(p):
    return time.time() - p.stat().st_mtime if p.exists() else float("inf")


try:
    tree = json.loads((ROOT / "tree.json").read_text(encoding="utf-8"))
except Exception as e:
    tree = {"nodes": [], "status": None}
    check("tree.json readable", False, str(e))
nodes = tree.get("nodes", [])
n_rules = sum(len(n.get("rules_tested") or []) for n in nodes)
check("tree.json >= 40 nodes and >= 1,000 rules", len(nodes) >= 40 and n_rules >= 1000, f"{len(nodes)} nodes, {n_rules:,} rules")

log = ROOT / "logs/run.log"
fresh = min(age(log), age(ROOT / "tree.json"))
check("loop alive (status running, log/tree fresh < 60 s)", tree.get("status") == "running" and fresh < 60,
      f"status={tree.get('status')}, last write {fresh:.0f}s ago")

paper = ROOT / "paper.html"
check("paper.html exists and < 15 min old", age(paper) < 15 * 60,
      f"{age(paper) / 60:.1f} min old" if paper.exists() else "missing")

try:
    code = urllib.request.urlopen("http://localhost:8000/viewer.html", timeout=3).status
except Exception as e:
    code = str(e)
check("viewer at localhost:8000 returns 200", code == 200, str(code))
if code == 200:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    p = subprocess.run([npx, "playwright", "test", "tests/live.spec.js"], cwd=ROOT, capture_output=True, text=True) if npx else None
    check("Playwright live smoke", bool(p) and p.returncode == 0, "" if p and p.returncode == 0 else (p.stdout[-400:] if p else "npx missing"))
else:
    check("Playwright live smoke", False, "server not running (python -m http.server 8000)")

best = tree.get("best_node_id")
pngs = sorted((ROOT / "frames").glob(f"{best}_*.png")) if best else []
check("frames/ has PNGs for the best node", bool(pngs), f"{best}: {len(pngs)} PNGs")

vid = ROOT / "demo/fallback.mp4"
dur = None
if vid.exists() and shutil.which("ffprobe"):
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(vid)],
                                   capture_output=True, text=True).stdout.strip())
    except ValueError:
        pass
if dur is not None:
    check("demo/fallback.mp4 > 30 s", dur > 30, f"{dur:.0f}s")
else:
    check("demo/fallback.mp4 > 30 s", vid.exists() and vid.stat().st_size > 1_000_000,
          "missing" if not vid.exists() else f"{vid.stat().st_size // 1024} KB (no ffprobe; size heuristic)")

try:
    t0 = datetime.fromisoformat(tree["started_at"])
    mins = int((datetime.now(t0.tzinfo) - t0).total_seconds() // 60)
    elapsed = f"{mins}m" if mins < 60 else f"{mins // 60}h {mins % 60}m"
except Exception:
    elapsed = "?"
done = [n for n in nodes if n.get("status") == "done" and isinstance(n.get("fitness"), (int, float))]
best_f = f"{max(n['fitness'] for n in done):.1f}" if done else "?"

print(f"\n{sum(results)}/{len(results)} PASS\n")
print("=" * 60)
for label, val in [("NODES", len(nodes)), ("EXPERIMENTS", f"{n_rules:,}"), ("ELAPSED", elapsed), ("BEST FITNESS", best_f)]:
    print(f"   {label:<14} {val}")
print("=" * 60)
sys.exit(0 if all(results) else 1)
