"use strict";
const byId = id => document.getElementById(id);
let generation = 0;
let pending = false;
byId("generate").addEventListener("click", async () => {
  if (pending) return;
  const context = byId("context").value.trim();
  if (!context) { byId("status").textContent = "Add an instruction and text first."; return; }
  if (!window.__TAURI__?.core?.invoke) { byId("status").textContent = "Open this interface in the Axiom-Grid desktop app."; return; }
  const current = ++generation;
  pending = true;
  byId("generate").disabled = true;
  byId("cancel").disabled = false;
  byId("result").value = "";
  byId("status").textContent = "Generating a preview. No text will be inserted.";
  try {
    const text = await window.__TAURI__.core.invoke("trigger_materialize", { context });
    if (current !== generation) return;
    byId("result").value = text;
    byId("status").textContent = "Ready for your review. Nothing has been inserted.";
  } catch (error) {
    if (current === generation) byId("status").textContent = `Generation failed: ${String(error)}`;
  } finally {
    pending = false;
    byId("generate").disabled = false;
  }
});
byId("cancel").addEventListener("click", () => {
  ++generation;
  byId("result").value = "";
  byId("cancel").disabled = true;
  byId("status").textContent = pending ? "Discarded. Local generation may finish in the background." : "Preview discarded.";
});
