# IMPLEMENTATION — Teammate (viewer.html, CA replay, paper renderer)

You own everything that **reads** `tree.json`. You never write it. Muaaz's loop can be late or broken and you still ship, because you build against the fake `tree.json` he commits at minute 10.

Files you own:

```
viewer.html       # single file, D3 from cdnjs, dark theme, no build step
render_paper.py   # paper.md -> paper.html with frames inlined
```

Serve everything with `python -m http.server 8000` from the repo root (fetching tree.json from `file://` is blocked in Chrome). Open `http://localhost:8000/viewer.html`.

Ship order: **tree → header numbers → node panel → replay → status/paper button → polish**. The replay is the demo money shot; everything after it is optional.

---

## 0. Minute 0–10: schema (with Muaaz)

Read `tree.json` schema in the PRD section 6. The fields you depend on:

`question, status, best_node_id, started_at, nodes[].{id, parent, depth, hypothesis, rules_tested, status, best_rule, fitness, metrics, frames, replay, notes, error}`

If any field is missing in a node, render a dash. Never crash on a half-written node.

---

## 1. Minute 10–30: the tree

Ask Claude Code for the skeleton, then fix by hand. The essentials:

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>Autonomous Discovery Lab</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
  :root{--bg:#121212;--panel:#1c1c1e;--fg:#e8e8e8;--muted:#8a8a8a;--acc:#e8724a;}
  body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 -apple-system,Inter,sans-serif;display:grid;grid-template-rows:auto 1fr;height:100vh}
  header{display:flex;gap:28px;align-items:baseline;padding:12px 18px;border-bottom:1px solid #2a2a2a}
  header .q{flex:1;color:var(--muted)} .stat b{font-size:22px;color:var(--acc);display:block}
  main{display:grid;grid-template-columns:1fr 420px;min-height:0}
  #tree{overflow:auto} aside{background:var(--panel);padding:14px;overflow:auto;border-left:1px solid #2a2a2a}
  .badge{padding:2px 8px;border-radius:10px;font-size:11px;background:#333} .badge.running{background:var(--acc);animation:pulse 1.2s infinite}
  @keyframes pulse{50%{opacity:.4}}
  canvas{width:100%;image-rendering:pixelated;background:#000;border-radius:6px}
  .node circle{stroke:#000;stroke-width:1.2} .node text{fill:var(--fg);font-size:10px} .link{fill:none;stroke:#444}
  .error circle{stroke:#d33;stroke-dasharray:2 2}
</style></head>
<body>
<header>
  <div class="q" id="question">…</div>
  <div class="stat">nodes<b id="s-nodes">0</b></div>
  <div class="stat">experiments<b id="s-exp">0</b></div>
  <div class="stat">elapsed<b id="s-time">0m</b></div>
  <div class="stat">best fitness<b id="s-best">0</b></div>
  <span class="badge" id="status">…</span>
</header>
<main>
  <div id="tree"><svg></svg></div>
  <aside id="panel">Click a node.</aside>
</main>
<script>
const svg = d3.select("#tree svg"), g = svg.append("g").attr("transform","translate(40,20)");
const color = d3.scaleSequential(d3.interpolateOranges).domain([0, 4]);
let selected = null, tree = null;

async function tick(){
  try { tree = await (await fetch("tree.json?t=" + Date.now())).json(); } catch(e){ return; }
  drawHeader(tree); drawTree(tree);
  if (selected) showNode(tree.nodes.find(n => n.id === selected));
}
setInterval(tick, 2000); tick();

function drawHeader(t){
  document.getElementById("question").textContent = t.question || "";
  document.getElementById("s-nodes").textContent = t.nodes.length;
  document.getElementById("s-exp").textContent = t.nodes.reduce((a,n)=>a+(n.rules_tested||[]).length,0).toLocaleString();
  document.getElementById("s-time").textContent = Math.round((Date.now()-new Date(t.started_at))/60000)+"m";
  document.getElementById("s-best").textContent = d3.max(t.nodes, n=>n.fitness||0)?.toFixed(1) ?? "0";
  const st = document.getElementById("status"); st.textContent = (t.status||"").replace("_"," ").toUpperCase();
  st.className = "badge " + (t.status==="running"?"running":"");
  if (t.status==="done" && !document.getElementById("paper-btn")) {
    const a = document.createElement("a"); a.id="paper-btn"; a.href="paper.html"; a.target="_blank"; a.textContent="Read the paper →";
    a.style.cssText="margin-left:12px;color:var(--acc);font-weight:600"; st.after(a);
  }
}

function drawTree(t){
  const byId = new Map(t.nodes.map(n=>[n.id,n]));
  // orphan-safe: a node whose parent isn't in the tree yet becomes a root child
  const data = {id:"root", children:[]}, map = new Map([["root",data]]);
  t.nodes.forEach(n => map.set(n.id, {id:n.id, node:n, children:[]}));
  t.nodes.forEach(n => (map.get(n.parent) || data).children.push(map.get(n.id)));
  const root = d3.hierarchy(data);
  const h = Math.max(400, t.nodes.length * 22), w = Math.max(900, root.height * 220);
  svg.attr("width", w + 200).attr("height", h + 40);
  d3.tree().size([h, w])(root);
  const links = g.selectAll(".link").data(root.links().filter(l=>l.source.data.id!=="root"), d=>d.target.data.id);
  links.enter().append("path").attr("class","link").merge(links)
       .transition().duration(400).attr("d", d3.linkHorizontal().x(d=>d.y).y(d=>d.x));
  const nodes = g.selectAll(".node").data(root.descendants().filter(d=>d.data.id!=="root"), d=>d.data.id);
  const enter = nodes.enter().append("g").attr("class","node").attr("transform", d=>`translate(${d.y},${d.x})`)
      .style("cursor","pointer").on("click", (e,d)=>{selected=d.data.id; showNode(d.data.node);});
  enter.append("circle").attr("r", 0).transition().duration(500).attr("r", 7);
  enter.append("text").attr("dx", 11).attr("dy", 4);
  const all = enter.merge(nodes);
  all.transition().duration(400).attr("transform", d=>`translate(${d.y},${d.x})`);
  all.classed("error", d=>d.data.node.status==="error")
     .select("circle").attr("fill", d=>d.data.node.status==="done" ? color(d.data.node.fitness||0) : "#555")
     .attr("stroke", d=>d.data.id===t.best_node_id ? "#fff" : "#000").attr("stroke-width", d=>d.data.id===t.best_node_id?2.5:1.2);
  all.select("text").text(d=>`${d.data.id} ${d.data.node.best_rule||""} ${d.data.node.fitness?d.data.node.fitness.toFixed(1):""}`);
}
</script>
</body></html>
```

Rules that make this not fall over on stage:

- **Key by id, update in place.** Never `selectAll().remove()` on every poll; the tree will flicker and the selection will be lost.
- **Orphan-safe hierarchy.** A node can be written before its parent finishes; attach to root if the parent is missing.
- **Cache-bust the fetch** (`?t=`) or Chrome will serve you the same file forever.

**Checkpoint (19:10):** fake tree renders, adding a 4th node to the fake JSON by hand makes it animate in within 2 s.

---

## 2. Minute 30–45: node panel + CA replay

```js
function showNode(n){
  if (!n) return;
  const m = n.metrics||{};
  document.getElementById("panel").innerHTML = `
    <div><span class="badge ${n.status}">${n.status}</span> <b>${n.id}</b> ← ${n.parent||"root"} · depth ${n.depth}</div>
    <h3 style="margin:10px 0 4px">${n.hypothesis||""}</h3>
    <div style="color:var(--muted)">${n.notes||""}</div>
    ${n.error?`<pre style="color:#f66;white-space:pre-wrap">${n.error}</pre>`:""}
    <div style="margin:10px 0"><b>Best rule:</b> ${n.best_rule||"—"} &nbsp; <b>fitness</b> ${n.fitness??"—"}
      &nbsp; copies ${m.copies??"—"} · alive ${m.alive??"—"} · growth ${(m.growth??0).toFixed?.(2)??"—"} · ${m.stable?"stable":"unstable"}</div>
    <div style="color:var(--muted);font-size:12px">tested: ${(n.rules_tested||[]).join(", ")}</div>
    <canvas id="replay" width="48" height="48" style="margin-top:12px"></canvas>
    <div style="display:flex;gap:6px;margin-top:8px">${(n.frames||[]).map(f=>`<img src="${f}" style="width:30%;image-rendering:pixelated;border-radius:4px">`).join("")}</div>`;
  if (n.replay) startReplay(n.replay);
}

let replayTimer = null;
function startReplay({rule, seed, size=48, steps=60}){
  clearInterval(replayTimer);
  const [b, s] = rule.toUpperCase().split("/"); const birth = new Set([...b.slice(1)].map(Number)), surv = new Set([...s.slice(1)].map(Number));
  let grid = new Uint8Array(size*size);
  const oy = (size - seed.length) >> 1, ox = (size - seed[0].length) >> 1;
  seed.forEach((row,y)=>row.forEach((v,x)=>{ if(v) grid[(oy+y)*size+ox+x]=1; }));
  const start = grid.slice(); let t = 0;
  const cv = document.getElementById("replay"), ctx = cv.getContext("2d"), img = ctx.createImageData(size,size);
  function step(){
    const next = new Uint8Array(size*size);
    for (let y=0;y<size;y++) for (let x=0;x<size;x++){
      let n=0;
      for (let dy=-1;dy<=1;dy++) for (let dx=-1;dx<=1;dx++){ if(dy||dx) n += grid[((y+dy+size)%size)*size + (x+dx+size)%size]; }
      const i=y*size+x; next[i] = grid[i] ? (surv.has(n)?1:0) : (birth.has(n)?1:0);
    }
    grid = next;
  }
  function draw(){
    for (let i=0;i<size*size;i++){ const v=grid[i]?232:0; img.data[i*4]=v; img.data[i*4+1]=grid[i]?114:0; img.data[i*4+2]=grid[i]?74:0; img.data[i*4+3]=255; }
    ctx.putImageData(img,0,0);
  }
  draw();
  replayTimer = setInterval(()=>{ step(); draw(); if(++t>=steps){ grid=start.slice(); t=0; } }, 66);
}
```

This is the JS twin of Muaaz's `ca.py`. **Same rule parsing, same torus wrap, same seed centering.** If your replay disagrees with his PNG frames, one of you has an off-by-one in the seed offset; fix yours, his frames are the source of truth.

**Checkpoint (19:25):** click a node, replay animates at ~15 fps, frames show. Pull Muaaz's real `tree.json`; it must work with zero code changes.

---

## 3. Minute 45–60: `render_paper.py`

Muaaz's loop calls this at the end. Keep it dumb.

```python
# render_paper.py
import markdown, base64, re, pathlib
md = pathlib.Path("paper.md").read_text()
def inline(m):
    p = pathlib.Path(m.group(1))
    if not p.exists(): return ""
    return f'<img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}" style="width:180px;image-rendering:pixelated;margin:4px">'
html = markdown.markdown(md, extensions=["tables"])
html = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', inline, html)
page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Lab report</title>
<style>body{{max-width:820px;margin:40px auto;padding:0 20px;font:16px/1.6 Georgia,serif;background:#121212;color:#e8e8e8}}
h1,h2{{color:#e8724a}} table{{border-collapse:collapse}} td,th{{border:1px solid #444;padding:6px 10px}} code{{background:#222;padding:1px 4px}}</style>
</head><body>{html}<hr><p style="color:#888">Written autonomously by Claude Fable 5.1 from tree.json · Claude Community Mumbai Build Day</p></body></html>"""
pathlib.Path("paper.html").write_text(page)
print("paper.html written")
```

Test it now with a fake `paper.md` containing a table and one `![](frames/n0_20.png)`.

---

## 4. Minute 60–90: polish, record, rehearse

Priority order, stop wherever time runs out:

1. Auto-select the best node the first time the page loads (`selected = tree.best_node_id`) so the replay is already playing when the judges look.
2. "NEW" flash on nodes added since the last poll (add a class for 3 s).
3. A "Show dead ends" toggle that dims nodes whose fitness < 20% of best. Nice for the "coherence" talking point.
4. Make the replay canvas bigger (CSS width 100% of the panel) and put the panel on the left for the demo if the projector is 16:9.
5. Record 60 s: header numbers → click dead end → click best node → paper. Save to phone.

Do **not** add: search, zoom/pan libraries, routing, frameworks, a backend. Every one of those has cost a team a demo.

---

## Claude Code prompts you can paste

1. `Build viewer.html per IMPLEMENTATION_TEAMMATE.md section 1 and 2, using the fake tree.json in this repo. Serve with python -m http.server and verify no console errors.`
2. `The D3 tree flickers on each poll. Refactor drawTree to key nodes/links by id and update in place with transitions.`
3. `Write render_paper.py per section 3 and test it on a fake paper.md with a table and one image.`
