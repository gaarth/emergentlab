"""Mock backend: stands in for lab.py so the viewer can be developed and demoed without the API.

Grows tree.json exactly like the real loop (atomic saves, running -> done/error, frames, replay,
writing_paper -> done + paper.html), but proposals are random mutations instead of Fable calls.
The CA and fitness are real (spec code from IMPLEMENTATION_MUAAZ.md section 1), so replays match frames.

usage: python mock_lab.py [--nodes 50] [--interval 3] [--dir .] [--resume]
Touch STOP to end early and write the paper.
"""
import argparse, json, os, pathlib, random, subprocess, sys, time
from datetime import datetime, timedelta, timezone
import numpy as np
from PIL import Image
from scipy.ndimage import label

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from ca_grid import parse_rule, step, place  # noqa: E402  (spec CA, identical to ca.py)

IST = timezone(timedelta(hours=5, minutes=30))
GRID_SIZE = 64
QUESTION = ("Find a Life-like CA rule (B../S..) and a seed of at most 5x5 cells under which the seed self-replicates: "
            "after N steps the grid contains 2 or more disjoint copies of the seed.")
SEEDS = {
    "glider": [[0, 1, 0], [0, 0, 1], [1, 1, 1]],
    "HighLife replicator": [[0, 0, 1, 1, 1], [0, 1, 0, 0, 1], [1, 0, 0, 0, 1], [1, 0, 0, 1, 0], [1, 1, 1, 0, 0]],
    "R-pentomino": [[0, 1, 1], [1, 1, 0], [0, 1, 0]],
    "T-tetromino": [[1, 1, 1], [0, 1, 0]],
    "pi-heptomino": [[1, 1, 1], [1, 0, 1], [1, 0, 1]],
}
FAMILIES = ["HighLife variants", "B3 sweeps over survive sets", "Seeds-type explosive rules",
            "B-only variations", "sparse birth rules", "survive-heavy rules"]


# ---- spec fitness (ca.py twin) ----
def _canon(p):
    p = np.array(p, dtype=np.uint8); forms = []
    for k in range(4):
        r = np.rot90(p, k); f = np.fliplr(r)
        forms += [r.tobytes() + bytes(r.shape), f.tobytes() + bytes(f.shape)]
    return min(forms)


def count_copies(grid, seed):
    target = _canon(seed); lab, n = label(grid, structure=np.ones((3, 3))); copies = 0
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
        if _canon(grid[sl] * (lab[sl] == i)) == target:
            copies += 1
    return copies


def evaluate(rule, seed, steps=60, size=GRID_SIZE, snapshots=(0, 20, 40, 60)):
    birth, survive = parse_rule(rule)
    g = place(seed, size); alive0 = int(g.sum()); frames, best = {}, 0
    for t in range(steps + 1):
        if t in snapshots: frames[t] = g.copy()
        if t % 5 == 0: best = max(best, count_copies(g, seed))
        if t < steps: g = step(g, birth, survive)
    alive = int(g.sum()); stable = 0 < alive < 0.30 * size * size
    copies = max(best, count_copies(g, seed))
    return {"rule": rule, "copies": copies, "alive": alive, "growth": round(alive / max(alive0, 1), 3),
            "stable": stable, "fitness": float(copies) if stable else round(copies * 0.2, 2), "frames": frames}


# ---- tree io ----
def save(tree, d):
    tmp = d / "tree.json.tmp"
    tmp.write_text(json.dumps(tree, indent=1), encoding="utf-8")
    os.replace(tmp, d / "tree.json")   # atomic: the viewer never reads a half file


def now():
    return datetime.now(IST).replace(microsecond=0).isoformat()


def mutate(rule, rng):
    b, s = parse_rule(rule)
    for part in (b, s):
        if rng.random() < 0.7:
            part.symmetric_difference_update({rng.randint(2 if part is b else 0, 8)})
    b.discard(1)   # B1 rules copy every fragment (B1357/S1357 replicates anything): keeps mock fitness in 0-4
    if not b: b.add(3)
    return "B" + "".join(map(str, sorted(b))) + "/S" + "".join(map(str, sorted(s)))


def propose(tree, rng):
    done = [n for n in tree["nodes"] if n["status"] == "done"]
    tested = {r for n in tree["nodes"] for r in n["rules_tested"]}
    if not done:
        return None, 0, "Baseline: sweep classic rules (Life, HighLife, Seeds) with a glider seed.", \
            ["B3/S23", "B36/S23", "B2/S", "B3/S12345", "B368/S245"], "glider"
    top = sorted(done, key=lambda n: -n["fitness"])[:3]
    parent = rng.choice(top) if rng.random() < 0.6 else rng.choice(done)
    if parent["depth"] >= 7: parent = rng.choice([n for n in done if n["depth"] < 4] or done)
    seed_name = rng.choice(list(SEEDS)) if rng.random() < 0.3 else parent["seed_name"]
    base = parent["best_rule"] or "B36/S23"
    rules = []
    for _ in range(400):
        r = mutate(base if rng.random() < 0.7 else mutate(base, rng), rng)
        if r not in tested and r not in rules: rules.append(r)
        if len(rules) >= rng.randint(8, 30): break
    fam = rng.choice(FAMILIES)
    hyp = (f"{fam} around {base} with the {seed_name} seed should beat {parent['id']}'s fitness "
           f"of {parent['fitness']}.")
    return parent, parent["depth"] + 1, hyp, rules, seed_name


def write_frames(d, nid, res):
    (d / "frames").mkdir(exist_ok=True); paths = []
    for t, g in res["frames"].items():
        p = f"frames/{nid}_{t}.png"
        Image.fromarray((255 - g * 255).astype(np.uint8)).resize((256, 256), Image.NEAREST).save(d / p)
        paths.append(p)
    return paths


def write_paper(tree, d):
    tree["status"] = "writing_paper"; save(tree, d); time.sleep(2)
    done = sorted([n for n in tree["nodes"] if n["status"] == "done"], key=lambda n: -n["fitness"])
    best = done[0] if done else None
    errs = [n for n in tree["nodes"] if n["status"] == "error"]
    worst = [n for n in done if n["metrics"].get("stable") is False][:2]
    rows = "\n".join(f"| {n['id']} | {n['best_rule']} | {n['seed_name']} | {n['metrics']['copies']} | "
                     f"{n['metrics']['stable']} | {n['fitness']} |" for n in done[:5])
    n_rules = sum(len(n["rules_tested"]) for n in tree["nodes"])
    figs = " ".join(f"![{best['id']} t={t}](frames/{best['id']}_{t}.png)" for t in (0, 20, 40, 60)) if best else ""
    md = f"""# Toward self-replication in Life-like cellular automata

*MOCK PAPER generated by mock_lab.py, not by Fable.*

## Abstract

Across {len(tree['nodes'])} nodes and {n_rules} rule evaluations, the strongest candidate was
{best['best_rule'] if best else '-'} with fitness {best['fitness'] if best else '-'} ({best['id'] if best else '-'}).

## Question

{tree['question']}

## Method

Each node mutates the best rule of a parent node, simulates 60 steps on a 64x64 torus, and counts connected
components matching the seed under rotation and reflection. Fitness is the copy count, scaled by 0.2 when unstable.

## Search summary

| node | rule | seed | copies | stable | fitness |
|------|------|------|--------|--------|---------|
{rows}

{figs}

## Findings

The best node {f"({best['id']})" if best else ""} branched from {best['parent'] if best else '-'}.

## Dead ends

{"; ".join(f"{n['best_rule']} was unstable ({n['id']})" for n in worst) or "None recorded."}
{len(errs)} nodes failed with errors{f" ({errs[0]['id']})" if errs else ""}.

## Limitations

The copy counter is a proxy and the proposals here are random mutations, not model reasoning.

## Next experiments

Replace this mock with the real Fable loop.
"""
    (d / "paper.md").write_text(md, encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "render_paper.py")], cwd=d)
    tree["status"] = "done"; save(tree, d)


def main(nodes, interval, d, resume, seed):
    rng = random.Random(seed)
    d.mkdir(parents=True, exist_ok=True)
    if resume and (d / "tree.json").exists():
        tree = json.loads((d / "tree.json").read_text(encoding="utf-8"))
    else:
        tree = {"question": QUESTION, "started_at": now(), "status": "running", "best_node_id": None, "nodes": []}
    tree["status"] = "running"; save(tree, d)
    while len(tree["nodes"]) < nodes and not (d / "STOP").exists():
        parent, depth, hyp, rules, seed_name = propose(tree, rng)
        nid = f"n{len(tree['nodes'])}"
        node = {"id": nid, "parent": parent["id"] if parent else None, "depth": depth if parent else 0,
                "hypothesis": hyp, "rules_tested": rules, "seed": SEEDS[seed_name], "seed_name": seed_name,
                "experiment_code": "def run(rules, seed, ca):\n    return [ca.evaluate(r, seed) for r in rules]\n",
                "notes": f"If {seed_name} copies rise above {parent['metrics'].get('copies', 0) if parent else 0}, "
                         f"keep branching here; otherwise mark it a dead end.",
                "status": "running", "started_at": now(), "ended_at": None, "best_rule": None, "fitness": 0.0,
                "metrics": {}, "frames": [], "replay": None, "error": None}
        tree["nodes"].append(node); save(tree, d)
        time.sleep(interval * 0.5)
        if parent and rng.random() < 0.1:
            node.update(status="error", error="Traceback (most recent call last):\n  File \"tmp_exp.py\", line 6, in run\n"
                                              "    return [ca.evaluate(r, seed)['copy_count'] for r in rules]\nKeyError: 'copy_count'")
        else:
            results = [evaluate(r, node["seed"]) for r in rules]
            best = max(results, key=lambda r: r["fitness"])
            node.update(best_rule=best["rule"], fitness=best["fitness"],
                        metrics={k: best[k] for k in ("copies", "alive", "growth", "stable")},
                        frames=write_frames(d, nid, best),
                        replay={"rule": best["rule"], "seed": node["seed"], "size": GRID_SIZE, "steps": 60},
                        results_top5=[{k: v for k, v in r.items() if k != "frames"}
                                      for r in sorted(results, key=lambda r: -r["fitness"])[:5]],
                        status="done")
            cur = next((n for n in tree["nodes"] if n["id"] == tree["best_node_id"]), None)
            if cur is None or node["fitness"] > cur["fitness"]:
                tree["best_node_id"] = nid
        node["ended_at"] = now(); save(tree, d)
        print(nid, node["status"], node["best_rule"], node["fitness"], flush=True)
        time.sleep(interval * 0.5)
    write_paper(tree, d)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", type=int, default=50); ap.add_argument("--interval", type=float, default=3)
    ap.add_argument("--dir", default=str(ROOT)); ap.add_argument("--resume", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    main(a.nodes, a.interval, pathlib.Path(a.dir), a.resume, a.seed)
