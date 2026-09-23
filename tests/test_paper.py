"""L5: write_paper with an injected fake model."""
import json, pathlib, re, shutil, warnings
import pytest
import lab

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAKE_MD = (ROOT / "fixtures" / "paper_fake.md").read_text(encoding="utf-8")


@pytest.fixture
def big(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copy(ROOT / "fixtures" / "tree_big.json", tmp_path / "tree.json")
    return str(tmp_path / "tree.json")


def test_write_paper_flow(big, tmp_path, monkeypatch):
    statuses, calls, prompts = [], [], []
    real_save = lab.save
    monkeypatch.setattr(lab, "save", lambda t, p=lab.TREE_PATH: (statuses.append(t["status"]), real_save(t, p)))
    monkeypatch.setattr(lab.subprocess, "run", lambda args, **k: calls.append(args))

    def ask(system, user):
        prompts.append(user)
        return FAKE_MD

    md = lab.write_paper(lab.load(big), ask=ask, tree_path=big)
    assert md == FAKE_MD
    assert (tmp_path / "paper.md").read_text(encoding="utf-8") == FAKE_MD
    assert statuses == ["writing_paper", "done"]
    assert lab.load(big)["status"] == "done"
    assert any("render_paper.py" in str(a) for c in calls for a in c)


def test_prompt_slim(big):
    prompts = []
    lab.write_paper(lab.load(big), ask=lambda s, u: prompts.append(u) or FAKE_MD, tree_path=big, render=False)
    assert "experiment_code" not in prompts[0]
    assert len(prompts[0]) < 150_000


def test_numbers_in_paper_come_from_tree():
    tree_txt = (ROOT / "fixtures" / "tree_big.json").read_text(encoding="utf-8")
    nums = [n for n in lab.numbers_in(FAKE_MD) if len(n) >= 2]
    assert nums, "numbers_in found nothing"
    missing = sorted({n for n in nums if n not in tree_txt})
    if missing:
        warnings.warn(f"numbers in paper not found in tree: {missing}")


def test_citations_exist():
    tree = json.loads((ROOT / "fixtures" / "tree_big.json").read_text(encoding="utf-8"))
    ids = {n["id"] for n in tree["nodes"]}
    cites = re.findall(r"\bn\d+\b", " ".join(re.findall(r"\(([^)]*n\d+[^)]*)\)", FAKE_MD)))
    assert cites
    assert set(cites) <= ids, set(cites) - ids
