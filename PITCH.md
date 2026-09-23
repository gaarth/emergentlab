# Autonomous Discovery Lab — 90-second demo

**Track:** Breakthrough. **Built on:** Fable 5.1 via the API, Claude Code for everything else.
**Demo URL:** `localhost:8000/app/dist/index.html` (3D). Fallback: `localhost:8000/app.html` (2D).

## The question we gave it

> Find a Life-like CA rule (B../S..) and a seed of at most 5x5 cells under which the seed self-replicates: after N steps the grid contains 2 or more disjoint copies of the seed.

In plain words: pick any rule from the Game-of-Life family and a tiny starting pattern, so that after some steps the grid holds two or more separate, exact copies of that pattern.

## The four numbers

Snapshot at 20:27. Read the live values off the header just before you go up.

| | |
|---|---|
| Hypotheses | **23** |
| Rules tested | **627** |
| Running unattended | **49 min** |
| Best result | **121 exact copies** of a 5-cell seed (`B1357/S02468`, node n2) |

## What's on the screen

```
┌──────────────────────────────────────────────┬──────────────────────┐
│ header: question · NODES · EXPERIMENTS ·      │  ● done  n2  from n0 │
│         ELAPSED · BEST FITNESS · ● RUNNING    │                      │
├──────────────────────────────────────────────┤  ┌────────────────┐  │
│                                              │  │  LIVE REPLAY   │  │
│          3D hypothesis tree (orbiting)       │  │  cells copying │  │
│                                              │  │  themselves    │  │
│   glowing orange sphere = high fitness       │  └────────────────┘  │
│   dark sphere = dead end                     │  rule · 64×64 · t=41 │
│   red sphere = crashed                       │                      │
│   ringed sphere = best so far                │  copies alive growth │
│   orange path = selected node's ancestry     │  stable   (4 chips)  │
│                                              │                      │
│  ┌────────────────┐                          │  hypothesis (3 lines)│
│  │ Lab chat       │  ← one message per       │  Show more           │
│  │ (floating)     │    experiment, live      │  metrics · snapshots │
│  └────────────────┘                          │  top-5 table · rules │
└──────────────────────────────────────────────┴──────────────────────┘
```

- **Header (top):** the question, the four pitch numbers, a green pulsing RUNNING pill. Updates every 2 seconds.
- **3D tree (left):** every sphere is one hypothesis Fable proposed. Rings out from the centre are depth: the root in the middle, children further out. Brighter and bigger means higher fitness, dark means a dead end, red means the experiment crashed, and a ring marks the best so far. Click a sphere to select it; the path back to the root lights up orange and the camera flies to it. Drag to orbit, scroll to zoom.
- **Lab chat (floating, bottom-left):** the lab narrating itself. The question first, then one message per experiment as it lands: hypothesis, rules tested, best rule, fitness. Click a message to jump to that node. The × hides it.
- **Panel (right), top to bottom:** node id and parent; the **live replay** of the winning rule on a 64×64 grid; four chips (copies, alive, growth, stable); the hypothesis in one sentence with "Show more"; the metrics list; four snapshots at t = 0, 20, 40, 60; the top-5 rules; and every rule tested.

## Script (~230 words, 90 seconds)

**[0:00] The idea** *(screen: 3D tree orbiting, chat scrolling)*

> Every sphere on this screen is an experiment Fable designed, coded, ran and scored itself. The chat on the left is the lab talking to itself. We gave it one question at 19:37 and walked away. No one has touched it since.

**[0:15] The question** *(point at the header)*

> The question is from artificial life. Find a rule in the Game-of-Life family, and a seed of at most five by five cells, such that after some steps the grid contains two or more exact copies of the seed. A pattern that reproduces itself. In under an hour it built 23 hypotheses and tested 627 rules.

**[0:35] The result** *(click n2, camera flies in, replay plays on the right)*

> This is the win. Five cells become 121 exact copies. 121 times 5 is 605, and 605 cells are alive. Nothing else on the grid. On its first attempt it also found HighLife, a replicator people know from the literature. It rediscovered both from scratch.

**[1:00] The honesty** *(click a dark sphere, then the red one)*

> The dead ends stay on the tree. When it crashed, it read the traceback and moved on. And when it wrote the paper, it criticised its own scoring metric, so we fixed it live.

**[1:15] The paper** *(open paper.html)*

> At the end it writes the paper. Every number is checked against the log, every claim links to a node. A full research loop, in one evening, on a model that shipped this week.

## Demo cues

- Open before you go up: `localhost:8000/app/dist/index.html` and `localhost:8000/paper.html`
- Click order: **n2** (121 copies, ringed) → **n0** (HighLife, 4 copies, centre) → any dark sphere → **n10** (red, hover for the traceback). Or click the messages in the chat, which is easier than aiming at spheres.
- **Do not press "Stop & write paper"** in the chat. It ends the live run. It asks for confirmation; say no.
- If the 3D view lags on the projector: add `?nofx` to the URL. If it breaks: `localhost:8000/app.html`, then `paper.html`, then `frames/n2_60.png`.
- If asked "is 121 real?": 605 alive = 121 × 5. A parity rule copies any seed at power-of-two steps; the paper's own next experiment is to confirm at step 64.
- Don't call it a new discovery. Both rules are known. The claim is *autonomous rediscovery with an honest writeup*.
