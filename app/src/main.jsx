import React from "react";
import { createRoot } from "react-dom/client";
import studio from "@theatre/studio";
import extension from "@theatre/r3f/dist/extension";
import App from "./App.jsx";
import { parseRule, placeSeed, stepGrid } from "./ca.js";
import "./styles.css";

// Test hook: the replay engine must be bit-exact with ca.py (tests/app.spec.js compares against tests/ca_grid.py).
window.stepCA = (rule, seed, size = 64, steps = 0) => {
  const [b, s] = parseRule(rule); let g = placeSeed(seed, size);
  for (let i = 0; i < steps; i++) g = stepGrid(g, b, s, size);
  return Array.from(g);
};

// Theatre.js studio only in dev: press Alt+\ to toggle the editor UI.
if (import.meta.env.DEV) {
  studio.initialize();
  studio.extend(extension);
  studio.ui.hide();
}

createRoot(document.getElementById("root")).render(<App />);
