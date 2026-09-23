"""L1: ca.py substrate."""
import time
import numpy as np
import ca


def test_parse_rule():
    assert ca.parse_rule("B36/S23") == ({3, 6}, {2, 3})
    assert ca.parse_rule("b36/s23") == ({3, 6}, {2, 3})
    assert ca.parse_rule("B3/S") == ({3}, set())


def run(rule, g, n):
    b, s = ca.parse_rule(rule)
    for _ in range(n):
        g = ca.step(g, b, s)
    return g


def test_glider_translates():
    g = ca.place(ca.GLIDER, 32)
    for n in (4, 8, 40):
        assert run("B3/S23", g, n).sum() == 5


def test_block_still_life():
    g = ca.place(ca.BLOCK, 32)
    assert np.array_equal(run("B3/S23", g, 50), g)


def test_count_copies():
    seed = np.array([[1, 1, 0], [0, 1, 1], [0, 1, 0]], dtype=np.uint8)  # R-pentomino, chiral
    g = np.zeros((64, 64), dtype=np.uint8)
    g[5:8, 5:8] = seed
    assert ca.count_copies(g, seed) == 1
    g2 = g.copy()
    g2[40:43, 40:43] = seed
    assert ca.count_copies(g2, seed) == 2
    g3 = g.copy()
    g3[40:43, 40:43] = np.fliplr(np.rot90(seed))
    assert ca.count_copies(g3, seed) == 2


def test_highlife_replicator_detected():
    r = ca.evaluate("B36/S23", ca.HIGHLIFE_REPLICATOR_SEED, steps=60)
    assert r["copies"] >= 2


def test_seeds_explosive():
    seed = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]
    r = ca.evaluate("B2/S", seed)
    assert r["stable"] is False
    # copies counts the final grid; an explosion leaves none, so compare against the transient peak
    assert r["peak_copies"] >= 1 and r["fitness"] < r["peak_copies"]


def test_evaluate_fast():
    t = time.time()
    ca.evaluate("B36/S23", ca.HIGHLIFE_REPLICATOR_SEED, steps=60, size=64)
    assert time.time() - t < 0.5
