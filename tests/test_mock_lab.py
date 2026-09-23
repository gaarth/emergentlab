"""The mock backend must produce a contract-valid tree, frames, and a rendered paper."""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
from test_contract import NODE_KEYS, TOP_KEYS  # noqa: E402


def test_mock_run(tmp_path):
    p = subprocess.run([sys.executable, str(ROOT / "mock_lab.py"), "--nodes", "6", "--interval", "0", "--dir", str(tmp_path)],
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    tree = json.loads((tmp_path / "tree.json").read_text(encoding="utf-8"))
    assert TOP_KEYS <= tree.keys() and tree["status"] == "done"
    assert len(tree["nodes"]) == 6
    for n in tree["nodes"]:
        assert NODE_KEYS <= n.keys()
        if n["parent"] is not None:
            parent = next(x for x in tree["nodes"] if x["id"] == n["parent"])
            assert n["depth"] == parent["depth"] + 1
        if n["status"] == "done":
            assert n["replay"]["size"] == 64 and all((tmp_path / f).exists() for f in n["frames"])
    done = [n for n in tree["nodes"] if n["status"] == "done"]
    best = next(n for n in tree["nodes"] if n["id"] == tree["best_node_id"])
    assert best["fitness"] == max(n["fitness"] for n in done)
    html = (tmp_path / "paper.html").read_text(encoding="utf-8")
    assert "data:image/png;base64," in html and "<table>" in html


def test_highlife_replicator_detected():
    """Sanity check from L1: the fitness can see replication at all."""
    import mock_lab
    r = mock_lab.evaluate("B36/S23", mock_lab.SEEDS["HighLife replicator"])
    assert r["copies"] >= 2, r
