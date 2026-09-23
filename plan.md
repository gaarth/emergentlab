# Plan: Autonomous Discovery Lab

Build Day, Mumbai, 23 Sep 2026 · Breakthrough track · 90 minutes · USD 200 API credits

Source of truth: `prd2.pdf` for scope, architecture, timeline, and contract. `PRD.md` supplies the long-term vision and stretch visuals only.

---

## 1. What we are building

One plain-English question goes in, for example:

> Find a Life-like CA rule (B../S..) under which a 3x3 seed self-replicates.

Claude Fable 5.1 then runs an unsupervised research loop. It proposes hypotheses, writes its own experiment code, runs thousands of cellular automaton simulations, and grows a hypothesis tree. A live viewer shows the tree growing, node details, and an animated replay of the best rule. At the end the model writes a short paper that cites its own node IDs.

**The pitch:** the breakthrough is not the rule. It is 30+ minutes of coherent, multi-branch research with no human steering, proven by a visible tree where every node cites its parent and the numbers behind it.

---

## 2. Definition of done

- [ ] `python lab.py --question '...'` runs 30 minutes unattended.
- [ ] The tree has at least 40 nodes and at least 1000 rule evaluations.
- [ ] `viewer.html` shows the live tree, clicked-node details, and an animated replay.
- [ ] `paper.html` exists, cites node IDs, and embeds at least one frame.
- [ ] A 60-second fallback screen recording is on a phone.

---

## 3. Architecture

Two processes, one file as the contract.

```
                ┌──────────────────── lab.py (Muaaz) ────────────────────┐
 question ──▶   Fable 5.1: propose ──▶ sandbox runner ──▶ summarise ──▶  tree.json ──▶ Fable 5.1: write paper.md
                hypothesis + code      subprocess, 20s     fitness,        ▲  │                      │
                     ▲                 timeout             best rule       │  │                      ▼
                     └────────── tree summary + last 5 results ────────────┘  │               paper.html
                                                                              │ poll every 2s
                ┌──────────────────── viewer.html (Teammate) ─────────────────▼──┐
                │  D3 search tree ──▶ node panel ──▶ CA replay canvas             │
                └─────────────────────────────────────────────────────────────────┘
```

- `lab.py` only ever writes (appends to) `tree.json`.
- `viewer.html` only ever reads it.
- Neither side needs the other running to make progress.

### File layout

```
build day/
├── lab.py            # agent loop, Fable calls, orchestration, paper call
├── ca.py             # CA engine, seeds, shape matching, fitness, frame export
├── sandbox.py        # runs generated experiment code in a subprocess with timeout
├── prompts.py        # system prompt, loop prompt, paper prompt
├── render_paper.py   # paper.md → paper.html with frames inlined
├── viewer.html       # single-file D3 viewer, dark theme
├── fake_tree.json    # hand-written fixture for viewer development
├── tree.json         # live output (gitignored)
├── frames/           # PNG frames per node (gitignored)
├── paper.md / paper.html
├── STOP              # create this file to trigger paper writing
└── requirements.txt  # anthropic, numpy, scipy, pillow, markdown
```

---

## 4. Data contract: `tree.json`

Agree in the first 10 minutes. Frozen after 19:00.

```json
{
  "question": "Find a Life-like CA rule (B../S..) under which a 3x3 seed self-replicates.",
  "started_at": "2026-09-23T18:50:00+05:30",
  "status": "running",
  "best_node_id": "n17",
  "nodes": [
    {
      "id": "n0", "parent": null, "depth": 0,
      "hypothesis": "Baseline: sweep classic rules (Life, HighLife, Seeds) with a glider seed.",
      "rules_tested": ["B3/S23", "B36/S23", "B2/S"],
      "status": "done",
      "started_at": "...", "ended_at": "...",
      "best_rule": "B36/S23",
      "fitness": 2.0,
      "metrics": {"copies": 2, "alive": 41, "growth": 1.3, "stable": true},
      "frames": ["frames/n0_0.png", "frames/n0_20.png", "frames/n0_40.png"],
      "replay": {"rule": "B36/S23", "seed": [[0,1,0],[0,1,1],[1,1,0]], "size": 48, "steps": 60},
      "notes": "HighLife produced a replicator-like growth; branch here.",
      "error": null
    }
  ]
}
```

| Field | Values |
|---|---|
| `status` (top) | `running`, `writing_paper`, `done` |
| `status` (node) | `pending`, `running`, `done`, `error` |
| `fitness` | copies of seed after N steps, penalised if unstable |

**Write rule:** write to `tree.tmp.json`, then atomic rename. The viewer never reads a half-written file.

---

## 5. Component specs

### 5.1 `ca.py` — simulation and fitness (Muaaz)

- `parse_rule("B36/S23")` returns birth and survive sets.
- `step(grid, rule)` uses NumPy with toroidal wrap via `np.roll` or `scipy.signal.convolve2d(mode="wrap")`.
- `run(rule, seed, size=64, steps=60)` returns the history or final grid.
- `copies(grid, seed)` labels connected components with `scipy.ndimage.label`, crops each, and matches against all 8 rotations and reflections of the seed.
- `fitness(history, seed)`:
  - `growth = alive_N / alive_0`
  - `stable = 0 < alive_N < 0.3 * size²`
  - `fitness = copies if stable else copies * 0.2`
- `save_frames(history, node_id, steps=[0, 20, 40])` writes PNGs to `frames/`.
- Target speed is under 5 ms per rule evaluation on a laptop.

### 5.2 `sandbox.py` — safe execution (Muaaz)

- Writes the model's `run(rules, ca)` function to a temp file.
- Executes it in a subprocess with a 20-second timeout.
- Returns JSON with per-rule fitness, copies, alive cells, and frame paths.
- Catches exceptions and returns the traceback so the node becomes `error` rather than crashing the loop.
- The generated code must also report the standard fitness so nodes stay comparable, even if it invents a new metric.

### 5.3 `lab.py` — the agent loop (Muaaz)

Each iteration:

1. Build context: compact tree summary (id, parent, hypothesis, best fitness) plus full results of the last 5 nodes. Never raw grids. Keep each call under about 15k tokens.
2. Call Fable 5.1 with extended thinking. It returns JSON: `parent_id`, `hypothesis`, `rules_to_test[]`, `experiment_code`.
3. Append the node as `running`.
4. Run the code in the sandbox.
5. Update the node to `done` or `error` with metrics, frames, replay, and notes.
6. Update `best_node_id`.
7. Check for a STOP file or time budget.

Loop rules:

- **Anti-stagnation:** if best fitness has not improved in 4 consecutive nodes, force the next branch from one of the top-3 frontier nodes.
- **Diversity nudge:** every 8 nodes inject "which rule family have you not tried yet?"
- **Error feedback:** a failed node's traceback goes into the next prompt.
- **Durability:** on startup, if `tree.json` exists, resume from it. Handle `KeyboardInterrupt` cleanly.
- **Retries:** exponential backoff, max 3 attempts. A second API key as fallback.

CLI:

```
python lab.py --question "..." --minutes 45 [--resume]
```

### 5.4 `prompts.py` (Muaaz)

- **System prompt:** role as an autonomous scientist, the `ca` helper API, the fitness definition, the JSON output schema, and the rule to always cite the parent node and justify from prior numbers.
- **Loop prompt:** question, tree summary, last 5 results, and any forced-branch or diversity instruction.
- **Paper prompt:** full tree plus frame paths. Required sections: Abstract, Question, Method, Search summary with a top-5 rules table, Findings, Dead ends, Limitations, Next experiments. Every number must appear in `tree.json`, with node IDs cited inline like `(n17)`.

### 5.5 `viewer.html` (Teammate)

| Element | Requirement |
|---|---|
| Tree | D3 tidy tree, root at left. Node colour from grey to orange by fitness. Error nodes red. New nodes animate in. Poll every 2 s and update in place, never redraw from scratch. |
| Header | Question, node count, experiments run, elapsed time, best fitness. These four numbers are the pitch. |
| Node panel | Hypothesis, rules tested, metrics, notes, and the three PNG frames. |
| Replay | Canvas runs `node.replay` in JS at 15 fps on a loop. Make it big. This is the money shot. |
| Status | Pulsing RUNNING badge, then WRITING PAPER, then a Read paper button linking to `paper.html`. |
| Constraints | Single HTML file, D3 from cdnjs, dark theme, works from `file://` and `python -m http.server`. |

Note: `fetch` of a local JSON file fails under `file://` in most browsers. Default to serving with `python -m http.server`. As a `file://` fallback, have `lab.py` also write `tree.js` containing `window.TREE = {...}` and load it by re-injecting a script tag.

### 5.6 `render_paper.py` (Teammate)

- Convert `paper.md` to HTML with the `markdown` library.
- Inline frames as base64 so the file is self-contained.
- Style with a serif academic look: centred title, abstract block, numbered sections, captioned figures.
- Turn `(n17)` citations into links back to `viewer.html#n17`.

---

## 6. Timeline (IST)

**Hard rule:** the real loop is running by 19:35 and is never stopped after that.

| Time | Both | Muaaz | Teammate |
|---|---|---|---|
| 18:40–18:50 | Agree schema, scaffold repo, write `fake_tree.json` | | |
| 18:50–19:05 | | `ca.py`, fitness, `sandbox.py` | `viewer.html` tree from fake data |
| 19:05–19:25 | | `lab.py` loop with Fable, prompts | Node panel and CA replay |
| 19:25–19:35 | Integrate, first live run | | |
| 19:35–19:55 | | Keep loop running, paper step | Polish, `render_paper.py` |
| 19:55–20:10 | Rehearse, record fallback video | | |

Checkpoints:

- **19:00** Schema frozen. `ca.py` finds copies for a known case.
- **19:15** One full loop iteration writes a valid node.
- **19:35** Real loop running. Viewer reads the live file.
- **19:55** Paper generated once from a snapshot. `paper.html` renders.
- **20:05** Fallback video recorded.

---

## 7. Task breakdown and to-do list

### Phase 0 — Setup (Both, 18:40–18:50)

- [ ] Create repo structure and `requirements.txt`.
- [ ] Install dependencies and confirm the Anthropic API key works with a hello call to `claude-fable-5-1`.
- [ ] Agree on the `tree.json` schema and commit it.
- [ ] Hand-write `fake_tree.json` with about 12 nodes, including one error node and a clear best node.
- [ ] Add `tree.json`, `frames/`, and `STOP` to `.gitignore`.
- [ ] Decide the demo question.

### Phase 1 — Simulation core (Muaaz, 18:50–19:05)

- [ ] Implement `parse_rule`, including rules with empty sets like `B2/S`.
- [ ] Implement toroidal `step` with NumPy.
- [ ] Implement `run` returning history.
- [ ] Implement `copies` with component labelling and 8-way symmetry matching.
- [ ] Implement `fitness` with the stability penalty.
- [ ] Implement `save_frames` to PNG, scaled up for visibility.
- [ ] Sanity test: B36/S23 with a replicator seed yields copies above 1.
- [ ] Benchmark to confirm under 5 ms per evaluation.

### Phase 2 — Sandbox (Muaaz, 18:50–19:05)

- [ ] Subprocess runner with 20-second timeout.
- [ ] Inject the `ca` module into the generated code's namespace.
- [ ] Return structured JSON results.
- [ ] Capture and return tracebacks on failure.
- [ ] Test with one good function, one that raises, and one infinite loop.

### Phase 3 — Viewer skeleton (Teammate, 18:50–19:05)

- [ ] Single HTML file, dark theme, D3 from cdnjs.
- [ ] Load `fake_tree.json` and render a tidy tree with the root at left.
- [ ] Colour nodes by fitness from grey to orange, errors red.
- [ ] Header with question, node count, experiments run, elapsed time, and best fitness.
- [ ] Two-second polling with in-place D3 enter, update, and exit.
- [ ] Animate new nodes in.

### Phase 4 — Agent loop (Muaaz, 19:05–19:25)

- [ ] Write system, loop, and paper prompts.
- [ ] Tree summary builder that stays under 15k tokens.
- [ ] Fable call with extended thinking and JSON parsing, with a repair retry on bad JSON.
- [ ] Node lifecycle from pending to running to done or error.
- [ ] Atomic writes to `tree.json`, plus `tree.js` for the `file://` fallback.
- [ ] Best-node tracking.
- [ ] Anti-stagnation rule after 4 non-improving nodes.
- [ ] Diversity nudge every 8 nodes.
- [ ] Traceback feedback into the next prompt.
- [ ] Resume from existing `tree.json`.
- [ ] Retries with backoff and a second key fallback.
- [ ] STOP file and time-budget checks.
- [ ] CLI flags for question, minutes, and resume.

### Phase 5 — Node panel and replay (Teammate, 19:05–19:25)

- [ ] Click a node to open the panel with hypothesis, rules, metrics, notes, and frames.
- [ ] JS CA engine that parses B/S rules and steps on a torus.
- [ ] Large canvas replay at 15 fps on loop, from `node.replay`.
- [ ] Auto-select the best node on load.
- [ ] Status badge with the three states and the Read paper button.

### Phase 6 — Integration (Both, 19:25–19:35)

- [ ] Point the viewer at the real `tree.json`.
- [ ] Start the real loop with the demo question and `--minutes` set to cover the demo.
- [ ] Verify nodes appear in the viewer within 2 seconds.
- [ ] Verify replay of a real node matches its PNG frames.
- [ ] **Do not stop the loop after this point.**

### Phase 7 — Paper (Muaaz and Teammate, 19:35–19:55)

- [ ] Paper call on a snapshot copy of the tree, so the live loop keeps going.
- [ ] Validate that every number in `paper.md` appears in `tree.json`, and log any that don't.
- [ ] `render_paper.py` converts to HTML with inlined frames and linked citations.
- [ ] Academic styling for the paper.
- [ ] Wire the Read paper button.

### Phase 8 — Demo prep (Both, 19:55–20:10)

- [ ] Rehearse the two-minute script twice.
- [ ] Record the 60-second fallback video and put it on a phone.
- [ ] Pre-pick a dead-end branch and the best node to click.
- [ ] Check the header numbers look impressive and correct.
- [ ] Close every unrelated tab and app.

---

## 8. Demo script (2 minutes)

| Time | On screen | Say |
|---|---|---|
| 0:00 | Viewer with 40+ nodes, RUNNING pulsing | "We gave it one sentence at 19:30. Nobody has touched it since. It has run N experiments." |
| 0:25 | Click root, then a dead-end branch | "Here it tried Seeds-type rules, saw explosions, wrote them off, and moved on. That's the coherence." |
| 0:50 | Click best node, replay plays big | "This is the rule it found. Watch the seed copy itself." |
| 1:20 | Open `paper.html` | "And it wrote this up, with its own dead ends, while we were talking." |
| 1:45 | Back to tree, a new node appears | "It's still going. The breakthrough is not the rule. It's hours of unsupervised, coherent research on a laptop." |

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Broken experiment code | Sandbox catches it, node marked `error`, traceback fed into the next prompt. Errors are visible nodes and show coherence. |
| Loop tunnels on one family | Anti-stagnation rule plus the diversity nudge every 8 nodes. |
| Nothing self-replicates | Proxy fitness rewards partial progress. The paper honestly reports closest candidates. |
| Rate limits or API errors | Backoff with max 3 retries. Node stays `pending`. Second API key. |
| Wi-Fi dies | Everything is local. Fallback video. |
| Integration fails at 19:25 | Viewer built against `fake_tree.json` from minute 10, so it demos regardless. |
| Paper invents numbers | Explicit instruction, inline node citations, and a post-hoc number check. |
| Viewer can't fetch under `file://` | Serve with `python -m http.server`, with `tree.js` as a fallback. |

---

## 10. Credit budget

| Item | Estimate |
|---|---|
| Loop call | ~12k input + ~2k output tokens |
| 60 nodes | USD 30–60 |
| Paper call | ~40k input, USD 2–5 |

Budget is not the constraint. Use extended thinking and generous `max_tokens`.

---

## 11. Stretch goals (only after the definition of done is met)

Pulled from the vision in `PRD.md`, ordered by payoff per minute:

- [ ] **Space-time replay:** render the replay as a 3D voxel stack with time as the vertical axis, using Three.js from a CDN. A replicator becomes a branching crystal.
- [ ] **Critic pass:** before a node is marked best, rerun its rule with 5 random seed placements and larger grids. Show a robustness badge.
- [ ] **Rule galaxy:** plot all 2^18 Life-like rules as a 2D point cloud and light up tested ones live.
- [ ] **Reasoning cards:** show the model's justification as an annotation floating on each tree edge.
- [ ] **Timeline scrubber:** replay the tree's growth from `started_at` to now.
- [ ] **Second family:** add Larger-than-Life rules to the `ca` helpers so the model can pivot there.
