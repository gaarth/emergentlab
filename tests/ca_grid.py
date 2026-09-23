"""Print the CA grid after N steps as JSON, for the JS replay parity test.

usage: python tests/ca_grid.py RULE SEED_JSON STEPS [SIZE]
Outputs {"ref": [...], "ca": [...] | null}. "ref" is the spec implementation from
IMPLEMENTATION_MUAAZ.md section 1; "ca" is the real ca.py if it is importable.
"""
import json, sys, pathlib
import numpy as np
from scipy.ndimage import convolve

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
KERNEL = np.ones((3, 3), dtype=int); KERNEL[1, 1] = 0
HIGHLIFE_REPLICATOR_SEED = [[0, 0, 1, 1, 1], [0, 1, 0, 0, 1], [1, 0, 0, 0, 1], [1, 0, 0, 1, 0], [1, 1, 1, 0, 0]]


def parse_rule(rule):
    b, s = rule.upper().split("/")
    return {int(c) for c in b[1:]}, {int(c) for c in s[1:]}


def step(grid, birth, survive):
    n = convolve(grid, KERNEL, mode="wrap")
    return (((grid == 0) & np.isin(n, list(birth))) | ((grid == 1) & np.isin(n, list(survive)))).astype(np.uint8)


def place(seed, size):
    g = np.zeros((size, size), dtype=np.uint8); s = np.array(seed, dtype=np.uint8)
    y, x = (size - s.shape[0]) // 2, (size - s.shape[1]) // 2
    g[y:y + s.shape[0], x:x + s.shape[1]] = s
    return g


def run(mod, rule, seed, steps, size):
    b, s = mod.parse_rule(rule)
    g = mod.place(seed, size)
    for _ in range(steps):
        g = mod.step(g, b, s)
    return [int(v) for v in np.asarray(g).ravel()]


if __name__ == "__main__":
    rule, seed, steps = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3])
    size = int(sys.argv[4]) if len(sys.argv) > 4 else 64
    out = {"ref": run(sys.modules[__name__], rule, seed, steps, size), "ca": None}
    try:
        import ca
        out["ca"] = run(ca, rule, seed, steps, size)
    except ImportError:
        pass
    print(json.dumps(out))
