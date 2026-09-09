//! Ollama Bootstrap — P0-A2
//! Detection is local-only; downloads require explicit opt-in and never run offline.

use tokio::time::Duration;

pub struct OllamaBootstrap;

impl OllamaBootstrap {
    /// Returns true if Ollama API is reachable.
    pub async fn is_running() -> bool {
        local_client_builder()
            .build()
            .expect("local HTTP client configuration")
            .get("http://127.0.0.1:11434/api/tags")
            .timeout(Duration::from_secs(2))
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false)
    }

    /// Pull a model in the background. Non-blocking — fires and forgets.
    pub async fn ensure_model(model: &str) -> anyhow::Result<()> {
        anyhow::ensure!(
            download_allowed(
                std::env::var("KAIRO_OFFLINE").ok().as_deref(),
                std::env::var("AXIOM_ALLOW_MODEL_DOWNLOAD").ok().as_deref()
            ),
            "Model downloads disabled: explicit consent required; offline mode always wins"
        );
        anyhow::ensure!(
            !model.trim().is_empty() && model.len() <= 256,
            "Invalid model name"
        );
        if Self::has_model(model).await {
            return Ok(());
        }
        tracing::info!("User-approved model download requested");
        let client = local_client_builder()
            .build()
            .expect("local HTTP client configuration");
        let body = serde_json::json!({"name": model, "stream": false});
        let resp = client
            .post("http://127.0.0.1:11434/api/pull")
            .json(&body)
            .timeout(Duration::from_secs(600))
            .send()
            .await?;
        resp.error_for_status()?;
        anyhow::ensure!(
            Self::has_model(model).await,
            "Downloaded model not found in local inventory"
        );
        Ok(())
    }

    /// Returns true if the given model is available locally in Ollama.
    pub async fn has_model(model: &str) -> bool {
        let client = match local_client_builder().build() {
            Ok(c) => c,
            Err(_) => return false,
        };
        let resp = match client
            .get("http://127.0.0.1:11434/api/tags")
            .timeout(Duration::from_secs(2))
            .send()
            .await
        {
            Ok(r) => r,
            Err(_) => return false,
        };
        if !resp.status().is_success() {
            return false;
        }

        #[derive(serde::Deserialize)]
        struct OllamaTags {
            models: Vec<OllamaModel>,
        }
        #[derive(serde::Deserialize)]
        struct OllamaModel {
            name: String,
        }

        if let Ok(tags) = resp.json::<OllamaTags>().await {
            tags.models.iter().any(|m| model_matches(model, &m.name))
        } else {
            false
        }
    }

    /// Detect locally without silently downloading model weights.
    pub async fn bootstrap(default_model: &str) {
        if !Self::is_running().await {
            tracing::warn!(
                "Ollama not detected on 127.0.0.1:11434; start Ollama before generating"
            );
            return;
        }
        if Self::has_model(default_model).await {
            return;
        }
        if !download_allowed(
            std::env::var("KAIRO_OFFLINE").ok().as_deref(),
            std::env::var("AXIOM_ALLOW_MODEL_DOWNLOAD").ok().as_deref(),
        ) {
            tracing::warn!("Configured model missing; install it explicitly before offline use");
            return;
        }
        let model = default_model.to_string();
        tokio::spawn(async move {
            if let Err(error) = Self::ensure_model(&model).await {
                tracing::warn!("Approved model setup failed: {}", error);
            }
        });
    }
}

fn local_client_builder() -> reqwest::ClientBuilder {
    reqwest::Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .connect_timeout(Duration::from_secs(2))
}

pub fn download_allowed(offline: Option<&str>, consent: Option<&str>) -> bool {
    offline != Some("1") && consent == Some("1")
}

pub fn model_matches(requested: &str, installed: &str) -> bool {
    if requested.is_empty() {
        return false;
    }
    if requested == installed {
        return true;
    }
    // Only the implicit latest tag is equivalent; never prefix-match sizes/tags.
    !requested.contains(':') && installed == format!("{requested}:latest")
}
