import React, { useEffect, useMemo, useRef, useState } from "react";
import Scene, { playIntro } from "./Scene.jsx";
import Chat from "./Chat.jsx";
import NodePanel from "./NodePanel.jsx";
import { useTree, stats, num } from "./useTree.js";

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
  const [chatOpen, setChatOpen] = useState(true);
  const introPlayed = useRef(false);
  const s = useMemo(() => stats(tree), [tree]);
  const nodesById = useMemo(() => new Map((tree?.nodes || []).map((n) => [n.id, n])), [tree]);
  const bestF = useMemo(() => { const d = (tree?.nodes || []).filter((n) => n.status === "done" && num(n.fitness)); return d.length ? Math.max(...d.map((n) => n.fitness)) : 0; }, [tree]);

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

  // Clicking empty space in the 3D view keeps the current selection (the panel always shows something).
  const pick = (id) => { if (id == null) return; setSelected(id); setUserPicked(true); };
  const post = async (path, body) => {
    setBusy(true);
    try { const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }); if (!r.ok) alert((await r.json()).error || r.statusText); }
    catch (e) { alert("server.py is not reachable: " + e.message); }
    finally { setBusy(false); }
  };
  const onStart = (question, mock) => { introPlayed.current = false; setSelected(null); setUserPicked(false); setHideStart(polled?.started_at ?? null); post("/api/start", { question, mock }); };
  const onMode = (mock) => { if (!mock && polled && polled.status !== "running") { setHideStart(polled.started_at); setSelected(null); setUserPicked(false); introPlayed.current = false; } if (mock) setHideStart(null); };
  const node = selected ? nodesById.get(selected) : null;
  const st = String(tree?.status || ""), stCls = { running: "running", writing_paper: "writing", done: "done" }[st] || "";

  return (
    <div className="app">
      <header>
        <div className="brand"><div><h1>Autonomous Discovery Lab</h1><p title={tree?.question}>{tree?.question || "waiting for tree.json…"}</p></div></div>
        <div className="stats">
          <div className="stat"><span>nodes</span><b id="s-nodes">{s.nodes}</b></div>
          <div className="stat"><span>experiments</span><b id="s-exp">{s.experiments.toLocaleString("en-US")}</b></div>
          <div className="stat"><span>elapsed</span><b id="s-time">{s.elapsed}</b></div>
          <div className="stat hot"><span>best fitness</span><b id="s-best">{s.best == null ? "—" : s.best.toFixed(1)}</b></div>
        </div>
        <span className={"badge " + stCls} id="status"><i />{st.replace(/_/g, " ").toUpperCase() || "…"}</span>
        {st === "done" && <a className="paper" id="paper-btn" href="/paper.html" target="_blank" rel="noreferrer">Read the paper →</a>}
      </header>
      <main>
        <div className="stage">
          <Scene tree={tree} selected={selected} onPick={pick} onHover={setHover} />
          <div className="legend"><span><i style={{ background: "#ff8a4c" }} />fitness (size + glow)</span><span><i style={{ background: "#3a1d1d", border: "1.5px solid #f87171" }} />error</span><span><i style={{ border: "2px solid #ff8a4c", background: "none" }} />best so far</span><span className="muted">drag to orbit · scroll to zoom</span></div>
          {hover && nodesById.get(hover) && hover !== selected && <div className="hint">{nodesById.get(hover).hypothesis}</div>}
          {chatOpen
            ? <div className="chatwrap"><button className="chat-toggle" onClick={() => setChatOpen(false)} aria-label="hide chat">×</button>
                <Chat tree={tree} selected={selected} onPick={pick} onStart={onStart} onStop={() => { if (confirm("Stop the lab and write the paper now? This ends the live run.")) post("/api/stop"); }} onMode={onMode} busy={busy} apiOk={apiOk} /></div>
            : <button className="chat-fab" onClick={() => setChatOpen(true)}><span className="dot" /> Lab chat</button>}
        </div>
        <NodePanel node={node} bestF={bestF} />
      </main>
    </div>
  );
}
