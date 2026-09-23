import React, { useEffect, useRef, useState } from "react";
import { parseRule, placeSeed, stepGrid } from "./ca.js";
import { num } from "./useTree.js";

function Replay({ replay }) {
  const cv = useRef(); const [t, setT] = useState(0);
  useEffect(() => {
    if (!replay || !Array.isArray(replay.seed) || !Array.isArray(replay.seed[0])) return;
    const size = Number.isInteger(replay.size) && replay.size >= 8 ? replay.size : 64, steps = replay.steps > 0 ? replay.steps : 60;
    let b, s; try { [b, s] = parseRule(replay.rule); } catch { return; }
    const start = placeSeed(replay.seed, size); let grid = start.slice(), k = 0, hold = 0;
    const c = cv.current; c.width = size; c.height = size; const ctx = c.getContext("2d"), img = ctx.createImageData(size, size);
    const draw = () => { for (let i = 0; i < size * size; i++) { const on = grid[i]; img.data[i * 4] = on ? 255 : 6; img.data[i * 4 + 1] = on ? 122 : 6; img.data[i * 4 + 2] = on ? 61 : 9; img.data[i * 4 + 3] = 255; } ctx.putImageData(img, 0, 0); setT(k); };
    draw();
    const timer = setInterval(() => { if (k >= steps) { if (++hold < 12) return; grid = start.slice(); k = 0; hold = 0; } else { grid = stepGrid(grid, b, s, size); k++; } draw(); }, 66);
    return () => clearInterval(timer);
  }, [JSON.stringify(replay)]);
  if (!replay) return null;
  return <div className="replay"><div className="cap"><span>replay · <b>{replay.rule}</b> · {replay.size || 64}² torus</span><span>t={t}/{replay.steps || 60}</span></div><canvas ref={cv} /></div>;
}

export default function NodePanel({ node, isBest, onClose }) {
  if (!node) return null;
  const m = node.metrics || {};
  return (
    <div className="panel glass">
      <div className="panel-head">
        <span className={`pill ${node.status}`}>{node.status}</span> <b>{node.id}</b> <span className="muted">← {node.parent ?? "root"} · depth {node.depth ?? "—"}</span>
        {isBest && <span className="pill best">best</span>}
        <button className="close" onClick={onClose} aria-label="close">×</button>
      </div>
      <h3>{node.hypothesis || "—"}</h3>
      {node.notes && <p className="muted">{node.notes}</p>}
      {node.error && <pre className="err">{node.error}</pre>}
      <div className="metrics">
        {[["best rule", node.best_rule || "—"], ["fitness", num(node.fitness) ? node.fitness : "—"], ["copies", m.copies ?? "—"],
          ["alive", m.alive ?? "—"], ["growth", num(m.growth) ? m.growth.toFixed(2) : "—"], ["stable", m.stable == null ? "—" : m.stable ? "yes" : "no"]]
          .map(([k, v]) => <div key={k}>{k}<b>{String(v)}</b></div>)}
      </div>
      <div className="muted small">tested ({(node.rules_tested || []).length}): {(node.rules_tested || []).join(", ") || "—"}</div>
      <Replay replay={node.replay} />
      {Array.isArray(node.frames) && node.frames.length > 0 && (
        <div className="frames">{node.frames.map((f) => { const tt = /_(\d+)\.png$/.exec(f); return (
          <figure key={f}><img src={"/" + f.replace(/^\//, "")} alt="" onError={(e) => { e.target.style.visibility = "hidden"; }} /><figcaption>{tt ? `t=${tt[1]}` : ""}</figcaption></figure>); })}</div>
      )}
    </div>
  );
}
