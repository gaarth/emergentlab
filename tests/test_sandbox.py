"""L2: run_sandbox."""
import glob, os, time
import pytest
import lab

SEED = [[0, 1, 0], [0, 0, 1], [1, 1, 1]]
GOOD = "def run(rules, seed, ca):\n    return [ca.evaluate(r, seed) for r in rules]\n"


@pytest.fixture(autouse=True)
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def node(code, rules=("B3/S23", "B36/S23")):
    return {"experiment_code": code, "seed": SEED, "rules_tested": list(rules)}


def test_valid_code():
    out = lab.run_sandbox(node(GOOD))
    assert len(out) == 2
    for r in out:
        assert "fitness" in r and "frames" not in r


def test_raises_carries_message():
    code = "def run(rules, seed, ca):\n    raise ValueError('kaboom-42')\n"
    with pytest.raises(RuntimeError, match="kaboom-42"):
        lab.run_sandbox(node(code))


def test_timeout():
    code = "def run(rules, seed, ca):\n    while True:\n        pass\n"
    t = time.time()
    with pytest.raises(RuntimeError, match="timed out"):
        lab.run_sandbox(node(code))
    assert time.time() - t <= 21


@pytest.mark.parametrize("code", [
    "import os\ndef run(rules, seed, ca):\n    return []\n",
    "def run(rules, seed, ca):\n    open('x', 'w')\n    return []\n",
    "import requests\ndef run(rules, seed, ca):\n    return []\n",
])
def test_rejected_before_execution(code, monkeypatch):
    called = []
    monkeypatch.setattr(lab.subprocess, "run", lambda *a, **k: called.append(1))
    with pytest.raises(ValueError):
        lab.run_sandbox(node(code))
    assert not called


def test_indented_code_dedented():
    code = "\n".join("    " + l for l in GOOD.splitlines())
    out = lab.run_sandbox(node(code))
    assert len(out) == 2


def test_tempfile_deleted_on_failure(in_tmp):
    code = "def run(rules, seed, ca):\n    raise ValueError('x')\n"
    with pytest.raises(RuntimeError):
        lab.run_sandbox(node(code))
    assert glob.glob(str(in_tmp / "*.py")) == []
    lab.run_sandbox(node(GOOD))
    assert glob.glob(str(in_tmp / "*.py")) == []
