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
    let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel();
    let server = axum::serve(listener, router(state, token)).with_graceful_shutdown(async {
        let _ = shutdown_rx.await;
    });
    // A separate task owns connections so a stalled/partial HTTP body cannot
    // prevent process shutdown forever. Runtime teardown closes any remainder.
    let mut server = tokio::spawn(async move { server.await });
    tokio::select! {
        result = &mut server => { result??; return Ok(()); }
        result = shutdown_signal() => { result?; }
    }
    let _ = shutdown_tx.send(());
    match tokio::time::timeout(std::time::Duration::from_secs(5), &mut server).await {
        Ok(result) => {
            result??;
        }
        Err(_) => {
            eprintln!("Shutdown drain deadline reached; closing remaining connections");
            server.abort();
            let _ = server.await;
        }
    }
    Ok(())
}

async fn shutdown_signal() -> std::io::Result<()> {
    #[cfg(unix)]
    {
        use tokio::signal::unix::{signal, SignalKind};
        let mut terminate = signal(SignalKind::terminate())?;
        tokio::select! {
            result = tokio::signal::ctrl_c() => result,
            _ = terminate.recv() => Ok(()),
        }
    }
    #[cfg(not(unix))]
    tokio::signal::ctrl_c().await
}
