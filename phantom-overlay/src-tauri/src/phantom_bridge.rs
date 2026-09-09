//! PhantomBridge — connects the Tauri overlay to the phantom-core engine
//! via HTTP IPC on localhost:7437 (the phantom-core daemon port)

use anyhow::Result;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::{Mutex, OnceLock};
use tokio::sync::oneshot;

const PHANTOM_PORT: u16 = 7437;

#[derive(Serialize)]
struct MaterializeRequest {
    context: Option<String>,
}

#[derive(Deserialize)]
struct MaterializeResponse {
    suggestion: String,
    #[allow(dead_code)]
    word_count: usize,
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

pub struct PhantomBridge;

impl PhantomBridge {
    /// Cancel the in-flight materialize request, if any.
    /// Dropping the request future closes the local connection, which lets the
    /// runtime drop its in-flight Ollama request. Returns true when one was cancelled.
    pub fn cancel_active() -> bool {
        match cancel_slot().lock() {
            Ok(mut slot) => slot.take().map(|tx| tx.send(()).is_ok()).unwrap_or(false),
            Err(_) => false,
        }
    }

    /// Call phantom-core to generate a preview suggestion for explicit context.
    pub async fn materialize(context: String) -> Result<String> {
        let client = Client::builder()
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(std::time::Duration::from_secs(95))
            .build()?;
        let token = std::env::var("AXIOM_API_TOKEN")
            .map_err(|_| anyhow::anyhow!("AXIOM_API_TOKEN is not set"))?;
        let (cancel_tx, cancel_rx) = oneshot::channel::<()>();
        if let Ok(mut slot) = cancel_slot().lock() {
            *slot = Some(cancel_tx);
        }
        let request = async {
            let resp = client
                .post(format!("http://127.0.0.1:{PHANTOM_PORT}/materialize"))
                .bearer_auth(token)
                .json(&MaterializeRequest {
                    context: Some(context),
                })
                .send()
                .await?
                .error_for_status()?
                .json::<MaterializeResponse>()
                .await?;
            Ok::<String, anyhow::Error>(resp.suggestion)
        };
        let result = tokio::select! {
            r = request => r,
            _ = cancel_rx => Err(anyhow::anyhow!("Generation cancelled by the user")),
        };
        if let Ok(mut slot) = cancel_slot().lock() {
            slot.take();
        }
        result
    }

    pub async fn readiness() -> Result<ReadinessResponse> {
        let client = Client::builder()
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(std::time::Duration::from_secs(3))
            .build()?;
        Ok(client
            .get(format!("http://127.0.0.1:{PHANTOM_PORT}/readiness"))
            .bearer_auth(std::env::var("AXIOM_API_TOKEN")
                .map_err(|_| anyhow::anyhow!("AXIOM_API_TOKEN is not set"))?)
            .send()
            .await?
            .error_for_status()?
            .json::<ReadinessResponse>()
            .await?)
    }

    /// Ping phantom-core to check if it's running
    #[allow(dead_code)]
    pub async fn ping() -> bool {
        let client = match Client::builder().no_proxy().redirect(reqwest::redirect::Policy::none()).build() { Ok(c) => c, Err(_) => return false };
        client
            .get(format!("http://127.0.0.1:{PHANTOM_PORT}/health"))
            .timeout(std::time::Duration::from_secs(1))
            .send()
            .await
            .map(|r| r.status().is_success()).unwrap_or(false)
    }
}
