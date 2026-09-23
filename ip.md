# Implementation Plan: Teammate (viewer.html, CA replay, paper renderer)

Source: `docs/IMPLEMENTATION_TEAMMATE.md`. This file turns it into ordered, checkable steps and adds fixes for problems found in the reference code.

**You own:** everything that reads `tree.json`. You never write it.

```
viewer.html       # single file, D3 v7 from cdnjs, dark theme, no build step
render_paper.py   # paper.md -> paper.html with frames inlined
```

**Ship order:** tree → header numbers → node panel → replay → status and paper button → polish.
The replay is the money shot. Everything after it is optional.

---

## 0. Setup (minute 0–10, with Muaaz)

Serve from the repo root, because Chrome blocks `fetch` of `tree.json` under `file://`:

```powershell
pip install markdown
python -m http.server 8000
# open http://localhost:8000/viewer.html
```

Fields you depend on:

```
question, status, best_node_id, started_at,
nodes[].{id, parent, depth, hypothesis, rules_tested, status, best_rule,
         fitness, metrics, frames, replay, notes, error}
```

**Rule:** if any field is missing, render a dash. Never crash on a half-written node.

### To-do
- [ ] Pull the repo and confirm Muaaz's fake `tree.json` with 3 nodes is committed.
- [ ] `pip install markdown` (it is not in Muaaz's dependency list).
- [ ] Start `python -m http.server 8000` and keep it running all night.
- [ ] Extend the fake tree by hand to about 10 nodes for realistic testing: one `error`, one `running`, one `pending`, one orphan whose parent is missing, and a clear best node.

---

## 1. The tree (minute 10–30)

Build `viewer.html` from section 1 of the source doc. That code is a good base. Keep these three rules:

- **Key by id and update in place.** Never remove and redraw everything on each poll, or the tree flickers and the selection is lost.
- **Orphan-safe hierarchy.** A node whose parent is missing attaches to the invisible root.
- **Cache-bust the fetch** with `?t=Date.now()`.

### Fixes to apply to the reference code
1. **Exit selection is missing.** Add `nodes.exit().remove()` and `links.exit().remove()`. This matters if Muaaz restarts with a fresh tree.
2. **Links animate from nowhere.** New links have no starting `d`, so they flash. Set an initial `d` on enter before the transition.
3. **Status colours.** Only `done` nodes get fitness colour. Give `running` a pulsing outline and `pending` a hollow circle so the audience sees live work.
4. **Best fitness shows `-Infinity` or breaks on an empty tree.** Guard `d3.max` when `nodes` is empty.
5. **Elapsed time.** Show `1h 12m` once past 60 minutes, not `72m`.
6. **Label clutter.** Truncate labels past about 40 nodes to `id` and fitness only.

### To-do
- [ ] Create `viewer.html` with header, tree pane, and side panel layout.
- [ ] Implement `tick()` polling every 2 seconds with cache-busting and a silent catch on bad JSON.
- [ ] Implement `drawHeader()` with question, nodes, experiments, elapsed, best fitness, and status badge.
- [ ] Implement `drawTree()` with keyed enter, update, and exit for nodes and links.
- [ ] Colour done nodes grey to orange by fitness. Red dashed outline for errors. White ring on the best node.
- [ ] Apply fixes 1 to 6 above.
- [ ] **Checkpoint 19:10:** fake tree renders. Adding a node to the JSON by hand makes it animate in within 2 seconds with no flicker.

---

## 2. Node panel and CA replay (minute 30–45)

Build `showNode()` and `startReplay()` from section 2 of the source doc.

### Fixes to apply to the reference code
1. **Replay will not match the frames.** Muaaz's `ca.evaluate` runs on a 64×64 torus, but the loop writes `replay.size = 48`. On a torus the grid size changes the result once patterns reach the edge. Ask Muaaz to set `replay.size` to 64. Until then, use `replay.size` as given, and treat his PNGs as the source of truth.
2. **HTML injection.** Hypotheses, notes, and errors are model-written text inserted with `innerHTML`. A `<` in a note breaks the panel. Escape every string with a small `esc()` helper.
3. **Canvas scale.** The canvas is 48 pixels wide and scaled by CSS. Keep `image-rendering: pixelated` and set CSS width to 100% of the panel so it is big.
4. **Replay restarts every poll.** `tick()` calls `showNode()` every 2 seconds, which rebuilds the panel and resets the animation. Only re-render the panel when the selected node's data has actually changed, for example by comparing `status` and `ended_at`.
5. **Frames show white background.** Muaaz's PNGs are black cells on white, while the replay is orange on black. That is fine, but label them "t=0, 20, 40, 60" so they read as a sequence. There will be 4 frames, not 3, so use 24% width each.
6. **Growth formatting.** `(m.growth ?? 0).toFixed?.(2)` shows `0.00` when missing. Show a dash instead.

The JS engine must match `ca.py` exactly: same rule parsing, same torus wrap, same seed centering with `(size - seedSize) >> 1`.

### To-do
- [ ] Implement `esc()` and use it for all model text.
- [ ] Implement `showNode()` with status, id, parent, depth, hypothesis, notes, error, best rule, metrics, rules tested, replay canvas, and frames.
- [ ] Implement `startReplay()` with B/S parsing, toroidal stepping, centred seed, and 15 fps loop.
- [ ] Only rebuild the panel when the selected node changes.
- [ ] Ask Muaaz to set `replay.size` to 64.
- [ ] Verify the replay for rule B36/S23 with the default seed matches his PNG at t=20 and t=40.
- [ ] **Checkpoint 19:25:** click a node, replay animates at about 15 fps, frames show. Real `tree.json` works with zero code changes.

---

## 3. Paper renderer (minute 45–60)

Build `render_paper.py` from section 3 of the source doc.

### Fixes to apply to the reference code
1. **Windows encoding.** `read_text()` and `write_text()` default to cp1252 on Windows and crash on characters like `→` or `≥`. Pass `encoding="utf-8"` to both.
2. **Missing images vanish silently.** If a frame is missing, print a warning instead of returning an empty string with no trace.
3. **Node citations.** Turn `(n17)` into links to `viewer.html#n17`. In the viewer, read `location.hash` on load and select that node.
4. **Academic look.** Centre the title, style the abstract as an indented block, add figure captions from the image alt text, and use a light theme. Judges read papers on white.

### To-do
- [ ] Write `render_paper.py` with UTF-8 reads and writes.
- [ ] Inline frames as base64 so `paper.html` is self-contained.
- [ ] Support the `tables` extension for the top-5 rules table.
- [ ] Link `(nXX)` citations to the viewer, and add hash-based node selection to the viewer.
- [ ] Style the paper as an academic report.
- [ ] Write a fake `paper.md` with a table, one citation, and one image, and render it.
- [ ] Confirm the viewer shows the Read the paper button when `status` becomes `done`.

---

## 4. Polish, record, rehearse (minute 60–90)

Stop wherever time runs out, in this order:

- [ ] Auto-select the best node on first load so the replay is already playing.
- [ ] Flash a NEW highlight on nodes added since the last poll, for 3 seconds.
- [ ] Add a Show dead ends toggle that dims nodes below 20% of the best fitness.
- [ ] Enlarge the replay canvas. Move the panel left if the projector is 16:9.
- [ ] Show a WRITING PAPER badge state distinctly from RUNNING.
- [ ] Record 60 seconds: header numbers, a dead end, the best node replay, then the paper. Save it to a phone.
- [ ] Rehearse the click path twice with Muaaz.

**Do not add:** search, zoom and pan libraries, routing, frameworks, or a backend.

---

## Master to-do checklist

- [ ] Setup: repo pulled, `markdown` installed, server running, fake tree extended
- [ ] Tree renders from fake data
- [ ] Keyed updates with no flicker, exit selection added
- [ ] Header shows all four pitch numbers and status
- [ ] Node colours by status and fitness, best node ringed
- [ ] Checkpoint 19:10 passed
- [ ] Node panel with escaped text
- [ ] Replay engine matches `ca.py`
- [ ] Replay does not reset on every poll
- [ ] `replay.size` agreed with Muaaz
- [ ] Checkpoint 19:25 passed on the real tree
- [ ] `render_paper.py` working with UTF-8 and inlined frames
- [ ] Citations link back to viewer nodes
- [ ] Read the paper button appears on done
- [ ] Best node auto-selected
- [ ] NEW flash and dead-ends toggle
- [ ] Fallback video recorded
- [ ] Demo rehearsed

---

## Claude Code prompts you can paste

1. `Build viewer.html per ip.md sections 1 and 2, including all listed fixes, using the fake tree.json. Serve with python -m http.server and verify no console errors.`
2. `The D3 tree flickers on each poll. Refactor drawTree to key nodes and links by id, add exit selections, and update in place with transitions.`
3. `Write render_paper.py per ip.md section 3 with UTF-8 IO, base64 frames, and (nXX) citation links, then test it on a fake paper.md.`
