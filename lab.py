"""Autonomous discovery lab: propose -> sandbox -> append node -> repeat -> write paper.

Owns tree.json. The viewer only ever reads it, so every write is atomic.
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image

import ca

IST = timezone(timedelta(hours=5, minutes=30))
MODEL = "claude-fable-5-1"
TREE_PATH = "tree.json"
STOP_FILE = "STOP"
SANDBOX_TIMEOUT = 20

SYSTEM = """You are an autonomous research agent running a cellular-automaton discovery lab.
You will be shown the hypothesis tree so far and full results of recent nodes.
Each turn you propose ONE new experiment node.

Respond with a single JSON object and nothing else. No markdown fences, no prose.

{
 "parent_id": "<id of the node you are branching from>",
 "hypothesis": "<one sentence, falsifiable, references a parent result>",
 "rules_to_test": ["B3/S23", "..."],
 "seed": [[0,1,0],[0,1,1],[1,1,0]],
 "experiment_code": "def run(rules, seed, ca):\\n    ...\\n    return results",
 "notes": "<why this, what would confirm/refute>"
}

experiment_code rules:
- Must define run(rules, seed, ca) at column 0, returning a list of dicts, one per rule,
  each containing at least ca.evaluate(...)'s keys (call ca.evaluate for the standard metric).
- May add extra metrics. May import numpy only. No file, network, os or subprocess access.
- Must finish in < 20 s total.
- rules_to_test: 5-40 valid Life-like strings. seed: 0/1 matrix, max 7x7.

Research rules:
- Never re-test a rule already in the tree. Branch from the most promising node unless told otherwise.
- Dead ends are valuable: say so in notes and move to a different rule family.
- Rule families to consider: Life-like sweeps, B-only variations around a survive set, known
  replicators (HighLife B36/S23), Seeds-type explosive rules, isotropic near-neighbours."""

PAPER_SYSTEM = """You are writing a short research report from a JSON hypothesis tree produced by an autonomous lab.
Write Markdown with sections: Abstract, Question, Method, Search summary (table of top 5 rules with node id,
rule, seed, copies, stable), Findings, Dead ends, Limitations, Next experiments.
Every number you state must exist in the tree. Every number must come from the JSON; do not round or estimate.
Cite node ids inline like (n17). Embed frames using ![](frames/xxx.png).
Be honest: if no rule truly self-replicated, say which came closest and why. 600-900 words."""

_client = None


def get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


# ---------------------------------------------------------------- tree io

def load(path=TREE_PATH):
    with open(path) as f:
        return json.load(f)


def save(tree, path=TREE_PATH):
    """Atomic: the viewer polling this file never sees a half-written JSON."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(tree, f, indent=1)
    os.replace(tmp, path)


# ---------------------------------------------------------------- model io

def extract_json(txt):
    """Fable wraps JSON in prose and fences. Slice first { to last }."""
    if not txt:
        return None
    t = txt.strip()
    if "```" in t:
        t = re.sub(r"```(?:json)?", "", t)
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1 or j < i:
        return None
    try:
        return json.loads(t[i:j + 1])
    except json.JSONDecodeError:
        return None


def ask_fable(system, user, max_tokens=4000):
    for attempt in range(3):
        try:
            r = get_client().messages.create(
                model=MODEL, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}])
            txt = r.content[0].text
            os.makedirs("logs", exist_ok=True)
            with open("logs/raw.log", "a") as f:
                f.write(f"\n===== {datetime.now(IST).isoformat()} =====\n{txt}\n")
            got = extract_json(txt)
            if got is not None:
                return got
            print("fable: unparseable JSON, retrying")
        except Exception as e:
            print("fable error", e)
        time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------- sandbox

ALLOWED_IMPORTS = {"numpy", "math", "itertools", "ca", "random"}
BANNED_NAMES = {"open", "eval", "exec", "compile", "__import__", "input", "breakpoint"}


def check_code(code):
    """Cheap static gate. Not a prison: see NOTES.md for the limits."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"experiment_code does not parse: {e}")
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise ValueError(f"disallowed import: {a.name}")
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                raise ValueError(f"disallowed import: {n.module}")
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id in BANNED_NAMES:
                raise ValueError(f"disallowed call: {n.func.id}()")
        elif isinstance(n, ast.Attribute) and n.attr.startswith("__"):
            raise ValueError(f"disallowed dunder access: {n.attr}")
    return True


def run_sandbox(node, timeout=SANDBOX_TIMEOUT):
    """Execute experiment_code in a subprocess. Returns list of result dicts."""
    code = textwrap.dedent(node["experiment_code"]).strip("\n")
    check_code(code)
    prog = "\n".join([
        "import json, sys",
        "import numpy as np",
        "import ca",
        f"seed = {json.dumps(node['seed'])}",
        f"rules = {json.dumps(node['rules_tested'])}",
        code,
        "out = run(rules, seed, ca)",
        "out = [dict(r) for r in out]",
        'for r in out: r.pop("frames", None)',
        "print(json.dumps(out))",
    ])
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=".") as f:
            f.write(prog)
            path = f.name
        try:
            p = subprocess.run([sys.executable, path], capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"experiment timed out after {timeout}s")
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-1500:])
        lines = [l for l in p.stdout.strip().splitlines() if l.strip()]
        if not lines:
            raise RuntimeError("experiment produced no output")
        return json.loads(lines[-1])
    finally:
        if path and os.path.exists(path):
            os.remove(path)


def write_frames(node_id, rule, seed):
    os.makedirs("frames", exist_ok=True)
    res = ca.evaluate(rule, seed)
    paths = []
    for t, g in sorted(res["frames"].items()):
        img = Image.fromarray((255 - g * 255).astype(np.uint8)).resize((256, 256), Image.NEAREST)
        p = f"frames/{node_id}_{t}.png"
        img.save(p)
        paths.append(p)
    return paths


# ---------------------------------------------------------------- prompting

def summary(tree):
    return "\n".join(
        f'{n["id"]} | {n.get("parent")} | {n.get("depth")} | {n.get("best_rule")} | '
        f'{n.get("fitness")} | {str(n.get("hypothesis", ""))[:90]}'
        for n in tree["nodes"])


def directive(tree):
    done = [n for n in tree["nodes"] if n["status"] == "done"]
    if len(done) < 5:
        return ""
    best = max(n["fitness"] for n in done)
    if all(n["fitness"] < best for n in done[-4:]):
        top = sorted(done, key=lambda n: -n["fitness"])[:3]
        return ("DIRECTIVE: no improvement in 4 nodes. Branch from one of "
                + ", ".join(n["id"] for n in top)
                + " OR open a rule family not yet in the tree. Do not continue the latest chain.")
    if len(done) % 8 == 0:
        return "DIRECTIVE: name a rule family you have NOT tried yet and test it."
    return ""


def build_user(tree, question):
    done = [n for n in tree["nodes"] if n["status"] == "done"]
    tested = sorted({r for n in tree["nodes"] for r in n.get("rules_tested", [])})
    recent = [{k: v for k, v in n.items() if k != "experiment_code"} for n in tree["nodes"][-5:]]
    return (f"QUESTION: {question}\n"
            f"TREE SUMMARY (id | parent | depth | best_rule | fitness | hypothesis):\n{summary(tree)}\n\n"
            f"RECENT NODES (full results, errors included):\n{json.dumps(recent, indent=0)[:12000]}\n\n"
            f"RULES ALREADY TESTED: {tested}\n{directive(tree)}")


# ---------------------------------------------------------------- paper

def numbers_in(text):
    """Every numeric literal in the paper, for the honesty guard."""
    return re.findall(r"\d+(?:\.\d+)?", text or "")


def write_paper(tree, ask=None, tree_path=TREE_PATH, render=True):
    tree["status"] = "writing_paper"
    save(tree, tree_path)
    slim = {"question": tree.get("question"),
            "nodes": [{k: v for k, v in n.items() if k != "experiment_code"} for n in tree["nodes"]]}
    payload = json.dumps(slim)[:150000]
    if ask is None:
        def ask(system, user):
            r = get_client().messages.create(model=MODEL, max_tokens=6000, system=system,
                                             messages=[{"role": "user", "content": user}])
            return r.content[0].text
    md = ask(PAPER_SYSTEM, payload)
    with open("paper.md", "w", encoding="utf-8") as f:
        f.write(md or "")
    tree["status"] = "done"
    save(tree, tree_path)
    if render and os.path.exists("render_paper.py"):
        subprocess.run([sys.executable, "render_paper.py"])
    return md


# ---------------------------------------------------------------- loop

def main(question, minutes, ask=None, tree_path=TREE_PATH, paper_fn=None, max_nodes=None):
    ask = ask or ask_fable
    paper_fn = paper_fn or write_paper
    if os.path.exists(tree_path):
        tree = load(tree_path)
    else:
        tree = {"question": question, "started_at": datetime.now(IST).isoformat(),
                "status": "running", "best_node_id": None, "nodes": []}
    tree["question"] = question
    tree["status"] = "running"
    tree.setdefault("best_node_id", None)
    save(tree, tree_path)

    deadline = time.time() + minutes * 60
    added = 0
    while time.time() < deadline and not os.path.exists(STOP_FILE):
        if max_nodes is not None and added >= max_nodes:
            break
        tested = sorted({r for n in tree["nodes"] for r in n.get("rules_tested", [])})
        prop = ask(SYSTEM, build_user(tree, question))
        if not prop:
            continue
        nid = f"n{len(tree['nodes'])}"
        parent = next((n for n in tree["nodes"] if n["id"] == prop.get("parent_id")), None)
        fresh = [r for r in prop.get("rules_to_test", []) if r not in tested][:40]
        node = {"id": nid, "parent": parent["id"] if parent else None,
                "depth": (parent["depth"] + 1) if parent else 0,
                "hypothesis": prop.get("hypothesis", ""), "rules_tested": fresh,
                "seed": prop.get("seed"), "experiment_code": prop.get("experiment_code", ""),
                "notes": prop.get("notes", ""), "status": "running",
                "started_at": datetime.now(IST).isoformat(), "ended_at": None,
                "best_rule": None, "fitness": 0.0, "metrics": {}, "frames": [],
                "replay": None, "error": None}
        tree["nodes"].append(node)
        save(tree, tree_path)
        added += 1
        try:
            if not fresh:
                raise RuntimeError("all proposed rules were already tested; propose an untested rule family")
            results = run_sandbox(node)
            if not results:
                raise RuntimeError("experiment returned no results")
            best = max(results, key=lambda r: r.get("fitness", 0))
            node.update(best_rule=best["rule"], fitness=float(best.get("fitness", 0.0)),
                        metrics={k: best.get(k) for k in ("copies", "alive", "growth", "stable")},
                        frames=write_frames(nid, best["rule"], node["seed"]),
                        replay={"rule": best["rule"], "seed": node["seed"],
                                "size": ca.GRID_SIZE, "steps": 60},
                        status="done",
                        results_top5=sorted(results, key=lambda r: -r.get("fitness", 0))[:5])
            cur = tree.get("best_node_id")
            cur_fit = next((n["fitness"] for n in tree["nodes"] if n["id"] == cur), None)
            if cur is None or node["fitness"] > cur_fit:
                tree["best_node_id"] = nid
        except Exception as e:
            node.update(status="error", error=str(e)[-800:])
        node["ended_at"] = datetime.now(IST).isoformat()
        save(tree, tree_path)
        print(nid, node["status"], node.get("best_rule"), node["fitness"], flush=True)
    paper_fn(tree, tree_path=tree_path)
    return tree


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", required=True)
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--tree", default=TREE_PATH)
    a = ap.parse_args()
    main(a.question, a.minutes, tree_path=a.tree)
