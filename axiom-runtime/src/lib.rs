//! Focused preview runtime, without legacy desktop dependencies.
#[path = "../../phantom-core/src/api_security.rs"]
pub mod api_security;
#[path = "../../phantom-core/src/crdt.rs"]
pub mod crdt;
#[path = "../../phantom-core/src/ghost_buffer.rs"]
pub mod ghost_buffer;
#[path = "../../phantom-core/src/ghost_session.rs"]
pub mod ghost_session;
#[path = "../../phantom-core/src/ollama_bootstrap.rs"]
pub mod ollama_bootstrap;
pub mod ai {
    pub const KAIRO_SYSTEM_PROMPT: &str =
        "Provide the requested writing assistance. Return only the suggested text.";
}
use axum::{
    extract::{DefaultBodyLimit, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::{sync::Arc, time::Duration};
use tokio::sync::Semaphore;
#[derive(Clone)]
pub struct AppState {
    client: reqwest::Client,
    model: String,
    inference_url: String,
    tags_url: String,
    slots: Arc<Semaphore>,
}
impl AppState {
    pub fn local(model: String) -> anyhow::Result<Self> {
        anyhow::ensure!(
            !model.trim().is_empty() && model.len() <= 256,
            "Invalid model name"
        );
        Ok(Self {
            client: reqwest::Client::builder()
                .no_proxy()
                .redirect(reqwest::redirect::Policy::none())
                .connect_timeout(Duration::from_secs(2))
                .timeout(Duration::from_secs(90))
                .build()?,
            model,
            inference_url: "http://127.0.0.1:11434/api/generate".into(),
            tags_url: "http://127.0.0.1:11434/api/tags".into(),
            slots: Arc::new(Semaphore::new(1)),
        })
    }
    /// Test harness can target a loopback mock, never external inference.
    pub fn with_loopback_port(mut self, port: u16) -> Self {
        self.inference_url = format!("http://127.0.0.1:{port}/api/generate");
        self.tags_url = format!("http://127.0.0.1:{port}/api/tags");
        self
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PreviewRequest {
    pub context: String,
}
#[derive(Serialize, Deserialize, Debug)]
pub struct PreviewResponse {
    pub suggestion: String,
    pub word_count: usize,
    pub char_count: usize,
}
#[derive(Deserialize)]
struct OllamaResponse {
    response: String,
    done: bool,
}
type ApiError = (StatusCode, &'static str);
#[derive(Deserialize)]
struct OllamaTags {
    models: Vec<OllamaModel>,
}
#[derive(Deserialize)]
struct OllamaModel {
    name: String,
    #[serde(default)]
    size: u64,
    #[serde(default)]
    digest: String,
}
#[derive(Serialize, Deserialize, Debug)]
pub struct ModelInfo {
    pub name: String,
    pub size: u64,
    pub digest: String,
}
#[derive(Serialize, Deserialize, Debug)]
pub struct ReadinessResponse {
    pub ready: bool,
    pub configured_model: String,
    pub installed_models: Vec<ModelInfo>,
}
async fn readiness(State(state): State<AppState>) -> Result<Json<ReadinessResponse>, ApiError> {
    let response = state
        .client
        .get(&state.tags_url)
        .send()
        .await
        .map_err(|_| {
            (
                StatusCode::SERVICE_UNAVAILABLE,
                "Local model service unavailable; start Ollama",
            )
        })?
        .error_for_status()
        .map_err(|_| (StatusCode::BAD_GATEWAY, "Local model inventory unavailable"))?;
    let tags: OllamaTags = response
        .json()
        .await
        .map_err(|_| (StatusCode::BAD_GATEWAY, "Invalid local model inventory"))?;
    let ready = tags.models.iter().any(|m| m.name == state.model);
    let installed_models = tags
        .models
        .into_iter()
        .map(|m| ModelInfo {
            name: m.name,
            size: m.size,
            digest: m.digest,
        })
        .collect();
    Ok(Json(ReadinessResponse {
        ready,
        configured_model: state.model.clone(),
        installed_models,
    }))
}
async fn preview(
    State(state): State<AppState>,
    Json(input): Json<PreviewRequest>,
) -> Result<Json<PreviewResponse>, ApiError> {
    if input.context.trim().is_empty() || input.context.chars().count() > 16000 {
        return Err((
            StatusCode::BAD_REQUEST,
            "Provide between 1 and 16000 characters of explicit context",
        ));
    }
    let _permit = state.slots.try_acquire().map_err(|_| {
        (
            StatusCode::TOO_MANY_REQUESTS,
            "Generation already running; retry after it finishes",
        )
    })?;
    let mut response = state.client.post(&state.inference_url).json(&serde_json::json!({
        "model": state.model, "prompt": input.context, "system": ai::KAIRO_SYSTEM_PROMPT,
        "stream": false, "options": {"num_predict": 2048}
    })).send().await.map_err(|_| (StatusCode::BAD_GATEWAY, "Local model unavailable or timed out; start Ollama and install the configured model"))?
        .error_for_status().map_err(|_| (StatusCode::BAD_GATEWAY, "Local model rejected generation; verify the installed model"))?;
    let mut bytes = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| (StatusCode::BAD_GATEWAY, "Local model response interrupted"))?
    {
        if bytes.len() + chunk.len() > 256 * 1024 {
            return Err((
                StatusCode::BAD_GATEWAY,
                "Local model output exceeds safety limit",
            ));
        }
        bytes.extend_from_slice(&chunk);
    }
    let output: OllamaResponse = serde_json::from_slice(&bytes)
        .map_err(|_| (StatusCode::BAD_GATEWAY, "Invalid local model response"))?;
    if !output.done || output.response.trim().is_empty() {
        return Err((
            StatusCode::BAD_GATEWAY,
            "Local model returned an incomplete or empty preview",
        ));
    }
    Ok(Json(PreviewResponse {
        word_count: output.response.split_whitespace().count(),
        char_count: output.response.chars().count(),
        suggestion: output.response,
    }))
}
pub fn router(state: AppState, token: api_security::ApiToken) -> Router {
    let protected = Router::new()
        .route("/materialize", post(preview))
        .route("/readiness", get(readiness))
        .layer(DefaultBodyLimit::max(64 * 1024))
        .route_layer(axum::middleware::from_fn_with_state(
            token,
            api_security::authorize,
        ));
    Router::new().route("/health", get(|| async { Json(serde_json::json!({"status":"ok", "product":"Axiom-Grid", "mode":"preview-only", "version":env!("CARGO_PKG_VERSION")})) }))
        .merge(protected).with_state(state)
}
