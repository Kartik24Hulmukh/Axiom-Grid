"use strict";
const byId = id => document.getElementById(id);
let generation = 0;
let pending = false;
async function checkReadiness() {
  const status = byId("model-status");
  if (!window.__TAURI__?.core?.invoke) { status.textContent = "Desktop runtime required."; return; }
  status.textContent = "Checking local model…";
  try {
    const info = await window.__TAURI__.core.invoke("model_readiness");
    const count = Array.isArray(info.installed_models) ? info.installed_models.length : 0;
    status.textContent = info.ready
      ? `Ready: ${info.configured_model} (${count} installed model${count === 1 ? "" : "s"}).`
      : `Not ready: configured model ${info.configured_model} is not installed. Install it explicitly, then retry.`;
    byId("generate").disabled = !info.ready;
  } catch (error) {
    status.textContent = `Not ready: ${String(error)}`;
    byId("generate").disabled = true;
  }
}
byId("retry-model").addEventListener("click", checkReadiness);
checkReadiness();
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
