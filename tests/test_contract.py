"""tree.json contract: every fixture (and the live tree.json, if present) must satisfy the PRD section 6 schema."""
import json, pathlib, numbers
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TREES = sorted((ROOT / "fixtures").glob("tree_*.json")) + [p for p in [ROOT / "tree.json"] if p.exists()]

TOP_KEYS = {"question", "started_at", "status", "best_node_id", "nodes"}
NODE_KEYS = {"id", "parent", "depth", "hypothesis", "rules_tested", "status", "started_at", "ended_at",
             "best_rule", "fitness", "metrics", "frames", "replay", "notes", "error"}


@pytest.fixture(params=TREES, ids=lambda p: p.name)
def tree(request):
    return json.loads(request.param.read_text(encoding="utf-8"))


def test_top_level(tree):
    assert TOP_KEYS <= tree.keys()
    assert tree["status"] in {"running", "writing_paper", "done"}
    assert isinstance(tree["nodes"], list)


def test_nodes(tree):
    ids = [n["id"] for n in tree["nodes"]]
    assert len(ids) == len(set(ids)), "duplicate node ids"
    for n in tree["nodes"]:
        missing = NODE_KEYS - n.keys()
        assert not missing, f"{n.get('id')} missing {missing}"
        assert n["status"] in {"pending", "running", "done", "error"}
        assert isinstance(n["fitness"], numbers.Number) and not isinstance(n["fitness"], bool)
        assert isinstance(n["rules_tested"], list) and isinstance(n["frames"], list)
        assert isinstance(n["depth"], int)
        if n["replay"] is not None:
            assert {"rule", "seed", "size", "steps"} <= n["replay"].keys()
        if n["status"] == "error":
            assert n["error"], f"{n['id']} is error with empty error text"


def test_best_node(tree):
    done = [n for n in tree["nodes"] if n["status"] == "done"]
    if not done:
        assert tree["best_node_id"] is None
        return
    best = next((n for n in tree["nodes"] if n["id"] == tree["best_node_id"]), None)
    assert best is not None, f"best_node_id {tree['best_node_id']} not in tree"
    assert best["fitness"] == max(n["fitness"] for n in done)
