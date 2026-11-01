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
use std::sync::{Arc, Mutex, OnceLock};
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
    pub expected_digest: String,
    pub identity_check_scope: String,
    pub installed_models: Vec<ModelInfo>,
}

struct ActiveMaterialize {
    owner: Arc<()>,
    cancel_tx: Option<oneshot::Sender<()>>,
}

fn cancel_slot() -> &'static Mutex<Option<ActiveMaterialize>> {
    static SLOT: OnceLock<Mutex<Option<ActiveMaterialize>>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(None))
}

/// Admission stays held even after the cancellation sender has been consumed.
/// Dropping the owning future releases its lease, including during cancel acknowledgement.
struct MaterializeLease {
    owner: Arc<()>,
}

impl MaterializeLease {
    fn reserve() -> Result<(Self, oneshot::Receiver<()>)> {
        let mut slot = cancel_slot()
            .lock()
            .map_err(|_| anyhow::anyhow!("Materialize admission lock poisoned"))?;
        if slot.is_some() {
            anyhow::bail!("A materialize request is already active");
        }
        let owner = Arc::new(());
        let (cancel_tx, cancel_rx) = oneshot::channel();
        *slot = Some(ActiveMaterialize {
            owner: Arc::clone(&owner),
            cancel_tx: Some(cancel_tx),
        });
        Ok((Self { owner }, cancel_rx))
    }
}

impl Drop for MaterializeLease {
    fn drop(&mut self) {
        // A poisoned lock is deliberately not recovered: admission fails closed.
        if let Ok(mut slot) = cancel_slot().lock() {
            if slot
                .as_ref()
                .map(|active| Arc::ptr_eq(&active.owner, &self.owner))
                .unwrap_or(false)
            {
                *slot = None;
            }
        }
    }
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
    /// Signal cancellation of the active materialize request, if any.
    /// Returns true only when the signal was delivered; repeated calls return false.
    /// Admission remains held until the owning future finishes or is dropped.
    /// The request connection is dropped and runtime cancellation is attempted, but
    /// neither a dropped connection nor an HTTP acknowledgement proves backend
    /// compute has stopped or data has been erased.
    pub fn cancel_active() -> bool {
        match cancel_slot().lock() {
            Ok(mut slot) => slot
                .as_mut()
                .and_then(|active| active.cancel_tx.take())
                .map(|tx| tx.send(()).is_ok())
                .unwrap_or(false),
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
        let (_lease, cancel_rx) = MaterializeLease::reserve()?;
        let client = client(Duration::from_secs(95))?;
        let token = token()?;
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
        tokio::select! {
            r = request => r,
            cancellation = cancel_rx => {
                match cancellation {
                    Ok(()) => {
                        // Best effort only; keep admission through acknowledgement.
                        let _ = Self::abort_runtime_generation().await;
                        Err(anyhow::anyhow!("Generation cancelled by the user"))
                    }
                    Err(_) => Err(anyhow::anyhow!("Materialize cancellation channel closed")),
                }
            }
        }
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
