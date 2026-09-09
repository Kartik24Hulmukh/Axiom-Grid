use axiom_grid::{api_security::ApiToken, router, AppState};
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Per-user OS-protected pairing; AXIOM_API_TOKEN is only an explicit CI/test override.
    let token = ApiToken::load_or_create_paired()?;
    if std::env::var_os("AXIOM_API_TOKEN").is_none() {
        eprintln!(
            "IPC pairing token at {} (mode 0600; never logged)",
            ApiToken::pairing_file_path()?.display()
        );
    }
    let model = std::env::var("AXIOM_MODEL").map_err(|_| {
        anyhow::anyhow!("Set AXIOM_MODEL to an installed Ollama model; no automatic downloads")
    })?;
    let state = AppState::local(model)?;
    let listener = tokio::net::TcpListener::bind("127.0.0.1:7437").await?;
    eprintln!("Axiom-Grid preview on 127.0.0.1:7437; explicit context; no automatic insertion");
    axum::serve(listener, router(state, token))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await?;
    Ok(())
}
