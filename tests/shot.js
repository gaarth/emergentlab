// Dev helper: node tests/shot.js [url] [out.png] — screenshot + console/page errors for the React app.
const { chromium } = require("playwright");
(async () => {
  const url = process.argv[2] || "http://localhost:5173/", out = process.argv[3] || "shot.png";
  const b = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"] });
  const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
  const errs = [];
  p.on("pageerror", (e) => errs.push("PAGEERROR " + e.message));
  p.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errs.push(m.type() + ": " + m.text().slice(0, 300)); });
  await p.goto(url, { waitUntil: "networkidle" });
  await p.waitForTimeout(4500);
  await p.screenshot({ path: out });
  console.log("canvas:", await p.locator("canvas").count(), "labels:", await p.locator(".label").count(), "msgs:", await p.locator(".msg").count());
  console.log(errs.length ? errs.join("\n") : "no console errors");
  await b.close();
})();
