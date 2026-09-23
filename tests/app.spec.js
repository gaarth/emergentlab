// Playwright tests for the React/R3F app (app/), served as a production build by server.py at /app/dist/.
// Run: npm run build (in app/) then npx playwright test.  ?nofx&nointro keeps headless rendering deterministic.
const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const APP = "/app/dist/index.html?nofx&nointro";
const small = () => JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures/tree_small.json"), "utf8"));
const big = () => JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures/tree_big.json"), "utf8"));

// Serve a mutable tree at /tree.json so tests never touch the real file.
async function serveTree(page, initial) {
  const state = { body: JSON.stringify(initial), set(t) { state.body = typeof t === "string" ? t : JSON.stringify(t); } };
  await page.route("**/tree.json*", (r) => r.fulfill({ status: 200, contentType: "application/json", body: state.body }));
  return state;
}
function trackErrors(page) {
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|WebGL|GL Driver/.test(m.text())) errors.push(m.text()); });
  return errors;
}

test("small tree: header numbers, chat messages, status, best node auto-selected with replay", async ({ page }) => {
  const errors = trackErrors(page);
  const t = small();
  await serveTree(page, t);
  await page.goto(APP);
  await expect(page.locator(".stat b").nth(0)).toHaveText("3");
  await expect(page.locator(".stat b").nth(1)).toHaveText(String(t.nodes.reduce((a, n) => a + n.rules_tested.length, 0)));
  await expect(page.locator(".stat b").nth(3)).toHaveText("2.0");
  await expect(page.locator(".status")).toHaveText("running");
  await expect(page.locator(".msg")).toHaveCount(2 + t.nodes.length);        // question + intro + one per node
  await expect(page.locator(".panel")).toContainText("n1");                   // best node auto-selected
  await expect(page.locator(".panel canvas")).toHaveCount(1);
  await expect(page.locator(".panel")).toContainText(t.nodes[1].hypothesis);
  await page.waitForTimeout(2500);
  expect(errors).toEqual([]);
});

test("clicking a chat message selects that node; error node shows traceback and no replay", async ({ page }) => {
  await serveTree(page, small());
  await page.goto(APP);
  await page.locator(".msg.clickable").filter({ hasText: "n2 failed" }).click();
  await expect(page.locator(".panel pre")).toContainText("KeyError: 'copiez'");
  await expect(page.locator(".panel canvas")).toHaveCount(0);
  await page.locator(".msg.clickable").filter({ hasText: /^n0 · / }).click();
  await expect(page.locator(".panel")).toContainText(small().nodes[0].hypothesis);
});

test("big tree renders 45 nodes in 3D with labels and no errors", async ({ page }) => {
  const errors = trackErrors(page);
  await serveTree(page, big());
  await page.goto(APP);
  await expect(page.locator(".stat b").nth(0)).toHaveText("45");
  await expect(page.locator(".label.best")).toHaveCount(1);
  await expect(page.locator(".label.best")).toContainText(big().best_node_id);
  await page.waitForTimeout(2000);
  expect(errors).toEqual([]);
});

test("live update: new node appears in chat and header within a poll; selection survives", async ({ page }) => {
  const t = small();
  const srv = await serveTree(page, t);
  await page.goto(APP);
  await page.locator(".msg.clickable").filter({ hasText: /^n0 · / }).click();
  t.nodes.push({ ...t.nodes[0], id: "n3", parent: "n1", depth: 2, hypothesis: "Fresh node from the loop" });
  srv.set(t);
  await expect(page.locator(".stat b").nth(0)).toHaveText("4", { timeout: 4000 });
  await expect(page.locator(".msg").filter({ hasText: "Fresh node" })).toHaveCount(1);
  await expect(page.locator(".panel")).toContainText(t.nodes[0].hypothesis);   // still n0
});

test("half-written tree.json keeps the previous tree", async ({ page }) => {
  const errors = trackErrors(page);
  const body = JSON.stringify(small());
  const srv = await serveTree(page, small());
  await page.goto(APP);
  await expect(page.locator(".stat b").nth(0)).toHaveText("3");
  srv.set(body.slice(0, body.length >> 1));
  await page.waitForTimeout(3000);
  await expect(page.locator(".stat b").nth(0)).toHaveText("3");
  expect(errors).toEqual([]);
});

test("model text is rendered as text, never HTML", async ({ page }) => {
  const evil = `<img src=x onerror=window.__pwned=1> & "quotes"`;
  const t = small();
  Object.assign(t.nodes[1], { hypothesis: evil, notes: evil }); t.nodes[2].error = evil; t.question = evil;
  await serveTree(page, t);
  await page.goto(APP);
  await expect(page.locator(".panel h3")).toHaveText(evil);
  await expect(page.locator(".msg.user .bubble")).toHaveText(evil);
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => window.__pwned)).toBeUndefined();
});

test("status done shows the paper link in header and chat", async ({ page }) => {
  const t = small(); t.status = "done";
  await serveTree(page, t);
  await page.goto(APP);
  await expect(page.locator("header .paper")).toHaveAttribute("href", "/paper.html");
  await expect(page.locator(".msg .sub.link")).toHaveAttribute("href", "/paper.html");
  await expect(page.locator(".status")).toHaveText("done");
});

test("replay parity with ca.py: bit-exact grids", async ({ page }) => {
  await serveTree(page, small());
  await page.goto(APP);
  const glider = [[0, 1, 0], [0, 0, 1], [1, 1, 1]], repl = small().nodes[1].seed;
  for (const [rule, seed, steps] of [["B3/S23", glider, 4], ["B3/S23", glider, 8], ["B36/S23", repl, 20], ["b36/s23", repl, 60], ["B3/S", glider, 3]]) {
    const js = await page.evaluate(([r, s, n]) => window.stepCA(r, s, 64, n), [rule, seed, steps]);
    const py = JSON.parse(execFileSync("python", [path.join(ROOT, "tests/ca_grid.py"), rule, JSON.stringify(seed), String(steps)], { encoding: "utf8" }));
    expect(js, `${rule} t=${steps} vs reference`).toEqual(py.ref);
    if (py.ca) expect(js, `${rule} t=${steps} vs ca.py`).toEqual(py.ca);
  }
});

test("live tree.json (whatever is in the repo) renders without errors", async ({ page, request }) => {
  const errors = trackErrors(page);
  const r = await request.get("/tree.json");
  test.skip(!r.ok(), "no tree.json yet");
  const t = await r.json();
  await page.goto(APP);
  await expect(page.locator(".stat b").nth(0)).not.toHaveText("0");
  expect(+(await page.locator(".stat b").nth(0).textContent())).toBeGreaterThanOrEqual(t.nodes.length);
  await page.waitForTimeout(2500);
  expect(errors).toEqual([]);
});
