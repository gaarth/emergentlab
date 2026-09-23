"""CA substrate + self-replication fitness proxy. Single source of truth for the lab."""
import numpy as np
from scipy.ndimage import label, convolve

GRID_SIZE = 64                      # replay.size in tree.json MUST equal this
KERNEL = np.ones((3, 3), dtype=int)
KERNEL[1, 1] = 0

GLIDER = [[0, 1, 0], [0, 0, 1], [1, 1, 1]]
BLOCK = [[1, 1], [1, 1]]
# Classic HighLife (B36/S23) 12-cell diagonal replicator.
HIGHLIFE_REPLICATOR_SEED = [
    [0, 0, 1, 1, 1],
    [0, 1, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 1, 0],
    [1, 1, 1, 0, 0],
]


def parse_rule(rule: str):
    """'B36/S23' -> (birth={3,6}, survive={2,3}). Lowercase and empty halves ok."""
    b, s = rule.upper().strip().split("/")
    return {int(c) for c in b[1:] if c.isdigit()}, {int(c) for c in s[1:] if c.isdigit()}


def step(grid, birth, survive):
    n = convolve(grid.astype(np.int16), KERNEL, mode="wrap")
    born = (grid == 0) & np.isin(n, list(birth))
    keep = (grid == 1) & np.isin(n, list(survive))
    return (born | keep).astype(np.uint8)


def place(seed, size=GRID_SIZE):
    g = np.zeros((size, size), dtype=np.uint8)
    s = np.array(seed, dtype=np.uint8)
    y, x = (size - s.shape[0]) // 2, (size - s.shape[1]) // 2
    g[y:y + s.shape[0], x:x + s.shape[1]] = s
    return g


def _trim(p):
    """Strip all-zero border rows/cols so shape comparison is offset-free."""
    p = np.asarray(p, dtype=np.uint8)
    if p.sum() == 0:
        return p[:0, :0]
    ys, xs = np.where(p)
    return p[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _canon(patch):
    """Canonical key under the 8 square symmetries."""
    p = _trim(patch)
    forms = []
    for k in range(4):
        r = np.rot90(p, k)
        forms.append((r.shape, r.tobytes()))
        f = np.fliplr(r)
        forms.append((f.shape, f.tobytes()))
    return min(forms)


def count_copies(grid, seed):
    """Connected components whose trimmed shape matches the seed under symmetry."""
    target = _canon(np.array(seed, dtype=np.uint8))
    th, tw = target[0]
    lbl, n = label(grid, structure=np.ones((3, 3)))
    copies = 0
    for i in range(1, n + 1):
        ys, xs = np.where(lbl == i)
        h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
        # cheap reject: a matching component must have the seed's bbox (or its transpose)
        if (h, w) != (th, tw) and (h, w) != (tw, th):
            continue
        sub = lbl[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        patch = (sub == i).astype(np.uint8)
        if _canon(patch) == target:
            copies += 1
    return copies


def evaluate(rule, seed, steps=60, size=GRID_SIZE, snapshots=(0, 20, 40, 60)):
    birth, survive = parse_rule(rule)
    g = place(seed, size)
    alive0 = int(g.sum())
    frames, max_copies = {}, 0
    for t in range(steps + 1):
        if t in snapshots:
            frames[t] = g.copy()
        if t % 5 == 0:
            max_copies = max(max_copies, count_copies(g, seed))
        if t < steps:
            g = step(g, birth, survive)
    alive = int(g.sum())
    stable = 0 < alive < 0.30 * size * size
    copies = max(max_copies, count_copies(g, seed))
    fitness = float(copies) if stable else copies * 0.2
    return {"rule": rule, "copies": copies, "alive": alive,
            "growth": alive / max(alive0, 1), "stable": stable,
            "fitness": fitness, "frames": frames}
