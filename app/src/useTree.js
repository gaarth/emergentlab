import { useEffect, useRef, useState } from "react";

// Polls tree.json every 2 s with cache-busting; a half-written file keeps the previous tree.
export function useTree(src = "/tree.json", poll = 2000) {
  const [tree, setTree] = useState(null);
  const last = useRef("");
  useEffect(() => {
    let alive = true, timer;
    const tick = async () => {
      try {
        const r = await fetch(`${src}?t=${Date.now()}`, { cache: "no-store" });
        if (r.ok) {
          const txt = await r.text();
          if (txt !== last.current) {
            const t = JSON.parse(txt);
            if (t && Array.isArray(t.nodes)) { last.current = txt; if (alive) setTree(t); }
          }
        } else if (r.status === 404 && alive) { last.current = ""; setTree(null); }
      } catch (e) { /* half-written or offline: keep previous */ }
      if (alive) timer = setTimeout(tick, poll);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [src, poll]);
  return tree;
}

export const num = (v) => typeof v === "number" && isFinite(v);

export function stats(tree) {
  const nodes = tree?.nodes || [];
  const done = nodes.filter((n) => n.status === "done" && num(n.fitness));
  const t0 = new Date(tree?.started_at);
  const mins = isNaN(t0) ? null : Math.max(0, Math.round((Date.now() - t0) / 60000));
  return {
    nodes: nodes.length,
    experiments: nodes.reduce((a, n) => a + (Array.isArray(n.rules_tested) ? n.rules_tested.length : 0), 0),
    elapsed: mins == null ? "—" : mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`,
    best: done.length ? Math.max(...done.map((n) => n.fitness)) : null,
    status: tree?.status || "idle",
  };
}
