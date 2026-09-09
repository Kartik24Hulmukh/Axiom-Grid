//! PhantomBridge — connects the Tauri overlay to the local Axiom-Grid runtime
//! over authenticated loopback HTTP IPC (127.0.0.1:7437 by default).
//!
//! Authentication uses the per-user OS-protected pairing file written by the
//! runtime (see `phantom-core/src/ipc_pairing.rs`); `AXIOM_API_TOKEN` remains an
//! explicit override for CI and tests. No secret is ever logged.

#[allow(dead_code)]
#[path = "../../../phantom-core/src/ipc_pairing.rs"]
mod ipc_pairing;

use anyhow::{Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::{Mutex, OnceLock};
use std::time::Duration;
use tokio::sync::oneshot;

const DEFAULT_RUNTIME_PORT: u16 = 7437;

#[derive(Serialize)]
struct MaterializeRequest {
    context: String,
}

#[derive(Deserialize)]
struct MaterializeResponse {
    suggestion: String,
    #[allow(dead_code)]
    word_count: usize,
}

#[derive(Deserialize)]
struct CancelResponse {
    cancelled: bool,
}

#[derive(Deserialize, Serialize)]
pub struct ModelInfo {
    pub name: String,
    pub size: u64,
    pub digest: String,
}
#[derive(Deserialize, Serialize)]
pub struct ReadinessResponse {
    pub ready: bool,
    pub configured_model: String,
    pub installed_models: Vec<ModelInfo>,
}

fn cancel_slot() -> &'static Mutex<Option<oneshot::Sender<()>>> {
    static SLOT: OnceLock<Mutex<Option<oneshot::Sender<()>>>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(None))
}

/// Runtime port: `AXIOM_RUNTIME_PORT` lets tests point at a loopback mock.
pub fn runtime_port() -> u16 {
    std::env::var("AXIOM_RUNTIME_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(DEFAULT_RUNTIME_PORT)
}

fn url(path: &str) -> String {
    format!("http://127.0.0.1:{}{path}", runtime_port())
}

fn client(timeout: Duration) -> Result<Client> {
    Ok(Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(timeout)
        .build()?)
}

/// Paired IPC token: environment override, else the OS-protected pairing file.
fn token() -> Result<String> {
    ipc_pairing::load_paired().with_context(|| {
        format!(
            "Not paired with the local runtime yet; start axiom-runtime once (pairing file: {})",
            ipc_pairing::pairing_file_path()
                .map(|p| p.display().to_string())
                .unwrap_or_else(|_| "unavailable".into())
        )
    })
}

pub struct PhantomBridge;

impl PhantomBridge {
    /// Cancel the in-flight materialize request, if any. Returns true when one was cancelled.
    /// The request future is dropped (closing our connection) and the runtime is told
    /// to abort its model request so generation stops end-to-end.
    pub fn cancel_active() -> bool {
        match cancel_slot().lock() {
            Ok(mut slot) => slot.take().map(|tx| tx.send(()).is_ok()).unwrap_or(false),
            Err(_) => false,
        }
    }

    async fn abort_runtime_generation() -> Result<bool> {
        let response = client(Duration::from_secs(2))?
            .post(url("/cancel"))
            .bearer_auth(token()?)
            .send()
            .await?
            .error_for_status()?
            .json::<CancelResponse>()
            .await?;
        Ok(response.cancelled)
    }

    /// Call the runtime to generate a preview suggestion for explicit context.
    pub async fn materialize(context: String) -> Result<String> {
        let client = client(Duration::from_secs(95))?;
        let token = token()?;
        let (cancel_tx, cancel_rx) = oneshot::channel::<()>();
        if let Ok(mut slot) = cancel_slot().lock() {
            *slot = Some(cancel_tx);
        }
        let request = async {
            let resp = client
                .post(url("/materialize"))
                .bearer_auth(&token)
                .json(&MaterializeRequest { context })
                .send()
                .await?
                .error_for_status()?
                .json::<MaterializeResponse>()
                .await?;
            Ok::<String, anyhow::Error>(resp.suggestion)
        };
        let result = tokio::select! {
            r = request => r,
            _ = cancel_rx => {
                // Best effort: the runtime also observes the dropped connection.
                let _ = Self::abort_runtime_generation().await;
                Err(anyhow::anyhow!("Generation cancelled by the user"))
            }
        };
        if let Ok(mut slot) = cancel_slot().lock() {
            slot.take();
        }
        result
    }

    pub async fn readiness() -> Result<ReadinessResponse> {
        Ok(client(Duration::from_secs(3))?
            .get(url("/readiness"))
            .bearer_auth(token()?)
            .send()
            .await?
            .error_for_status()?
            .json::<ReadinessResponse>()
            .await?)
    }

    /// Ping the runtime health endpoint (unauthenticated liveness only).
    #[allow(dead_code)]
    pub async fn ping() -> bool {
        let Ok(client) = client(Duration::from_secs(1)) else {
            return false;
        };
        client
            .get(url("/health"))
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false)
    }
}
