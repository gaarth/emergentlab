import React, { useEffect, useMemo, useRef, useState } from "react";
import { num } from "./useTree.js";

// The chat is a projection of tree.json: the question, then one message per node as it lands, then paper status.
export function chatMessages(tree) {
  if (!tree) return [];
  const msgs = [{ id: "q", role: "user", text: tree.question }];
  msgs.push({ id: "start", role: "lab", text: "Starting the lab. I'll propose one experiment at a time, run it in a sandbox, and grow the hypothesis tree as I go." });
  for (const n of tree.nodes || []) {
    if (n.status === "running" || n.status === "pending") {
      msgs.push({ id: n.id, role: "lab", node: n.id, running: true, text: `${n.id} · ${n.hypothesis || "…"}`, sub: `testing ${(n.rules_tested || []).length} rules${n.parent ? ` · branching from ${n.parent}` : ""}` });
    } else if (n.status === "error") {
      msgs.push({ id: n.id, role: "lab", node: n.id, error: true, text: `${n.id} failed · ${n.hypothesis || ""}`, sub: (n.error || "").split("\n").filter(Boolean).slice(-1)[0] || "error" });
    } else {
      const m = n.metrics || {};
      msgs.push({ id: n.id, role: "lab", node: n.id, best: n.id === tree.best_node_id,
        text: `${n.id} · ${n.hypothesis || ""}`,
        sub: `${(n.rules_tested || []).length} rules → best ${n.best_rule || "—"} · fitness ${num(n.fitness) ? n.fitness.toFixed(1) : "—"} · ${m.copies ?? "—"} copies${m.stable === false ? " · unstable" : ""}` });
    }
  }
  if (tree.status === "writing_paper") msgs.push({ id: "paper", role: "lab", running: true, text: "Writing the paper from the tree…" });
  if (tree.status === "done") msgs.push({ id: "paper", role: "lab", link: "/paper.html", text: "The paper is ready.", sub: "Read the paper →" });
  return msgs;
}

export default function Chat({ tree, selected, onPick, onStart, onStop, onMode, busy, apiOk }) {
  const [q, setQ] = useState("");
  const [mock, setMock] = useState(false);          // default: the real lab, Claude Fable 5.1 via lab.py
  const setMode = (m) => { setMock(m); onMode?.(m); };
  const msgs = useMemo(() => chatMessages(tree), [tree]);
  const listRef = useRef(), stick = useRef(true);
  useEffect(() => { const el = listRef.current; if (el && stick.current) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }); }, [msgs.length, tree?.status]);
  const running = tree && tree.status === "running";
  return (
    <div className="chat glass">
      <div className="chat-head"><span className="dot" /> Discovery Lab <span className="muted">{running ? "running" : tree?.status === "done" ? "finished" : tree ? tree.status.replace("_", " ") : "idle"}</span></div>
      <div className="msgs" ref={listRef} onScroll={(e) => { const el = e.target; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60; }}>
        {!tree && <div className="msg lab"><div className="bubble">Ask me an open scientific question. Claude Fable 5.1 will write and run the experiments while you watch the hypothesis tree grow, then write up the paper.<div className="sub">e.g. "Find a Life-like CA rule and a seed of at most 5×5 cells under which the seed self-replicates."</div></div></div>}
        {msgs.map((m) => (
          <div key={m.id} className={`msg ${m.role} ${m.node ? "clickable" : ""} ${m.node && m.node === selected ? "sel" : ""}`} onClick={() => m.node && onPick(m.node)}>
            <div className={`bubble ${m.error ? "err" : ""} ${m.best ? "best" : ""} ${m.running ? "running" : ""}`}>
              <div>{m.text}</div>
              {m.sub && (m.link ? <a className="sub link" href={m.link} target="_blank" rel="noreferrer">{m.sub}</a> : <div className="sub">{m.sub}</div>)}
            </div>
          </div>
        ))}
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); if (q.trim() && !running) onStart(q.trim(), mock); }}>
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={2} placeholder="Enter your research question…" disabled={running || busy}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.target.form.requestSubmit(); } }} />
        <div className="row">
          <label className="mock"><input type="checkbox" checked={mock} onChange={(e) => setMode(e.target.checked)} disabled={running} /> mock lab (no API)</label>
          {running ? <button type="button" className="stop" onClick={onStop} disabled={busy}>Stop & write paper</button>
                   : <button type="submit" disabled={busy || !apiOk} title={apiOk ? "" : "server.py is not running"}>{busy ? "…" : "Run"}</button>}
        </div>
      </form>
    </div>
  );
}
