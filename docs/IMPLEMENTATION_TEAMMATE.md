# IMPLEMENTATION — Teammate (3D UI, CA replay, paper renderer)

You own everything that **reads** `tree.json`. You never write it (the one exception: `server.py` *launches* the writer).

```
app/                 # React 18 + Vite 5 + React Three Fiber 8 + drei + @react-three/postprocessing + Theatre.js 0.7
  src/App.jsx        #   layout, selection state, polling, start/stop calls
  src/Scene.jsx      #   3D hypothesis tree, camera rig, Theatre.js intro sheet
  src/Chat.jsx       #   chat window: question in, one message per experiment out
  src/NodePanel.jsx  #   node details + CA replay canvas + frame PNGs
  src/ca.js          #   JS twin of ca.py (rule parsing, torus step, seed centring)
  src/useTree.js     #   2 s poller with cache-busting; header stats
  src/theatre-state.json  # Theatre.js project state: intro keyframes for "Tree" (scale/rotation) and "Key" light
server.py            # static files + POST /api/start (spawns lab.py or mock_lab.py) + POST /api/stop (touches STOP)
render_paper.py      # paper.md -> paper.html with frames inlined
mock_lab.py          # fake lab for developing/demoing without the API
```

The old single-file `viewer.html` was replaced by this app on 23 Sep 2026 (user request). There is no HTML UI any more.

## Run

```bash
python server.py            # :8000 — tree.json, frames/, paper.html, /api/*, and the built app at /app/dist/
cd app && npm run dev       # :5173 — hot reload, proxies /tree.json,/frames,/api,/paper.html to :8000
cd app && npm run build     # production build -> app/dist (what tests and demo_check use)
```

`.env` (git-ignored) holds `ANTHROPIC_API_KEY` and `ANTHROPIC_WORKSPACE_ID`; `server.py` and `lab.py` both read it.

## UI spec

**Look.** Dark, Apple-style: frosted-glass panels (`backdrop-filter: blur(22px)`), SF/Inter system font, one accent
(`#ff7a3d`), 999px pills, soft drop-in animations, ACES tone mapping, bloom + vignette, star field, fog.

**Header (top centre pill).** Brand, the four pitch numbers — nodes, experiments, elapsed, best fitness — status
pill (RUNNING pulses orange, WRITING PAPER pulses yellow, DONE green) and a "Read the paper →" link when done.

**Chat (left).** The chat is a *projection of tree.json*, not a separate log: the question as the user bubble, an intro
line, then one lab bubble per node in tree order — running nodes show "…", errors show the last traceback line, done
nodes show `rules → best rule · fitness · copies`, the best node has an orange border. `writing_paper` / `done`
append a paper message with the link. Clicking a bubble selects that node in 3D. The composer takes the research
question (Enter sends, Shift+Enter newline), a "mock lab (no API)" toggle, and Run / "Stop & write paper".

**3D tree (centre).** Radial layout: depth → ring radius (3.2 units per level), d3 tidy order → angle, gentle vertical
wave. Nodes are spheres: colour grey→orange by fitness (done), dim red (error), amber pulsing (running); size grows
with fitness; the best node is largest with a pulsing glow and an orange ring; the selected node gets a white ring.
Links are quadratic Bézier curves; the selected node's links highlight. Labels (`.label`) appear for best, selected
and hovered nodes. New nodes scale in from 0; everything moves with `maath/easing.damp3` (no snapping).
Orphans and parent cycles attach to the invisible root. Positions are recomputed per poll and eased, so the tree
re-flows smoothly as it grows.

**Camera.** Slow auto-orbit around the whole tree (radius follows tree depth). Selecting a node eases the camera to
9 units from it. Dragging (OrbitControls, damped) pauses the rig for 8 s.

**Theatre.js.** `getProject("Discovery Lab", {state})` → sheet `Intro`. `<SheetProvider>` wraps the scene;
`<e.group theatreKey="Tree">` and `<e.pointLight theatreKey="Key"/"Fill">` are editable. The 3 s intro sequence
(tree scale 0.001→1, rotation −2.4→0, key light 0→35) plays when a tree first loads and after every Run. Studio is
initialised only in dev (`Alt+\` shows it); a 4 s fallback forces the sequence to its end so the tree can never stay hidden.

**Node panel (right).** Status pill, id ← parent · depth, hypothesis, notes, traceback (`<pre>`), six metric tiles
(best rule, fitness, copies, alive, growth, stable), rules tested, the replay canvas (`replay.rule/seed/size/steps`,
15 fps, holds the last frame, loops) and the frame PNGs with `t=` captions. The panel only re-renders when the node's
JSON changes, so the replay does not restart on every poll.

**Robustness.** Half-written `tree.json` → keep the previous tree. 404 → idle state. Missing fields → "—". All model
text is rendered as React text (never `dangerouslySetInnerHTML`). No external assets at runtime (no CDN, no HDR
environment) so Wi-Fi loss cannot blank the scene. URL flags: `?nofx` (no post-processing), `?nointro`.

**Replay parity.** `window.stepCA(rule, seed, size, steps)` is exposed; `tests/app.spec.js` compares it bit-exactly
with `tests/ca_grid.py` (spec CA) and with the real `ca.py`.

## Tests

```bash
python -m pytest -q                         # contract, render_paper, mock_lab (+ Muaaz's ca/sandbox/loop/paper)
cd app && npm run build && cd .. && npx playwright test    # 9 UI tests against the production build
python demo_check.py                        # phase D readiness + the four pitch numbers
```

## Paper renderer

`render_paper.py [in.md] [out.html]` (defaults `paper.md`/`paper.html`): Markdown → HTML with `tables`, frames
inlined as base64, `(n17)` citations linked to the app (`/app/dist/index.html#n17`), UTF-8 safe on Windows consoles,
light academic theme.
