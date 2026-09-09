//! PhantomBridge — connects the Tauri overlay to the phantom-core engine
//! via HTTP IPC on localhost:7437 (the phantom-core daemon port)

use anyhow::Result;
use reqwest::Client;
use serde::{Deserialize, Serialize};

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

pub struct PhantomBridge;

impl PhantomBridge {
    /// Call phantom-core to read UIA, get AI suggestion, and ghost-type it
    pub async fn materialize(context: String) -> Result<String> {
        let client = Client::builder()
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(std::time::Duration::from_secs(95))
            .build()?;

        let resp = client
            .post(format!("http://127.0.0.1:{PHANTOM_PORT}/materialize"))
            .bearer_auth(std::env::var("AXIOM_API_TOKEN")
                .map_err(|_| anyhow::anyhow!("AXIOM_API_TOKEN is not set"))?)
            .json(&MaterializeRequest { context: Some(context) })
            .send()
            .await?
            .error_for_status()?
            .json::<MaterializeResponse>()
            .await?;

        Ok(resp.suggestion)
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
