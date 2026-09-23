// Smoke test against the real tree.json (whatever is in the repo root right now). Used by demo_check.py.
const { test, expect } = require("@playwright/test");

test("live tree.json renders with no errors", async ({ page, request }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
  const t = await (await request.get("/tree.json?t=" + Date.now())).json();
  await page.goto("/viewer.html");
  await expect(page.locator("#tree .node").first()).toBeVisible({ timeout: 5000 });
  const shown = +(await page.locator("#s-nodes").textContent());
  expect(shown).toBeGreaterThanOrEqual(t.nodes.length);         // the loop may have appended since
  expect(await page.locator("#tree .node").count()).toBe(shown);
  if (t.best_node_id) {
    await expect(page.locator("#panel")).toContainText(t.best_node_id);
    const best = t.nodes.find((n) => n.id === t.best_node_id);
    if (best && best.replay) expect(await page.evaluate(() => window.__replayTimer)).not.toBeNull();
  }
  await page.waitForTimeout(2500);
  expect(errors).toEqual([]);
});
