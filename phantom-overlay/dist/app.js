"use strict";
const byId = id => document.getElementById(id);
let generation = 0;
let pending = false;
let modelReady = false;
let readinessCheck = 0;
let cancelling = false;
function updateGenerate() {
  byId("generate").disabled = pending || cancelling || !modelReady;
}
async function checkReadiness() {
  const status = byId("model-status");
  const current = ++readinessCheck;
  modelReady = false;
  updateGenerate();
  if (!window.__TAURI__?.core?.invoke) { status.textContent = "Desktop runtime required."; return; }
  status.textContent = "Checking local model…";
  try {
    const info = await window.__TAURI__.core.invoke("model_readiness");
    if (current !== readinessCheck) return;
    modelReady = info.ready === true;
    const count = Array.isArray(info.installed_models) ? info.installed_models.length : 0;
    status.textContent = modelReady
      ? `Ready: ${info.configured_model} (${count} installed model${count === 1 ? "" : "s"}).`
      : `Not ready: configured model ${info.configured_model} is not installed. Install it explicitly, then retry.`;
    updateGenerate();
  } catch (error) {
    if (current !== readinessCheck) return;
    modelReady = false;
    status.textContent = `Not ready: ${String(error)}`;
    updateGenerate();
  }
}
byId("retry-model").addEventListener("click", checkReadiness);
checkReadiness();
byId("generate").addEventListener("click", async () => {
  if (pending || cancelling) return;
  const context = byId("context").value.trim();
  if (!context) { byId("status").textContent = "Add an instruction and text first."; return; }
  if (!window.__TAURI__?.core?.invoke) { byId("status").textContent = "Open this interface in the Axiom-Grid desktop app."; return; }
  if (!modelReady) { byId("status").textContent = "Wait for a successful local model readiness check."; return; }
  const current = ++generation;
  pending = true;
  updateGenerate();
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
    updateGenerate();
  }
});
byId("cancel").addEventListener("click", async () => {
  if (cancelling) return;
  const wasPending = pending;
  const current = ++generation;
  byId("result").value = "";
  byId("cancel").disabled = true;
  if (wasPending && window.__TAURI__?.core?.invoke) {
    cancelling = true;
    updateGenerate();
    byId("status").textContent = "Discarded. Requesting cancellation…";
    try {
      const accepted = await window.__TAURI__.core.invoke("cancel_materialize");
      if (current === generation) {
        // The command acknowledges the bridge signal, not confirmed model termination.
        byId("status").textContent = accepted
          ? "Discarded. Cancellation requested. No result will be displayed."
          : "Discarded. No active request acknowledged cancellation; generation may still finish.";
      }
    } catch (error) {
      if (current === generation) byId("status").textContent = `Discarded. Cancellation could not be confirmed: ${String(error)}. Local generation may continue.`;
    } finally {
      cancelling = false;
      updateGenerate();
    }
  } else {
    byId("status").textContent = wasPending ? "Discarded. Local generation may finish in the background." : "Preview discarded.";
  }
});
