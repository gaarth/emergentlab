import React, { useEffect, useRef, useState } from "react";
import { parseRule, placeSeed, stepGrid } from "./ca.js";
import { num } from "./useTree.js";

function Replay({ replay }) {
  const cv = useRef(), lbl = useRef();
  useEffect(() => {
    if (!replay || !Array.isArray(replay.seed) || !Array.isArray(replay.seed[0])) return;
    const size = Number.isInteger(replay.size) && replay.size >= 8 ? replay.size : 64, steps = replay.steps > 0 ? replay.steps : 60;
    let b, s; try { [b, s] = parseRule(replay.rule); } catch { return; }
    const start = placeSeed(replay.seed, size); let grid = start.slice(), k = 0, hold = 0;
    const c = cv.current; c.width = size; c.height = size; const ctx = c.getContext("2d"), img = ctx.createImageData(size, size);
    const draw = () => {
      for (let i = 0; i < size * size; i++) { const on = grid[i]; img.data[i * 4] = on ? 255 : 5; img.data[i * 4 + 1] = on ? 122 : 7; img.data[i * 4 + 2] = on ? 61 : 11; img.data[i * 4 + 3] = 255; }
      ctx.putImageData(img, 0, 0); if (lbl.current) lbl.current.textContent = `t = ${k} / ${steps}`; window.__frames = (window.__frames || 0) + 1;
    };
    draw();
    const timer = setInterval(() => { if (k >= steps) { if (++hold < 12) return; grid = start.slice(); k = 0; hold = 0; } else { grid = stepGrid(grid, b, s, size); k++; } draw(); }, 66);
    window.__replayTimer = timer;
    return () => { clearInterval(timer); window.__replayTimer = null; };
  }, [JSON.stringify(replay)]);
  if (!replay) return null;
  return (
    <div>
      <canvas id="replay" ref={cv} />
      <div className="cap"><span><code>{replay.rule}</code> · {replay.size || 64}×{replay.size || 64} torus</span><span ref={lbl}>t = 0</span></div>
    </div>
  );
}

export default function NodePanel({ node: n, bestF }) {
  const [more, setMore] = useState(false);
  useEffect(() => setMore(false), [n && n.id]);
  if (!n) return <aside id="panel"><div className="empty"><div>Select a hypothesis node</div></div></aside>;
  const m = (n.metrics && typeof n.metrics === "object") ? n.metrics : {}, top = Array.isArray(n.results_top5) ? n.results_top5 : [];
  const frames = Array.isArray(n.frames) ? n.frames : [], rules = Array.isArray(n.rules_tested) ? n.rules_tested : [];
  const pct = num(n.fitness) && bestF > 0 ? Math.max(1, 100 * n.fitness / bestF) : 0;
  const stableCls = m.stable === true ? "ok" : m.stable === false ? "bad" : "";
  return (
    <aside id="panel">
      <div className="crumb"><span className={"badge " + n.status}><i />{n.status}</span><b>{n.id}</b><span className="path">from {n.parent ?? "root"} · depth {n.depth ?? "—"}</span></div>
      <Replay replay={n.replay} />
      <div className="chiprow">
        <div><span>copies</span><b>{m.copies ?? "—"}</b></div>
        <div><span>alive</span><b>{m.alive ?? "—"}</b></div>
        <div><span>growth</span><b>{num(m.growth) ? m.growth.toFixed(1) : "—"}</b></div>
        <div className={stableCls}><span>stable</span><b>{m.stable == null ? "—" : m.stable ? "✓" : "✕"}</b></div>
      </div>
      <div className={"hyp" + (!more ? " clamp" : "")}>{n.hypothesis || "—"}</div>
      {n.notes && more && <div className="notes">{n.notes}</div>}
      {(n.notes || (n.hypothesis || "").length > 160) && <button className="more" onClick={() => setMore(!more)}>{more ? "Show less" : "Show more"}</button>}
      {n.error && <pre className="err">{n.error}</pre>}
      <div className="kv">
        <div className="hot"><span>best rule</span><b>{n.best_rule || "—"}</b></div>
        <div className="hot"><span>fitness</span><b>{num(n.fitness) ? n.fitness : "—"}</b></div>
        <div><span>copies at t=60</span><b>{m.copies ?? "—"}</b></div>
        <div><span>alive cells</span><b>{m.alive ?? "—"}</b></div>
        <div><span>growth</span><b>{num(m.growth) ? m.growth.toFixed(1) + "×" : "—"}</b></div>
        <div className={stableCls}><span>stable</span><b>{m.stable == null ? "—" : m.stable ? "yes" : "no"}</b></div>
      </div>
      {pct > 0 && <div><div className="barwrap"><div className="bar" style={{ width: pct + "%" }} /></div><div className="barlbl"><span>fitness vs best in tree</span><span>{pct.toFixed(0)}%</span></div></div>}
      {frames.length > 0 && (
        <div><div className="sec"><span>snapshots</span><span>{n.best_rule}</span></div><div className="frames">
          {frames.map((f) => { const tt = /_(\d+)\.png$/.exec(f); return (
            <figure key={f}><img src={"/" + f.replace(/^\//, "")} alt="" onError={(e) => { e.target.parentNode.style.display = "none"; }} />t = {tt ? tt[1] : "?"}</figure>); })}
        </div></div>
      )}
      {top.length > 0 && (
        <div><div className="sec"><span>top rules in this node</span></div>
          <table><thead><tr><th>rule</th><th className="r">copies</th><th className="r">alive</th><th className="r">stable</th><th className="r">fitness</th></tr></thead><tbody>
            {top.map((x, i) => <tr key={i} className={x.rule === n.best_rule ? "best" : ""}><td>{x.rule}</td><td className="r">{x.copies}</td><td className="r">{x.alive}</td><td className="r">{x.stable ? "yes" : "no"}</td><td className="r">{x.fitness}</td></tr>)}
          </tbody></table></div>
      )}
      <div className="sec"><span>all rules tested</span><span>{rules.length}</span></div>
      <div className="chips">{rules.map((r) => <span key={r} className={"chip" + (r === n.best_rule ? " best" : "")}>{r}</span>)}</div>
    </aside>
  );
}
