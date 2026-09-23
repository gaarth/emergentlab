# IMPLEMENTATION — Muaaz (lab.py: agent loop, sandbox, paper)

You own everything that **writes** `tree.json`. Your teammate only reads it.
Ship order matters: **ca.py → sandbox → loop → paper**. Do not touch the viewer.

Repo layout (create in the first 5 minutes, push to GitHub so both of you pull):

```
discovery-lab/
  lab.py            # you
  ca.py             # you
  viewer.html       # teammate
  render_paper.py   # teammate
  tree.json         # contract — generated, but commit a fake one first
  frames/           # PNGs written by sandbox
  STOP              # touch this file to trigger the paper
```

Deps: `pip install anthropic numpy scipy pillow markdown` — nothing else (`markdown` is for render_paper.py, which lab.py calls).

---

## 0. Minute 0–10: schema + scaffold (with teammate)

1. Paste the tree.json schema from the PRD (section 6) into `tree.json` with **3 fake nodes** (root + 2 children, one with `status: error`). Commit. Teammate builds against this.
2. Ask Claude Code to scaffold `ca.py` and `lab.py` from this document in one shot. Then fix by hand.

---

## 1. Minute 10–25: `ca.py` — the substrate and fitness

Keep this tiny and correct. Fable's experiment code will call into it.

```python
# ca.py
import numpy as np
from scipy.ndimage import label, convolve

GRID_SIZE = 64   # single source of truth; replay.size in tree.json must equal this
KERNEL = np.ones((3, 3), dtype=int); KERNEL[1, 1] = 0

def parse_rule(rule: str):
    """'B36/S23' -> (birth={3,6}, survive={2,3})"""
    b, s = rule.upper().split("/")
    return {int(c) for c in b[1:]}, {int(c) for c in s[1:]}

def step(grid, birth, survive):
    n = convolve(grid, KERNEL, mode="wrap")
    born = (grid == 0) & np.isin(n, list(birth))
    keep = (grid == 1) & np.isin(n, list(survive))
    return (born | keep).astype(np.uint8)

def place(seed, size=GRID_SIZE):
    g = np.zeros((size, size), dtype=np.uint8)
    s = np.array(seed, dtype=np.uint8)
    y, x = (size - s.shape[0]) // 2, (size - s.shape[1]) // 2
    g[y:y+s.shape[0], x:x+s.shape[1]] = s
    return g

def _canon(patch):
    """Canonical form under 8 symmetries, as bytes."""
    p = np.array(patch, dtype=np.uint8)
    forms = []
    for k in range(4):
        r = np.rot90(p, k); forms += [r.tobytes() + bytes(r.shape), np.fliplr(r).tobytes() + bytes(np.fliplr(r).shape)]
    return min(forms)

def count_copies(grid, seed):
    """Connected components whose trimmed bounding box matches the seed under symmetry."""
    target = _canon(np.array(seed))
    lab, n = label(grid, structure=np.ones((3, 3)))
    copies = 0
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        patch = grid[ys.min():ys.max()+1, xs.min():xs.max()+1] * (lab[ys.min():ys.max()+1, xs.min():xs.max()+1] == i)
        if _canon(patch) == target:
            copies += 1
    return copies

def evaluate(rule, seed, steps=60, size=GRID_SIZE, snapshots=(0, 20, 40, 60)):
    birth, survive = parse_rule(rule)
    g = place(seed, size); alive0 = int(g.sum())
    frames, max_copies = {}, 0
    for t in range(steps + 1):
        if t in snapshots: frames[t] = g.copy()
        if t % 5 == 0: max_copies = max(max_copies, count_copies(g, seed))
        g = step(g, birth, survive)
    alive = int(g.sum())
    stable = 0 < alive < 0.30 * size * size
    copies = max(max_copies, count_copies(g, seed))
    fitness = float(copies) if stable else copies * 0.2
    return {"rule": rule, "copies": copies, "alive": alive, "growth": alive / max(alive0, 1),
            "stable": stable, "fitness": fitness, "frames": frames}
```

**Checkpoint (19:05):** `python -c "import ca; print(ca.evaluate('B36/S23', [[0,1,0],[0,1,1],[1,1,0]])['copies'])"` prints a number in < 0.2 s. If `count_copies` is slow, only call it at t % 10.

---

## 2. Minute 25–45: `lab.py` — the loop

### 2.1 Prompt design (this is the whole product)

System prompt — keep it short and strict:

```
You are an autonomous research agent running a cellular-automaton discovery lab.
You will be shown the hypothesis tree so far and full results of recent nodes.
Each turn you propose ONE new experiment node. Respond with ONLY a JSON object:

{
 "parent_id": "<id of the node you are branching from>",
 "hypothesis": "<one sentence, falsifiable, references a parent result>",
 "rules_to_test": ["B3/S23", ...],            // 5–40 rules, valid Life-like strings
 "seed": [[0,1,0],[0,1,1],[1,1,0]],            // small 0/1 matrix, max 7x7
 "experiment_code": "def run(rules, seed, ca):\n    ...\n    return results",
 "notes": "<why this, what would confirm/refute>"
}

experiment_code rules:
- Must define run(rules, seed, ca) returning a list of dicts, one per rule,
  each containing at least ca.evaluate(...)'s keys (call ca.evaluate for the standard metric).
- May add extra metrics. May not import anything except numpy. No file/network access.
- Must finish in < 20 s total.

Research rules:
- Never re-test a rule already in the tree. Branch from the most promising node unless told otherwise.
- Dead ends are valuable: say so in notes and move to a different rule family.
- Rule families to consider: Life-like sweeps, B-only variations around a survive set, known replicators
  (HighLife B36/S23, B3/S23 with specific seeds), Seeds-type explosive rules, isotropic near-neighbors.
```

User message each turn:

```
QUESTION: {question}
TREE SUMMARY (id | parent | depth | best_rule | fitness | hypothesis):
n0 | - | 0 | B36/S23 | 2.0 | Baseline sweep...
...
RECENT NODES (full results, last 5): {json}
RULES ALREADY TESTED: [...]
{directive}   # "" normally; anti-stagnation text when triggered
```

### 2.2 Loop skeleton

```python
# lab.py
import json, time, sys, subprocess, tempfile, textwrap, argparse, os
from datetime import datetime, timezone, timedelta
import anthropic
from PIL import Image
import numpy as np
import ca

IST = timezone(timedelta(hours=5, minutes=30))
MODEL = "claude-fable-5-1"
client = anthropic.Anthropic()

def load(): return json.load(open("tree.json"))
def save(t):
    tmp = "tree.json.tmp"; json.dump(t, open(tmp, "w"), indent=1); os.replace(tmp, "tree.json")  # atomic: viewer never reads a half file

def ask_fable(system, user):
    for attempt in range(3):
        try:
            r = client.messages.create(model=MODEL, max_tokens=4000, system=system,
                                       messages=[{"role": "user", "content": user}])
            txt = r.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(txt)
        except Exception as e:
            print("fable error", e); time.sleep(2 ** attempt)
    return None

def run_sandbox(node):
    """Execute experiment_code in a subprocess with a timeout. Returns list of result dicts."""
    prog = textwrap.dedent(f'''
        import json, sys, numpy as np, ca
        seed = {json.dumps(node["seed"])}
        rules = {json.dumps(node["rules_tested"])}
        {node["experiment_code"]}
        out = run(rules, seed, ca)
        for r in out: r.pop("frames", None)   # frames handled separately
        print(json.dumps(out))
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=".") as f:
        f.write(prog); path = f.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=20)
        if p.returncode != 0: raise RuntimeError(p.stderr[-1500:])
        return json.loads(p.stdout.strip().splitlines()[-1])
    finally:
        os.remove(path)

def write_frames(node_id, rule, seed):
    res = ca.evaluate(rule, seed)
    paths = []
    for t, g in res["frames"].items():
        img = Image.fromarray((255 - g * 255).astype(np.uint8)).resize((256, 256), Image.NEAREST)
        p = f"frames/{node_id}_{t}.png"; img.save(p); paths.append(p)
    return paths

def summary(tree):
    lines = [f'{n["id"]} | {n["parent"]} | {n["depth"]} | {n.get("best_rule")} | {n.get("fitness")} | {n["hypothesis"][:90]}'
             for n in tree["nodes"]]
    return "\n".join(lines)

def directive(tree):
    done = [n for n in tree["nodes"] if n["status"] == "done"]
    if len(done) < 5: return ""
    best = max(n["fitness"] for n in done)
    recent = done[-4:]
    if all(n["fitness"] < best for n in recent):
        top = sorted(done, key=lambda n: -n["fitness"])[:3]
        return ("DIRECTIVE: no improvement in 4 nodes. Branch from one of " + ", ".join(n["id"] for n in top) +
                " OR open a rule family not yet in the tree. Do not continue the latest chain.")
    if len(done) % 8 == 0:
        return "DIRECTIVE: name a rule family you have NOT tried yet and test it."
    return ""

def main(question, minutes):
    tree = load() if os.path.exists("tree.json") else {"question": question, "started_at": datetime.now(IST).isoformat(),
                                                       "status": "running", "best_node_id": None, "nodes": []}
    tree["question"] = question; tree["status"] = "running"; save(tree)
    deadline = time.time() + minutes * 60
    while time.time() < deadline and not os.path.exists("STOP"):
        done = [n for n in tree["nodes"] if n["status"] == "done"]
        tested = sorted({r for n in tree["nodes"] for r in n.get("rules_tested", [])})
        user = (f"QUESTION: {question}\nTREE SUMMARY (id | parent | depth | best_rule | fitness | hypothesis):\n{summary(tree)}\n\n"
                f"RECENT NODES (full results):\n{json.dumps(done[-5:], indent=0)[:12000]}\n\nRULES ALREADY TESTED: {tested}\n{directive(tree)}")
        prop = ask_fable(SYSTEM, user)
        if not prop: continue
        nid = f"n{len(tree['nodes'])}"
        parent = next((n for n in tree["nodes"] if n["id"] == prop.get("parent_id")), None)
        node = {"id": nid, "parent": parent["id"] if parent else None, "depth": (parent["depth"] + 1) if parent else 0,
                "hypothesis": prop["hypothesis"], "rules_tested": [r for r in prop["rules_to_test"] if r not in tested][:40],
                "seed": prop["seed"], "experiment_code": prop["experiment_code"], "notes": prop.get("notes", ""),
                "status": "running", "started_at": datetime.now(IST).isoformat(), "ended_at": None,
                "best_rule": None, "fitness": 0.0, "metrics": {}, "frames": [], "replay": None, "error": None}
        tree["nodes"].append(node); save(tree)
        try:
            results = run_sandbox(node)
            best = max(results, key=lambda r: r["fitness"])
            node.update(best_rule=best["rule"], fitness=best["fitness"],
                        metrics={k: best[k] for k in ("copies", "alive", "growth", "stable")},
                        frames=write_frames(nid, best["rule"], node["seed"]),
                        replay={"rule": best["rule"], "seed": node["seed"], "size": ca.GRID_SIZE, "steps": 60},  # must equal the simulation size; torus wrap differs otherwise,
                        status="done", results_top5=sorted(results, key=lambda r: -r["fitness"])[:5])
            if tree["best_node_id"] is None or node["fitness"] > next(n["fitness"] for n in tree["nodes"] if n["id"] == tree["best_node_id"]):
                tree["best_node_id"] = nid
        except Exception as e:
            node.update(status="error", error=str(e)[-800:])
        node["ended_at"] = datetime.now(IST).isoformat(); save(tree)
        print(nid, node["status"], node.get("best_rule"), node["fitness"])
    write_paper(tree)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--question", required=True); ap.add_argument("--minutes", type=int, default=45)
    a = ap.parse_args(); main(a.question, a.minutes)
```

Things that will bite you (fix pre-emptively):

- **Fable wraps JSON in prose.** The `removeprefix` trick handles fences; if it still fails, find the first `{` and last `}` and slice.
- **`experiment_code` indentation.** Dedent the whole program, not the snippet, and require `run` at column 0 in the prompt.
- **Error nodes must stay in the tree.** They feed back as context ("your last code raised X"). Add `node["error"]` to the RECENT NODES dump.
- **Never let `tested` filtering empty the rule list.** If it does, mark the node error with "all rules already tested" so Fable learns.

**Checkpoint (19:25):** 3 real nodes in tree.json, at least one branching from a non-root parent. Teammate points the viewer at it.

---

## 3. Minute 45–65: run it for real, then `write_paper`

Start the real run **now** and leave it:

```bash
rm -f STOP tree.json; mkdir -p frames
python lab.py --question "Find a Life-like CA rule (B../S..) and a seed of at most 5x5 cells under which the seed self-replicates: after N steps the grid contains 2 or more disjoint copies of the seed." --minutes 60
```

While it runs, write `write_paper`:

```python
PAPER_SYSTEM = """You are writing a short research report from a JSON hypothesis tree produced by an autonomous lab.
Write Markdown with sections: Abstract, Question, Method, Search summary (table of top 5 rules with node id, rule, seed, copies, stable),
Findings, Dead ends, Limitations, Next experiments.
Every number you state must exist in the tree. Cite node ids inline like (n17). Embed frames using ![](frames/xxx.png).
Be honest: if no rule truly self-replicated, say which came closest and why. 600-900 words."""

def write_paper(tree):
    tree["status"] = "writing_paper"; save(tree)
    slim = {"question": tree["question"], "nodes": [{k: v for k, v in n.items() if k != "experiment_code"} for n in tree["nodes"]]}
    r = client.messages.create(model=MODEL, max_tokens=6000, system=PAPER_SYSTEM,
                               messages=[{"role": "user", "content": json.dumps(slim)[:150000]}])
    open("paper.md", "w").write(r.content[0].text)
    tree["status"] = "done"; save(tree)
    subprocess.run([sys.executable, "render_paper.py"])   # teammate's script -> paper.html
```

Test the paper step on a *copy* of the live tree so you don't stop the real run: `cp tree.json test_tree.json` and call `write_paper` in a REPL with that.

---

## 4. Minute 65–90: do not touch the loop

- Watch `tail -f` of the loop output. If it tunnels, add one line to the directive; do not restart.
- At **19:55** `touch STOP` only if you want a paper before rehearsal; otherwise let it run to the demo and generate the paper at 20:15 from a copy (so the tree keeps growing on stage).
- Record the fallback video with the teammate.
- Numbers to have ready for the pitch: node count, total rules evaluated (`sum(len(n["rules_tested"]))`), elapsed minutes, best fitness. Put them in the viewer header; say them out loud.

---

## Claude Code prompts you can paste

1. `Scaffold discovery-lab per IMPLEMENTATION_MUAAZ.md: ca.py, lab.py, a fake tree.json with 3 nodes. Run ca.evaluate on B36/S23 and print copies.`
2. `lab.py: Fable sometimes returns JSON with prose around it. Make ask_fable robust (slice first { to last }), and log raw text on failure to logs/.`
3. `Add --resume to lab.py that continues from an existing tree.json without resetting best_node_id.`