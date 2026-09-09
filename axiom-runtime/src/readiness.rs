//! Inventory checks are bounded and authenticated, and never pull or load a model.
use super::{ApiError, AppState};
use axum::{extract::State, http::StatusCode, Json};
use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Deserialize, Serialize, Debug)]
pub struct ModelInfo {
    pub name: String,
    pub size: u64,
}
#[derive(Deserialize)]
struct Inventory {
    models: Vec<ModelInfo>,
}
#[derive(Deserialize, Serialize, Debug)]
pub struct ReadinessResponse {
    pub configured_model: String,
    pub ready: bool,
    pub models: Vec<ModelInfo>,
    pub message: String,
}
pub async fn readiness(State(state): State<AppState>) -> Result<Json<ReadinessResponse>, ApiError> {
    let url = state.inference_url.replace("/api/generate", "/api/tags");
    let mut response = state
        .client
        .get(url)
        .timeout(Duration::from_secs(3))
        .send()
        .await
        .map_err(|_| {
            (
                StatusCode::BAD_GATEWAY,
                "Cannot reach local Ollama. Start Ollama on 127.0.0.1:11434 and retry.",
            )
        })?;
    if !response.status().is_success() {
        return Err((
            StatusCode::BAD_GATEWAY,
            "Ollama inventory request failed. Check the local daemon.",
        ));
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| {
        (
            StatusCode::BAD_GATEWAY,
            "Ollama inventory response interrupted.",
        )
    })? {
        if bytes.len() + chunk.len() > 256 * 1024 {
            return Err((
                StatusCode::BAD_GATEWAY,
                "Ollama inventory exceeds safety limit.",
            ));
        }
        bytes.extend_from_slice(&chunk);
    }
    let inventory: Inventory = serde_json::from_slice(&bytes).map_err(|_| {
        (
            StatusCode::BAD_GATEWAY,
            "Invalid Ollama inventory response.",
        )
    })?;
    if inventory.models.len() > 1024
        || inventory.models.iter().any(|m| {
            m.name.len() > 256 || m.name.trim().is_empty() || m.name.chars().any(char::is_control)
        })
    {
        return Err((StatusCode::BAD_GATEWAY, "Invalid Ollama model inventory."));
    }
    let ready = inventory.models.iter().any(|m| m.name == state.model);
    let message = if ready {
        "Configured model is installed. Inference and quality are not yet verified."
    } else {
        "Configured model is not installed. Install it yourself in Ollama, or restart the runtime with an exact installed tag. No download was started."
    };
    Ok(Json(ReadinessResponse {
        configured_model: state.model,
        ready,
        models: inventory.models,
        message: message.into(),
    }))
}
