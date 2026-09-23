import React, { useEffect, useMemo, useRef, useState } from "react";
import Scene, { playIntro } from "./Scene.jsx";
import Chat from "./Chat.jsx";
import NodePanel from "./NodePanel.jsx";
import { useTree, stats } from "./useTree.js";

export default function App() {
  const polled = useTree();
  // Blank stage: after Run (or switching off the mock) hide the previous run until a new tree.json appears.
  const [hideStart, setHideStart] = useState(null);
  const tree = polled && polled.started_at === hideStart ? null : polled;
  const [selected, setSelected] = useState(null);
  const [userPicked, setUserPicked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [apiOk, setApiOk] = useState(false);
  const [hover, setHover] = useState(null);
  const introPlayed = useRef(false);
  const s = useMemo(() => stats(tree), [tree]);
  const nodesById = useMemo(() => new Map((tree?.nodes || []).map((n) => [n.id, n])), [tree]);

  useEffect(() => { fetch("/api/status").then((r) => setApiOk(r.ok)).catch(() => setApiOk(false)); }, [tree?.status]);
  useEffect(() => { if (tree && !introPlayed.current) { introPlayed.current = true; playIntro(); } }, [tree]);
  // Follow the best node until the user picks one; drop a selection whose node vanished (restarted run).
  useEffect(() => {
    if (!tree) { setSelected(null); setUserPicked(false); return; }
    const hash = location.hash.slice(1);                      // paper citations link here as #n17
    if (hash && !userPicked && nodesById.has(hash)) { setSelected(hash); setUserPicked(true); history.replaceState(null, "", location.pathname + location.search); return; }
    if (selected && !nodesById.has(selected)) { setSelected(null); setUserPicked(false); }
    if (!userPicked && tree.best_node_id && nodesById.has(tree.best_node_id) && selected !== tree.best_node_id) setSelected(tree.best_node_id);
  }, [tree]);

  const pick = (id) => { setSelected(id); setUserPicked(id != null); };
  const post = async (path, body) => {
    setBusy(true);
    try { const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }); if (!r.ok) alert((await r.json()).error || r.statusText); }
    catch (e) { alert("server.py is not reachable: " + e.message); }
    finally { setBusy(false); }
  };
  const onStart = (question, mock) => { introPlayed.current = false; setSelected(null); setUserPicked(false); setHideStart(polled?.started_at ?? null); post("/api/start", { question, mock }); };
  const onMode = (mock) => { if (!mock && polled && polled.status !== "running") { setHideStart(polled.started_at); setSelected(null); setUserPicked(false); introPlayed.current = false; } if (mock) setHideStart(null); };
  const node = selected ? nodesById.get(selected) : null;

  return (
    <div className="app">
      <Scene tree={tree} selected={selected} onPick={pick} onHover={setHover} />
      <header className="hud glass">
        <div className="brand">Autonomous Discovery Lab</div>
        {[["nodes", s.nodes], ["experiments", s.experiments.toLocaleString("en-US")], ["elapsed", s.elapsed], ["best fitness", s.best == null ? "—" : s.best.toFixed(1)]]
          .map(([k, v]) => <div className="stat" key={k}><span>{k}</span><b>{v}</b></div>)}
        <span className={`status ${s.status}`}>{s.status.replace("_", " ")}</span>
        {tree?.status === "done" && <a className="paper" href="/paper.html" target="_blank" rel="noreferrer">Read the paper →</a>}
      </header>
      <Chat tree={tree} selected={selected} onPick={pick} onStart={onStart} onStop={() => post("/api/stop")} onMode={onMode} busy={busy} apiOk={apiOk} />
      <NodePanel node={node} isBest={node && node.id === tree?.best_node_id} onClose={() => pick(null)} />
      {hover && !node && nodesById.get(hover) && <div className="hint glass">{nodesById.get(hover).hypothesis}</div>}
      {tree && !node && <div className="hint glass subtle">Click a node or a message to inspect it · drag to orbit</div>}
    </div>
  );
}
