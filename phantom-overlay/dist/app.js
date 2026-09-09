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

let checking = false;
byId("check-models").addEventListener("click", async () => {
  if (checking) return;
  if (!window.__TAURI__?.core?.invoke) {
    byId("model-status").textContent = "Open the desktop app to check local models.";
    return;
  }
  checking = true;
  byId("check-models").disabled = true;
  byId("model-status").textContent = "Checking local Ollama inventory…";
  byId("models").textContent = "";
  try {
    const state = await window.__TAURI__.core.invoke("model_readiness");
    byId("model-status").textContent = `${state.ready ? "Installed" : "Not ready"}: ${state.configured_model}. ${state.message}`;
    byId("models").textContent = state.models.length
      ? state.models.map(m => `${m.name} (${(m.size / 1024 ** 3).toFixed(2)} GiB on disk)`).join("\n")
      : "No models installed. Axiom never downloads models automatically.";
  } catch (error) {
    byId("model-status").textContent = `Readiness check failed: ${String(error)}`;
  } finally {
    checking = false;
    byId("check-models").disabled = false;
  }
});
