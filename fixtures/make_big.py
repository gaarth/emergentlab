"""Generate fixtures/tree_big.json (45 nodes) and fixtures/paper_fake.md.

Deterministic (fixed seed). Run from repo root: python fixtures/make_big.py
"""
import json, random, pathlib
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
HERE = pathlib.Path(__file__).parent
rng = random.Random(42)

SEEDS = [
    [[0, 1, 0], [0, 0, 1], [1, 1, 1]],
    [[0, 0, 1, 1, 1], [0, 1, 0, 0, 1], [1, 0, 0, 0, 1], [1, 0, 0, 1, 0], [1, 1, 1, 0, 0]],
    [[1, 1, 0], [0, 1, 1], [0, 1, 0]],
    [[1, 1], [1, 1]],
]
FAMILIES = ["HighLife variants", "Seeds-type explosive rules", "B3 sweeps over survive sets",
            "B-only variations", "isotropic near-neighbours", "sparse birth rules"]


def rand_rule():
    b = sorted(rng.sample(range(1, 9), rng.randint(1, 3)))
    s = sorted(rng.sample(range(0, 9), rng.randint(0, 3)))
    return "B" + "".join(map(str, b)) + "/S" + "".join(map(str, s))


def make_tree():
    start = datetime.now(IST).replace(microsecond=0) - timedelta(minutes=37)
    nodes = []
    for i in range(45):
        nid = f"n{i}"
        if i == 0:
            parent, depth = None, 0
        elif i in (13, 29):  # deliberate orphans: parent id does not exist
            parent, depth = f"n{900 + i}", 1
        else:
            p = rng.choice([n for n in nodes if n["depth"] < 6])
            parent, depth = p["id"], p["depth"] + 1
        t0 = start + timedelta(seconds=45 * i)
        rules = sorted({rand_rule() for _ in range(rng.randint(5, 40))})
        seed = rng.choice(SEEDS)
        fam = rng.choice(FAMILIES)
        node = {
            "id": nid, "parent": parent, "depth": depth,
            "hypothesis": f"Test {fam} branching from {parent or 'scratch'}: expect more copies than the parent.",
            "rules_tested": rules, "seed": seed,
            "experiment_code": "def run(rules, seed, ca):\n    return [ca.evaluate(r, seed) for r in rules]\n",
            "status": "done", "started_at": t0.isoformat(), "ended_at": (t0 + timedelta(seconds=30)).isoformat(),
            "best_rule": None, "fitness": 0.0, "metrics": {}, "frames": [], "replay": None,
            "notes": f"Explored {fam}.", "error": None,
        }
        last = i == 44
        if last:
            node.update(status="running", ended_at=None)
        elif rng.random() < 0.10 or i in (7, 21):
            node.update(status="error",
                        error="Traceback (most recent call last):\n  File \"exp.py\", line 5, in run\nKeyError: 'copies'")
        else:
            best = rng.choice(rules)
            copies = rng.randint(0, 4)
            stable = rng.random() < 0.75
            fitness = round(float(copies) if stable else copies * 0.2, 2)
            if i == 31:  # unique, clear winner
                best, copies, stable, fitness = "B36/S23", 4, True, 4.0
            elif fitness >= 4.0:
                fitness = 3.0
            node.update(best_rule=best, fitness=fitness,
                        metrics={"copies": copies, "alive": rng.randint(5, 900),
                                 "growth": round(rng.uniform(0.1, 20), 2), "stable": stable},
                        frames=[f"frames/{nid}_{t}.png" for t in (0, 20, 40, 60)],
                        replay={"rule": best, "seed": seed, "size": 64, "steps": 60})
        nodes.append(node)
    done = [n for n in nodes if n["status"] == "done"]
    best_id = max(done, key=lambda n: n["fitness"])["id"]
    return {"question": "Find a Life-like CA rule (B../S..) and a seed of at most 5x5 cells under which the seed "
                        "self-replicates: after N steps the grid contains 2 or more disjoint copies of the seed.",
            "started_at": start.isoformat(), "status": "running", "best_node_id": best_id, "nodes": nodes}


def make_paper(tree):
    done = sorted([n for n in tree["nodes"] if n["status"] == "done"], key=lambda n: -n["fitness"])[:5]
    rows = "\n".join(f"| {n['id']} | {n['best_rule']} | {json.dumps(n['replay']['seed'])} | "
                     f"{n['metrics']['copies']} | {n['metrics']['stable']} |" for n in done)
    best = done[0]
    n_nodes = len(tree["nodes"])
    n_rules = sum(len(n["rules_tested"]) for n in tree["nodes"])
    return f"""# Self-replication in Life-like cellular automata: an autonomous search

## Abstract

An autonomous agent explored {n_nodes} hypothesis nodes and evaluated {n_rules} rules. The strongest candidate was
{best['best_rule']} with fitness {best['fitness']} ({best['id']}).

## Question

{tree['question']}

## Method

Each node proposes rules and a seed, simulates 60 steps on a 64x64 torus, and counts disjoint copies of the seed.

## Search summary

| node | rule | seed | copies | stable |
|------|------|------|--------|--------|
{rows}

![](frames/n0_20.png)

## Findings

The HighLife family dominated the frontier (n17), and the best node refined it further ({best['id']}).

## Dead ends

Seeds-type explosive rules filled the grid and scored low (n3).

## Limitations

The copy counter is a proxy; it cannot distinguish replication from coincidental debris.

## Next experiments

Larger seeds, longer runs, and a translation-aware copy metric.
"""


if __name__ == "__main__":
    tree = make_tree()
    (HERE / "tree_big.json").write_text(json.dumps(tree, indent=1), encoding="utf-8")
    (HERE / "paper_fake.md").write_text(make_paper(tree), encoding="utf-8")
    print("wrote tree_big.json and paper_fake.md;", len(tree["nodes"]), "nodes, best", tree["best_node_id"])
