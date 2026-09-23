"""L3: lab.py loop with a scripted fake model."""
import itertools, json, os, pathlib, shutil, threading
import pytest
import ca
import lab

ROOT = pathlib.Path(__file__).resolve().parent.parent
Q = "test question"
SEED = [[0, 1, 0], [0, 0, 1], [1, 1, 1]]
EVAL = "def run(rules, seed, ca):\n    return [ca.evaluate(r, seed) for r in rules]\n"
_rules = (f"B{b}/S{s}" for b, s in itertools.product(["1", "13", "14", "15", "17", "18", "134", "135", "137", "145"],
                                                      ["", "0", "01", "04", "05", "08", "12", "123", "1234"]))


def fixed(fit):
    """experiment_code whose every result has the given fitness."""
    return f"def run(rules, seed, ca):\n    return [dict(ca.evaluate(r, seed), fitness={fit}) for r in rules]\n"


def prop(code=EVAL, parent="n1", rules=None):
    return {"parent_id": parent, "hypothesis": "h: " + parent, "rules_to_test": rules or [next(_rules), next(_rules)],
            "seed": SEED, "experiment_code": code, "notes": "n"}


class FakeFable:
    def __init__(self, props):
        self.props = list(props)
        self.users = []

    def __call__(self, system, user):
        self.users.append(user)
        return self.props.pop(0) if self.props else None


@pytest.fixture
def tree_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copy(ROOT / "fixtures" / "tree_small.json", tmp_path / "tree.json")
    return str(tmp_path / "tree.json")


def run(fake, tree_path, n, paper=None):
    return lab.main(Q, 999, ask=fake, tree_path=tree_path,
                    paper_fn=paper or (lambda t, tree_path=None: None), max_nodes=n)


def test_three_nodes(tree_path):
    run(FakeFable([prop(parent="n0"), prop(parent="n1"), prop(parent="n1")]), tree_path, 3)
    t = lab.load(tree_path)
    new = t["nodes"][3:]
    assert [n["id"] for n in new] == ["n3", "n4", "n5"]
    by = {n["id"]: n for n in t["nodes"]}
    for n in new:
        assert n["status"] == "done"
        assert n["parent"] in by and n["depth"] == by[n["parent"]]["depth"] + 1
        assert len(n["frames"]) == 4 and all(os.path.exists(p) for p in n["frames"])
        assert set(n["replay"]) >= {"rule", "seed", "size", "steps"}


def test_broken_code_feeds_error_back(tree_path):
    bad = "def run(rules, seed, ca):\n    raise ValueError('unique-boom-777')\n"
    fake = FakeFable([prop(code=bad), prop()])
    run(fake, tree_path, 2)
    n3 = lab.load(tree_path)["nodes"][3]
    assert n3["status"] == "error" and n3["error"]
    assert "unique-boom-777" in n3["error"]
    assert "unique-boom-777" in fake.users[1]


def test_already_tested_skips_sandbox(tree_path, monkeypatch):
    calls = []
    monkeypatch.setattr(lab, "run_sandbox", lambda *a, **k: calls.append(1))
    run(FakeFable([prop(rules=["B3/S23", "B36/S23"])]), tree_path, 1)
    n3 = lab.load(tree_path)["nodes"][3]
    assert n3["status"] == "error" and "already tested" in n3["error"]
    assert not calls


def test_best_only_on_strict_improvement(tree_path):
    # fixture best is n1 with fitness 2.0
    run(FakeFable([prop(code=fixed(2.0))]), tree_path, 1)
    assert lab.load(tree_path)["best_node_id"] == "n1"
    run(FakeFable([prop(code=fixed(3.0))]), tree_path, 1)
    assert lab.load(tree_path)["best_node_id"] == "n4"
    run(FakeFable([prop(code=fixed(3.0))]), tree_path, 1)
    assert lab.load(tree_path)["best_node_id"] == "n4"


def test_replay_size_matches_grid(tree_path):
    run(FakeFable([prop(), prop()]), tree_path, 2)
    for n in lab.load(tree_path)["nodes"][3:]:
        assert n["status"] == "done"
        assert n["replay"]["size"] == ca.GRID_SIZE


def test_anti_stagnation_directive(tree_path):
    fake = FakeFable([prop(code=fixed(0.5)) for _ in range(5)])
    run(fake, tree_path, 5)
    assert "DIRECTIVE" not in fake.users[3]
    msg = fake.users[4]  # after 4 done nodes with no improvement
    assert "DIRECTIVE" in msg
    assert all(i in msg for i in ("n1", "n0", "n3"))


def test_every_eighth_done_new_family(tree_path):
    # fixture has 2 done; 6 improving nodes -> 8 done before the 7th prompt
    fake = FakeFable([prop(code=fixed(3.0 + i)) for i in range(7)])
    run(fake, tree_path, 7)
    assert "rule family you have NOT tried" in fake.users[6]
    assert "rule family you have NOT tried" not in fake.users[5]


def test_save_uses_os_replace(tmp_path, monkeypatch):
    used = []
    real = os.replace
    monkeypatch.setattr(lab.os, "replace", lambda a, b: (used.append((a, b)), real(a, b)))
    lab.save({"x": 1}, str(tmp_path / "t.json"))
    assert used


def test_save_atomic_under_concurrent_reads(tmp_path):
    p = str(tmp_path / "t.json")
    big = json.loads((ROOT / "fixtures" / "tree_big.json").read_text())
    lab.save(big, p)
    errors, done = [], threading.Event()

    def writer():
        for i in range(200):
            big["nodes"][0]["fitness"] = i
            lab.save(big, p)
        done.set()

    th = threading.Thread(target=writer)
    th.start()
    reads = 0
    while not done.is_set():
        try:
            with open(p) as f:
                json.load(f)
            reads += 1
        except json.JSONDecodeError as e:
            errors.append(e)
    th.join()
    assert not errors and reads > 0


def test_stop_file(tree_path):
    open("STOP", "w").close()
    fake, papers = FakeFable([prop()]), []
    run(fake, tree_path, 5, paper=lambda t, tree_path=None: papers.append(t))
    assert fake.users == [] and len(papers) == 1
    assert len(lab.load(tree_path)["nodes"]) == 3


def test_extract_json_robust():
    d = {"parent_id": "n1", "rules_to_test": ["B3/S23"]}
    assert lab.extract_json("Sure! Here it is:\n" + json.dumps(d) + "\nHope that helps.") == d
    assert lab.extract_json("```json\n" + json.dumps(d) + "\n```") == d
    assert lab.extract_json("prose\n```json\n" + json.dumps(d) + "\n```\nmore prose") == d
    assert lab.extract_json("no json here") is None


def test_ask_fable_garbage_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class Msg:
        content = [type("T", (), {"text": "total garbage, no braces"})()]

    class Client:
        class messages:
            n = 0

            @classmethod
            def create(cls, **k):
                cls.n += 1
                return Msg()

    monkeypatch.setattr(lab, "get_client", lambda: Client)
    monkeypatch.setattr(lab.time, "sleep", lambda s: None)
    assert lab.ask_fable("s", "u") is None
    assert Client.messages.n == 3


def test_loop_survives_none(tree_path):
    class Seq(FakeFable):
        def __call__(self, system, user):
            self.users.append(user)
            return None if len(self.users) == 1 else prop()

    fake = Seq([])
    run(fake, tree_path, 1)
    t = lab.load(tree_path)
    assert len(t["nodes"]) == 4 and t["nodes"][3]["id"] == "n3"
    assert len(fake.users) == 2


def test_resume(tree_path):
    run(FakeFable([prop(code=fixed(3.0))]), tree_path, 1)
    t = lab.load(tree_path)
    assert t["best_node_id"] == "n3"
    run(FakeFable([prop(code=fixed(1.0))]), tree_path, 1)
    t = lab.load(tree_path)
    assert [n["id"] for n in t["nodes"]] == ["n0", "n1", "n2", "n3", "n4"]
    assert t["best_node_id"] == "n3"
