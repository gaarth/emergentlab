// JS twin of ca.py: same rule parsing, torus wrap and seed centring (parity-tested in tests/viewer.spec.js).
export function parseRule(rule) {
  const [b, s] = String(rule).toUpperCase().split("/");
  if (s === undefined) throw new Error("bad rule " + rule);
  return [new Set([...b.slice(1)].map(Number)), new Set([...s.slice(1)].map(Number))];
}

export function placeSeed(seed, size) {
  const grid = new Uint8Array(size * size);
  const oy = Math.floor((size - seed.length) / 2), ox = Math.floor((size - (seed[0] || []).length) / 2);
  seed.forEach((row, y) => row.forEach((v, x) => { if (v) grid[(oy + y) * size + ox + x] = 1; }));
  return grid;
}

export function stepGrid(grid, birth, surv, size) {
  const next = new Uint8Array(size * size);
  for (let y = 0; y < size; y++) {
    const ym = ((y - 1 + size) % size) * size, y0 = y * size, yp = ((y + 1) % size) * size;
    for (let x = 0; x < size; x++) {
      const xm = (x - 1 + size) % size, xp = (x + 1) % size;
      const n = grid[ym + xm] + grid[ym + x] + grid[ym + xp] + grid[y0 + xm] + grid[y0 + xp] + grid[yp + xm] + grid[yp + x] + grid[yp + xp];
      next[y0 + x] = grid[y0 + x] ? (surv.has(n) ? 1 : 0) : (birth.has(n) ? 1 : 0);
    }
  }
  return next;
}
