//! Bounded native IPC to the focused runtime. Credentials never reach JavaScript.
use anyhow::{anyhow, bail, Result};
use reqwest::{Client, Response, StatusCode};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::time::Duration;
const BASE: &str = "http://127.0.0.1:7437";
const RESPONSE_LIMIT: usize = 512 * 1024;

#[derive(Deserialize)]
struct MaterializeResponse {
    suggestion: String,
}
#[derive(Deserialize, Serialize)]
pub struct ModelInfo {
    name: String,
    size: u64,
}
#[derive(Deserialize, Serialize)]
pub struct ReadinessResponse {
    configured_model: String,
    ready: bool,
    models: Vec<ModelInfo>,
    message: String,
}
fn token() -> Result<String> {
    let value = std::env::var("AXIOM_API_TOKEN").map_err(|_| {
        anyhow!("IPC credential missing. Start both processes using the Axiom launcher.")
    })?;
    if value.len() != 64 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
        bail!("Invalid IPC credential. Restart both processes using the Axiom launcher.");
    }
    Ok(value)
}
fn client() -> Result<Client> {
    Ok(Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .connect_timeout(Duration::from_secs(2))
        .timeout(Duration::from_secs(95))
        .build()?)
}
fn status_message(status: StatusCode) -> &'static str {
    match status.as_u16() {
        401 | 403 => "Runtime authentication failed. Restart both processes using the Axiom launcher.",
        400 | 413 | 422 => "Input rejected. Provide at most 16000 characters of explicit text.",
        429 => "A generation is still running. Wait for it to finish before retrying.",
        502..=504 => "Local model unavailable, missing, invalid, or timed out. Check readiness and Ollama, then retry.",
        _ => "Unexpected runtime response. Check that the focused Axiom runtime is running.",
    }
}
async fn decode<T: DeserializeOwned>(mut response: Response) -> Result<T> {
    if !response.status().is_success() {
        bail!(status_message(response.status()));
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| anyhow!("Runtime response interrupted."))?
    {
        if bytes.len() + chunk.len() > RESPONSE_LIMIT {
            bail!("Runtime response exceeds safety limit.");
        }
        bytes.extend_from_slice(&chunk);
    }
    serde_json::from_slice(&bytes)
        .map_err(|_| anyhow!("Invalid runtime response. Verify the Axiom runtime version."))
}
pub struct PhantomBridge;
impl PhantomBridge {
    pub async fn materialize(context: String) -> Result<String> {
        if context.trim().is_empty() || context.chars().count() > 16000 {
            bail!("Provide between 1 and 16000 characters of explicit context.");
        }
        let response = client()?.post(format!("{BASE}/materialize")).bearer_auth(token()?)
            .json(&serde_json::json!({"context":context})).send().await
            .map_err(|_| anyhow!("Cannot reach the focused runtime or generation timed out. Start Axiom using the launcher."))?;
        Ok(decode::<MaterializeResponse>(response).await?.suggestion)
    }
    pub async fn readiness() -> Result<ReadinessResponse> {
        let response = client()?
            .get(format!("{BASE}/readiness"))
            .bearer_auth(token()?)
            .timeout(Duration::from_secs(5))
            .send()
            .await
            .map_err(|_| {
                anyhow!("Cannot reach the focused runtime. Start Axiom using the launcher.")
            })?;
        decode(response).await
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn actionable_status_without_backend_text() {
        assert!(status_message(StatusCode::UNAUTHORIZED).contains("authentication"));
        assert!(status_message(StatusCode::TOO_MANY_REQUESTS).contains("still running"));
        assert!(status_message(StatusCode::BAD_GATEWAY).contains("Ollama"));
        assert!(status_message(StatusCode::PAYLOAD_TOO_LARGE).contains("16000"));
    }
}
