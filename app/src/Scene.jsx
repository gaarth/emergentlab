import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Line, Html, Stars } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";
import { SheetProvider, editable as e } from "@theatre/r3f";
import { getProject } from "@theatre/core";
import * as THREE from "three";
import { hierarchy, tree as d3tree } from "d3-hierarchy";
import { damp3, damp } from "maath/easing";
import state from "./theatre-state.json";
import { num } from "./useTree.js";

let project;
try { project = getProject("Discovery Lab", { state }); } catch (err) { console.warn("theatre state rejected", err); project = getProject("Discovery Lab"); }
export const introSheet = project.sheet("Intro");
const QS = new URLSearchParams(location.search);
const FX = !QS.has("nofx");           // ?nofx disables post-processing (headless tests, weak GPUs)
export function playIntro() {
  if (QS.has("nointro")) { project.ready.then(() => { introSheet.sequence.position = 3; }); return; }
  const done = project.ready.then(() => introSheet.sequence.play({ range: [0, 3] }));
  done.catch((err) => console.warn("intro failed", err));
  setTimeout(() => { if (introSheet.sequence.position < 3) introSheet.sequence.position = 3; }, 4000);   // never leave the tree hidden
}

const ORANGE = new THREE.Color("#ff7a3d"), GREY = new THREE.Color("#3a3a40"), RED = new THREE.Color("#ff4d4d"), WHITE = new THREE.Color("#ffffff");
const RING = 3.2;     // radius per depth level

// Radial 3D layout: depth -> radius, d3 tidy order -> angle, a gentle vertical wave for depth.
export function layout(nodes) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const data = { id: "__root", children: [] }, map = new Map([["__root", data]]);
  nodes.forEach((n) => map.set(n.id, { id: n.id, node: n, children: [] }));
  nodes.forEach((n) => {
    let p = n.parent == null ? null : String(n.parent);
    const seen = new Set([n.id]);
    for (let c = p; c != null && byId.has(c); c = byId.get(c).parent == null ? null : String(byId.get(c).parent)) { if (seen.has(c)) { p = null; break; } seen.add(c); }
    (p != null && byId.has(p) ? map.get(p) : data).children.push(map.get(n.id));
  });
  const root = hierarchy(data);
  d3tree().size([Math.PI * 2, 1])(root);
  const pos = new Map(), links = [];
  root.descendants().forEach((d) => {
    if (d.data.id === "__root") return;
    const depth = d.depth - 1, r = depth * RING;
    const a = d.x - Math.PI / 2;
    const p = new THREE.Vector3(Math.cos(a) * r, Math.sin(depth * 0.9) * 0.8 + depth * 0.35, Math.sin(a) * r);
    pos.set(d.data.id, p);
  });
  root.links().forEach((l) => { if (l.source.data.id !== "__root") links.push([l.source.data.id, l.target.data.id]); });
  const maxDepth = root.height - 1;
  return { pos, links, radius: Math.max(RING, maxDepth * RING) };
}

function fitnessColor(n, maxF) {
  if (n.status === "error") return RED.clone().multiplyScalar(0.7);
  if (n.status !== "done") return new THREE.Color("#8a5a3a");
  return GREY.clone().lerp(ORANGE, Math.min(1, (num(n.fitness) ? n.fitness : 0) / Math.max(maxF, 1e-6)));
}

function Node({ n, p, isBest, isSelected, maxF, onPick, onHover, fresh }) {
  const ref = useRef(), mat = useRef(), ring = useRef();
  const target = useMemo(() => new THREE.Vector3(), []);
  const [hover, setHover] = useState(false);
  const base = isBest ? 0.22 : n.status === "error" ? 0.1 : 0.13 + Math.min(0.06, (num(n.fitness) ? n.fitness : 0) / Math.max(maxF, 1e-6) * 0.06);
  const color = useMemo(() => fitnessColor(n, maxF), [n.status, n.fitness, maxF]);
  useEffect(() => { if (ref.current && fresh) ref.current.scale.setScalar(0.001); }, []);
  useFrame((st, dt) => {
    if (!ref.current) return;
    target.copy(p);
    damp3(ref.current.position, target, 0.35, dt);
    const s = (hover || isSelected ? 1.35 : 1) * base * (n.status === "running" ? 1 + Math.sin(st.clock.elapsedTime * 5) * 0.12 : 1);
    damp3(ref.current.scale, [s, s, s], 0.25, dt);
    if (mat.current) {
      const glow = isBest ? 1.1 + Math.sin(st.clock.elapsedTime * 2) * 0.25 : n.status === "done" ? 0.3 + (num(n.fitness) ? n.fitness : 0) / Math.max(maxF, 1e-6) * 0.5 : 0.2;
      mat.current.emissiveIntensity = THREE.MathUtils.damp(mat.current.emissiveIntensity, hover || isSelected ? glow + 0.4 : glow, 6, dt);
    }
    if (ring.current) { ring.current.lookAt(st.camera.position); ring.current.material.opacity = THREE.MathUtils.damp(ring.current.material.opacity, isSelected || isBest ? 0.9 : 0, 8, dt); }
  });
  return (
    <group>
      <mesh ref={ref} position={p} onClick={(ev) => { ev.stopPropagation(); onPick(n.id); }}
            onPointerOver={(ev) => { ev.stopPropagation(); setHover(true); onHover(n.id); }} onPointerOut={() => { setHover(false); onHover(null); }}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshStandardMaterial ref={mat} color={color} emissive={color} emissiveIntensity={0.6} roughness={0.25} metalness={0.1} />
      </mesh>
      <mesh ref={ring} position={p}>
        <ringGeometry args={[base * 1.7, base * 1.85, 48]} />
        <meshBasicMaterial color={isBest && !isSelected ? ORANGE : WHITE} transparent opacity={0} side={THREE.DoubleSide} />
      </mesh>
      {(isSelected || isBest || hover) && (
        <Html position={[p.x, p.y + base + 0.3, p.z]} center distanceFactor={12} style={{ pointerEvents: "none" }}>
          <div className={"label" + (isBest ? " best" : "")}>{n.id}{n.best_rule ? ` · ${n.best_rule}` : ""}{num(n.fitness) && n.status === "done" ? ` · ${n.fitness.toFixed(1)}` : ""}{isBest ? " · best" : ""}</div>
        </Html>
      )}
    </group>
  );
}

// The path from the selected node back to the root is drawn in orange (same flow as the 2D viewer).
function Links({ links, pos, nodesById, selected }) {
  const lit = new Set();
  for (let c = selected; c && nodesById.has(c); c = nodesById.get(c).parent == null ? null : String(nodesById.get(c).parent)) { if (lit.has(c)) break; lit.add(c); }
  return links.map(([a, b]) => {
    const pa = pos.get(a), pb = pos.get(b); if (!pa || !pb) return null;
    const mid = pa.clone().lerp(pb, 0.5); mid.y += 0.6;
    const pts = new THREE.QuadraticBezierCurve3(pa, mid, pb).getPoints(20);
    const n = nodesById.get(b), hot = lit.has(a) && lit.has(b);
    const c = n?.status === "error" ? "#c98080" : "#ffffff";
    return <Line key={a + ">" + b} points={pts} color={hot ? "#ff8a4c" : c} lineWidth={hot ? 2.4 : 0.8} transparent opacity={hot ? 1 : 0.4} />;
  });
}

// Smooth camera: slow orbit of the whole tree, or a gentle fly-to when a node is selected. User drags pause it.
function CameraRig({ focus, radius, controls }) {
  const { camera } = useThree();
  const angle = useRef(0.6), idleSince = useRef(0), userBusy = useRef(false);
  useEffect(() => {
    const c = controls.current; if (!c) return;
    const on = () => { userBusy.current = true; }, off = () => { userBusy.current = false; idleSince.current = performance.now(); };
    c.addEventListener("start", on); c.addEventListener("end", off);
    return () => { c.removeEventListener("start", on); c.removeEventListener("end", off); };
  }, [controls.current]);
  useFrame((st, dt) => {
    const c = controls.current; if (!c) return;
    if (userBusy.current || performance.now() - idleSince.current < 8000) return;   // respect the user for 8 s
    const R = Math.max(10, radius * 2.2 + 6);
    if (focus) {
      const dir = focus.clone().sub(c.target).normalize();
      const want = focus.clone().add(new THREE.Vector3(dir.x, 0.45, dir.z).normalize().multiplyScalar(6));
      damp3(camera.position, want, 0.9, dt); damp3(c.target, focus, 0.7, dt);
    } else {
      angle.current += dt * 0.08;
      const want = new THREE.Vector3(Math.cos(angle.current) * R, R * 0.45, Math.sin(angle.current) * R);
      damp3(camera.position, want, 1.4, dt); damp3(c.target, [0, 1, 0], 1.0, dt);
    }
    c.update();
  });
  return null;
}

export default function Scene({ tree, selected, onPick, onHover }) {
  const controls = useRef();
  const nodes = tree?.nodes || [];
  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [tree]);
  const { pos, links, radius } = useMemo(() => layout(nodes), [tree]);
  const maxF = useMemo(() => Math.max(1, ...nodes.filter((n) => n.status === "done" && num(n.fitness)).map((n) => n.fitness)), [tree]);
  const seen = useRef(new Set());
  const freshIds = useMemo(() => { const f = new Set(); nodes.forEach((n) => { if (!seen.current.has(n.id)) { f.add(n.id); } }); nodes.forEach((n) => seen.current.add(n.id)); return f; }, [tree]);
  const focus = selected && pos.get(selected) ? pos.get(selected) : null;
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 12, 26], fov: 42, near: 0.1, far: 400 }} gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
            onPointerMissed={() => onPick(null)}>
      <color attach="background" args={["#08080b"]} />
      <fog attach="fog" args={["#08080b", 30, 110]} />
      <SheetProvider sheet={introSheet}>
        <ambientLight intensity={0.3} />
        <e.pointLight theatreKey="Key" position={[8, 14, 10]} intensity={35} decay={1} color="#ffd9c2" />
        <e.pointLight theatreKey="Fill" position={[-14, 6, -8]} intensity={12} decay={1} color="#6f8cff" />
        <Stars radius={120} depth={40} count={2500} factor={3} saturation={0} fade speed={0.4} />
        <e.group theatreKey="Tree">
          <Links links={links} pos={pos} nodesById={nodesById} selected={selected} />
          {nodes.map((n) => pos.get(n.id) && (
            <Node key={n.id} n={n} p={pos.get(n.id)} isBest={n.id === tree?.best_node_id} isSelected={n.id === selected}
                  maxF={maxF} onPick={onPick} onHover={onHover} fresh={freshIds.has(n.id) && seen.current.size > nodes.length - freshIds.size} />
          ))}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.2, 0]}>
            <ringGeometry args={[RING - 0.02, RING, 128]} /><meshBasicMaterial color="#26262c" transparent opacity={0.5} />
          </mesh>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.2, 0]}>
            <ringGeometry args={[RING * 2 - 0.02, RING * 2, 128]} /><meshBasicMaterial color="#26262c" transparent opacity={0.35} />
          </mesh>
        </e.group>
        <hemisphereLight args={["#5a6cff", "#2a1408", 0.5]} />
        <OrbitControls ref={controls} enableDamping dampingFactor={0.06} enablePan={false} minDistance={3} maxDistance={120} />
        <CameraRig focus={focus} radius={radius} controls={controls} />
        {FX && (
          <EffectComposer disableNormalPass>
            <Bloom luminanceThreshold={0.85} luminanceSmoothing={0.25} intensity={0.45} mipmapBlur />
            <Vignette eskil={false} offset={0.2} darkness={0.75} />
          </EffectComposer>
        )}
      </SheetProvider>
    </Canvas>
  );
}
