// Playwright tests for viewer.html (phases V1, V2, V3 status flip). Run: npx playwright test
const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const small = () => JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures/tree_small.json"), "utf8"));
const big = () => JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures/tree_big.json"), "utf8"));
const LIVE = "__live/tree.json";

// Serve a mutable body at /__live/tree.json so tests can swap the "file" without touching disk.
async function live(page, initial) {
  const state = { body: typeof initial === "string" ? initial : JSON.stringify(initial), urls: [] };
  await page.route("**/__live/tree.json*", (route) => {
    state.urls.push(route.request().url());
    route.fulfill({ status: 200, contentType: "application/json", body: state.body });
  });
  state.set = (b) => { state.body = typeof b === "string" ? b : JSON.stringify(b); };
  return state;
}

function trackErrors(page) {
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
  return errors;
}

const nodeCount = (page) => page.locator("#tree .node").count();

// ---------------- V1: tree rendering ----------------

test("small tree: nodes, links, header, status badge", async ({ page }) => {
  const t = small();
  await page.goto("/viewer.html?src=fixtures/tree_small.json");
  await expect(page.locator("#tree .node")).toHaveCount(3);
  await expect(page.locator("#tree .link")).toHaveCount(2);
  await expect(page.locator("#s-nodes")).toHaveText("3");
  const exp = t.nodes.reduce((a, n) => a + n.rules_tested.length, 0);
  await expect(page.locator("#s-exp")).toHaveText(exp.toLocaleString("en-US"));
  await expect(page.locator("#s-best")).toHaveText(t.nodes.find((n) => n.id === "n1").fitness.toFixed(1));
  await expect(page.locator("#status")).toHaveText("RUNNING");
  await expect(page.locator("#status")).toHaveClass(/\brunning\b/);
});

test("error node class and best-node white stroke", async ({ page }) => {
  await page.goto("/viewer.html?src=fixtures/tree_small.json");
  await expect(page.locator('.node[data-id="n2"]')).toHaveClass(/\berror\b/);
  const stroke = await page.locator('.node[data-id="n1"] circle').evaluate((c) => getComputedStyle(c).stroke);
  expect(stroke).toBe("rgb(255, 255, 255)");
});

test("big tree: 45 nodes, orphans attach to root, no console errors, fast first paint", async ({ page }) => {
  const errors = trackErrors(page);
  const t = big();
  const ids = new Set(t.nodes.map((n) => n.id));
  const orphans = t.nodes.filter((n) => n.parent != null && !ids.has(n.parent)).length;
  expect(orphans).toBe(2);
  const t0 = Date.now();
  await page.goto("/viewer.html?src=fixtures/tree_big.json");
  await expect(page.locator("#tree .node")).toHaveCount(45);
  expect(Date.now() - t0).toBeLessThan(1500);
  await expect(page.locator('#tree .node[data-parent="root"]')).toHaveCount(1 + orphans);
  await page.waitForTimeout(2500);  // at least one more poll
  expect(errors).toEqual([]);
});

test("update in place: new node appears, existing DOM element is reused", async ({ page }) => {
  const t = small();
  const srv = await live(page, t);
  await page.goto(`/viewer.html?src=${LIVE}`);
  await expect(page.locator("#tree .node")).toHaveCount(3);
  const before = await page.$('.node[data-id="n1"]');
  const t4 = small();
  t4.nodes.push({ ...t4.nodes[0], id: "n3", parent: "n1", depth: 2, fitness: 0.5 });
  srv.set(t4);
  await page.waitForTimeout(3000);
  expect(await nodeCount(page)).toBe(4);
  expect(await before.evaluate((el) => el.isConnected && el === document.querySelector('.node[data-id="n1"]'))).toBe(true);
});

test("cache-busting: every poll URL has a different ?t=", async ({ page }) => {
  const srv = await live(page, small());
  await page.goto(`/viewer.html?src=${LIVE}`);
  await page.waitForTimeout(4500);
  expect(srv.urls.length).toBeGreaterThanOrEqual(2);
  const ts = srv.urls.map((u) => new URL(u).searchParams.get("t"));
  expect(ts.every(Boolean)).toBe(true);
  expect(new Set(ts).size).toBe(ts.length);
});

test("half-written file does not throw; previous tree stays", async ({ page }) => {
  const errors = trackErrors(page);
  const body = JSON.stringify(small());
  const srv = await live(page, body);
  await page.goto(`/viewer.html?src=${LIVE}`);
  await expect(page.locator("#tree .node")).toHaveCount(3);
  srv.set(body.slice(0, Math.floor(body.length / 2)));
  await page.waitForTimeout(3000);
  expect(await nodeCount(page)).toBe(3);
  await expect(page.locator("#s-nodes")).toHaveText("3");
  expect(errors).toEqual([]);
});

// ---------------- V2: node panel and replay ----------------

test("click n1: panel shows hypothesis, rule, copies, frames, replay canvas", async ({ page }) => {
  const n1 = small().nodes[1];
  await page.goto("/viewer.html?src=fixtures/tree_small.json");
  await page.locator('.node[data-id="n1"]').click();
  const panel = page.locator("#panel");
  await expect(panel).toContainText(n1.hypothesis);
  await expect(panel).toContainText(n1.best_rule);
  await expect(panel.locator(".metrics")).toContainText("copies" + n1.metrics.copies);
  const srcs = await panel.locator("img").evaluateAll((els) => els.map((e) => e.getAttribute("src")));
  expect(srcs).toEqual(n1.frames);
  expect(srcs.length).toBe(3);
  await expect(page.locator("canvas#replay")).toHaveCount(1);
});

test("click error node: traceback in <pre>, no replay running", async ({ page }) => {
  await page.goto("/viewer.html?src=fixtures/tree_small.json");
  await page.locator('.node[data-id="n2"]').click();
  await expect(page.locator("#panel pre")).toContainText("KeyError: 'copiez'");
  await expect(page.locator("canvas#replay")).toHaveCount(0);
  expect(await page.evaluate(() => window.__replayTimer)).toBeNull();
});

function pyGrid(rule, seed, steps) {
  return JSON.parse(execFileSync("python", [path.join(ROOT, "tests/ca_grid.py"), rule, JSON.stringify(seed), String(steps)], { encoding: "utf8" }));
}

test("replay parity with ca.py: bit-exact grids", async ({ page }) => {
  await page.goto("/viewer.html?src=fixtures/tree_small.json");
  const glider = [[0, 1, 0], [0, 0, 1], [1, 1, 1]];
  const repl = small().nodes[1].seed;
  const cases = [["B3/S23", glider, 4], ["B3/S23", glider, 8], ["B36/S23", repl, 20], ["b36/s23", repl, 60], ["B3/S", glider, 3]];
  for (const [rule, seed, steps] of cases) {
    const js = await page.evaluate(([r, s, n]) => window.stepCA(r, s, 64, n), [rule, seed, steps]);
    const py = pyGrid(rule, seed, steps);
    expect(js, `${rule} t=${steps} vs reference`).toEqual(py.ref);
    if (py.ca) expect(js, `${rule} t=${steps} vs ca.py`).toEqual(py.ca);
    if (steps === 4 || steps === 8) expect(js.reduce((a, b) => a + b, 0)).toBe(5);  // glider keeps 5 cells
  }
});

test("replay runs at >= 12 fps", async ({ page }) => {
  await page.goto("/viewer.html?src=fixtures/tree_small.json");
  await expect(page.locator("canvas#replay")).toHaveCount(1);
  const f0 = await page.evaluate(() => window.__frames);
  await page.waitForTimeout(2000);
  const f1 = await page.evaluate(() => window.__frames);
  expect(f1 - f0).toBeGreaterThanOrEqual(24);
});

test("selection survives a poll", async ({ page }) => {
  await page.goto("/viewer.html?src=fixtures/tree_small.json");
  await page.locator('.node[data-id="n0"]').click();   // n0, not the auto-selected best, so a reset would show
  await page.waitForTimeout(3000);
  await expect(page.locator("#panel")).toContainText(small().nodes[0].hypothesis);
  await page.locator('.node[data-id="n1"]').click();
  await page.waitForTimeout(3000);
  await expect(page.locator("#panel")).toContainText(small().nodes[1].hypothesis);
});

test("replay survives a poll; panel rebuilds exactly once on change", async ({ page }) => {
  const t = small();
  const srv = await live(page, t);
  await page.goto(`/viewer.html?src=${LIVE}`);
  await page.locator('.node[data-id="n1"]').click();
  await expect(page.locator("canvas#replay")).toHaveCount(1);
  const timer = await page.evaluate(() => window.__replayTimer);
  const canvas = await page.$("canvas#replay");
  const builds = await page.evaluate(() => window.__panelBuilds);
  await page.waitForTimeout(5000);
  expect(await page.evaluate(() => window.__replayTimer)).toBe(timer);
  expect(await canvas.evaluate((c) => c === document.querySelector("canvas#replay"))).toBe(true);
  expect(await page.evaluate(() => window.__panelBuilds)).toBe(builds);
  t.nodes[1].fitness = 2.5;
  srv.set(t);
  await page.waitForTimeout(5000);
  expect(await page.evaluate(() => window.__panelBuilds)).toBe(builds + 1);
  await expect(page.locator("#panel .metrics")).toContainText("fitness2.5");
});

test("model text is escaped (no XSS, layout intact)", async ({ page }) => {
  const evil = `<img src=x onerror=window.__pwned=1> & "quotes"`;
  const t = small();
  Object.assign(t.nodes[1], { hypothesis: evil, notes: evil, best_rule: "B36/S23" });
  t.nodes[2].error = evil;
  t.question = evil;
  await live(page, t);
  await page.goto(`/viewer.html?src=${LIVE}`);
  await page.locator('.node[data-id="n1"]').click();
  await expect(page.locator("#panel h3")).toHaveText(evil);
  await page.locator('.node[data-id="n2"]').click();
  await expect(page.locator("#panel pre")).toHaveText(evil);
  await expect(page.locator("#question")).toHaveText(evil);
  await expect(page.locator("#panel .metrics")).toHaveCount(1);
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => window.__pwned)).toBeUndefined();
});

test("stale nodes are removed when the tree shrinks", async ({ page }) => {
  const srv = await live(page, big());
  await page.goto(`/viewer.html?src=${LIVE}`);
  await expect(page.locator("#tree .node")).toHaveCount(45);
  srv.set(small());
  await page.waitForTimeout(3000);
  expect(await nodeCount(page)).toBe(3);
  await expect(page.locator("#tree .link")).toHaveCount(2);
});

test("best node auto-selected on first load with replay running", async ({ page }) => {
  await page.goto("/viewer.html?src=fixtures/tree_big.json");
  const b = big(), best = b.nodes.find((n) => n.id === b.best_node_id);
  await expect(page.locator("#panel")).toContainText(best.hypothesis);
  await expect(page.locator("#panel")).toContainText(best.id);
  await expect(page.locator("canvas#replay")).toHaveCount(1);
  expect(await page.evaluate(() => window.__replayTimer)).not.toBeNull();
});

test("hash selects a node on load (#n0)", async ({ page }) => {
  await page.goto("/viewer.html?src=fixtures/tree_small.json#n0");
  await expect(page.locator("#panel")).toContainText(small().nodes[0].hypothesis);
});

// ---------------- V3: status flip ----------------

test("status done shows a Read the paper button that opens paper.html", async ({ page, context }) => {
  const t = small();
  t.status = "writing_paper";
  const srv = await live(page, t);
  await context.route("**/paper.html", (r) => r.fulfill({ status: 200, contentType: "text/html", body: "<h1>paper</h1>" }));
  await page.goto(`/viewer.html?src=${LIVE}`);
  await expect(page.locator("#status")).toHaveText("WRITING PAPER");
  await expect(page.locator("#paper-btn")).toHaveCount(0);
  t.status = "done";
  srv.set(t);
  await expect(page.locator("#paper-btn")).toBeVisible({ timeout: 4000 });
  await expect(page.locator("#paper-btn")).toHaveAttribute("href", "paper.html");
  const [popup] = await Promise.all([context.waitForEvent("page"), page.locator("#paper-btn").click()]);
  await popup.waitForLoadState();
  expect(popup.url()).toMatch(/paper\.html$/);
  await expect(popup.locator("h1")).toHaveText("paper");
});
