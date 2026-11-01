//! Exact production bridge, exercised without Tauri or real inference.
//! Loopback mocks establish client lifecycle contracts, not backend termination.
#[allow(dead_code)]
#[path = "../../phantom-overlay/src-tauri/src/phantom_bridge.rs"]
mod bridge;

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use bridge::PhantomBridge;
use serde_json::{json, Value};
use std::{
    ffi::OsString,
    sync::{
        atomic::{AtomicUsize, Ordering},
        Arc, Mutex,
    },
    time::Duration,
};
use tokio::sync::{Mutex as AsyncMutex, Notify};

static ENVIRONMENT: AsyncMutex<()> = AsyncMutex::const_new(());
const WAIT: Duration = Duration::from_secs(5);

struct Environment(Vec<(&'static str, Option<OsString>)>);
impl Environment {
    fn configure(port: u16) -> Self {
        let keys = ["AXIOM_RUNTIME_PORT", "AXIOM_API_TOKEN"];
        let old = keys
            .into_iter()
            .map(|key| (key, std::env::var_os(key)))
            .collect();
        std::env::set_var("AXIOM_RUNTIME_PORT", port.to_string());
        // Synthetic public fixture; never a real credential.
        std::env::set_var("AXIOM_API_TOKEN", "b".repeat(64));
        Self(old)
    }
}
impl Drop for Environment {
    fn drop(&mut self) {
        for (key, value) in &self.0 {
            match value {
                Some(value) => std::env::set_var(key, value),
                None => std::env::remove_var(key),
            }
        }
    }
}

#[derive(Default)]
struct Observed {
    previews: Vec<Value>,
    authorizations: Vec<String>,
    cancellations: usize,
    readiness: usize,
}
#[derive(Clone, Default)]
struct Mock {
    seen: Arc<Mutex<Observed>>,
    preview_entered: Arc<Notify>,
    preview_release: Arc<Notify>,
    cancel_entered: Arc<Notify>,
    cancel_release: Arc<Notify>,
    cancel_mode: Arc<AtomicUsize>,
}
async fn preview(
    State(state): State<Mock>,
    headers: HeaderMap,
    Json(input): Json<Value>,
) -> Response {
    {
        let mut seen = state.seen.lock().unwrap();
        seen.previews.push(input.clone());
        seen.authorizations
            .push(headers["authorization"].to_str().unwrap().to_owned());
    }
    match input["context"].as_str().unwrap() {
        "hold-first" => {
            state.preview_entered.notify_one();
            state.preview_release.notified().await;
        }
        "http-fail" => return StatusCode::SERVICE_UNAVAILABLE.into_response(),
        "invalid-json" => return (StatusCode::OK, "not-json").into_response(),
        _ => {}
    }
    Json(json!({"suggestion":"Reviewed 🌍", "word_count":2, "char_count":10})).into_response()
}
async fn cancel(State(state): State<Mock>) -> Response {
    state.seen.lock().unwrap().cancellations += 1;
    state.cancel_entered.notify_one();
    state.cancel_release.notified().await;
    match state.cancel_mode.load(Ordering::SeqCst) {
        1 => Json(json!({"cancelled":false})).into_response(),
        2 => StatusCode::SERVICE_UNAVAILABLE.into_response(),
        3 => (StatusCode::OK, "not-json").into_response(),
        _ => Json(json!({"cancelled":true})).into_response(),
    }
}
async fn readiness(State(state): State<Mock>) -> Json<Value> {
    state.seen.lock().unwrap().readiness += 1;
    Json(
        json!({"ready":true,"configured_model":"fixture","expected_digest":"a".repeat(64),
        "identity_check_scope":"reported-only","installed_models":[]}),
    )
}
struct Server(tokio::task::JoinHandle<()>);
impl Drop for Server {
    fn drop(&mut self) {
        self.0.abort();
    }
}
async fn fixture() -> (Mock, Server, Environment) {
    let state = Mock::default();
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let env = Environment::configure(listener.local_addr().unwrap().port());
    let router = Router::new()
        .route("/materialize", post(preview))
        .route("/cancel", post(cancel))
        .route("/readiness", get(readiness))
        .with_state(state.clone());
    let server = Server(tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    }));
    (state, server, env)
}
async fn notified(signal: &Notify) {
    tokio::time::timeout(WAIT, signal.notified())
        .await
        .expect("mock barrier must be reached");
}
async fn generate(context: &str) -> anyhow::Result<String> {
    tokio::time::timeout(WAIT, PhantomBridge::materialize(context.into()))
        .await
        .expect("bridge must settle")
}

#[tokio::test]
async fn explicit_unicode_roundtrip_and_idle_cancel() {
    let _serial = ENVIRONMENT.lock().await;
    let (state, _server, _env) = fixture().await;
    assert!(!PhantomBridge::cancel_active());
    assert_eq!(generate("Rewrite: café 🌍").await.unwrap(), "Reviewed 🌍");
    assert!(!PhantomBridge::cancel_active());
    let seen = state.seen.lock().unwrap();
    assert_eq!(seen.previews, vec![json!({"context":"Rewrite: café 🌍"})]);
    assert_eq!(
        seen.authorizations,
        vec![format!("Bearer {}", "b".repeat(64))]
    );
    assert_eq!(seen.cancellations, 0);
}

#[tokio::test]
async fn overlap_cannot_replace_owner_or_bypass_cancel_acknowledgement() {
    let _serial = ENVIRONMENT.lock().await;
    let (state, _server, _env) = fixture().await;
    let first = tokio::spawn(PhantomBridge::materialize("hold-first".into()));
    notified(&state.preview_entered).await;
    let rejected = generate("must-not-be-sent").await;
    assert!(rejected.is_err(), "second native call must fail closed");
    assert_eq!(state.seen.lock().unwrap().previews.len(), 1);
    assert_eq!(state.seen.lock().unwrap().cancellations, 0);
    assert!(
        PhantomBridge::cancel_active(),
        "first caller still owns cancellation"
    );
    assert!(!PhantomBridge::cancel_active(), "signal is one-shot");
    notified(&state.cancel_entered).await;
    assert!(generate("blocked-until-cancel-settles").await.is_err());
    assert_eq!(state.seen.lock().unwrap().previews.len(), 1);
    assert!(!first.is_finished(), "cancel attempt must still be pending");
    state.cancel_release.notify_one();
    let result = tokio::time::timeout(WAIT, first).await.unwrap().unwrap();
    assert!(result.is_err());
    assert!(!PhantomBridge::cancel_active());
    state.preview_release.notify_one(); // cleanup; not proof model computation stopped
    assert_eq!(generate("next-owner").await.unwrap(), "Reviewed 🌍");
    let seen = state.seen.lock().unwrap();
    assert_eq!(seen.previews.len(), 2);
    assert_eq!(seen.previews[1], json!({"context":"next-owner"}));
    assert_eq!(seen.cancellations, 1);
}

#[tokio::test]
async fn aborted_call_releases_local_ownership_without_claiming_remote_stop() {
    let _serial = ENVIRONMENT.lock().await;
    let (state, _server, _env) = fixture().await;
    let first = tokio::spawn(PhantomBridge::materialize("hold-first".into()));
    notified(&state.preview_entered).await;
    first.abort();
    assert!(first.await.unwrap_err().is_cancelled());
    assert!(
        !PhantomBridge::cancel_active(),
        "dropped future must not leave stale sender"
    );
    assert_eq!(generate("after-task-abort").await.unwrap(), "Reviewed 🌍");
    state.preview_release.notify_one();
    let seen = state.seen.lock().unwrap();
    assert_eq!(seen.previews.len(), 2);
    assert_eq!(
        seen.cancellations, 0,
        "Drop cannot attest or asynchronously stop backend work"
    );
}

#[tokio::test]
async fn token_failure_releases_admission_before_retry() {
    let _serial = ENVIRONMENT.lock().await;
    let (state, _server, _env) = fixture().await;
    std::env::set_var("AXIOM_API_TOKEN", "invalid-public-fixture");
    assert!(generate("not-transmitted").await.is_err());
    assert!(state.seen.lock().unwrap().previews.is_empty());
    assert!(!PhantomBridge::cancel_active());
    std::env::set_var("AXIOM_API_TOKEN", "b".repeat(64));
    assert_eq!(generate("retry").await.unwrap(), "Reviewed 🌍");
}

#[tokio::test]
async fn http_and_decode_errors_release_admission() {
    let _serial = ENVIRONMENT.lock().await;
    let (state, _server, _env) = fixture().await;
    for context in ["http-fail", "invalid-json"] {
        assert!(generate(context).await.is_err());
        assert!(!PhantomBridge::cancel_active());
        assert_eq!(generate("recovered").await.unwrap(), "Reviewed 🌍");
    }
    assert_eq!(state.seen.lock().unwrap().previews.len(), 4);
    assert_eq!(state.seen.lock().unwrap().cancellations, 0);
}

#[tokio::test]
async fn readiness_does_not_replace_an_active_generation_owner() {
    let _serial = ENVIRONMENT.lock().await;
    let (state, _server, _env) = fixture().await;
    let first = tokio::spawn(PhantomBridge::materialize("hold-first".into()));
    notified(&state.preview_entered).await;
    let ready = tokio::time::timeout(WAIT, PhantomBridge::readiness())
        .await
        .unwrap()
        .unwrap();
    assert!(ready.ready);
    assert_eq!(ready.identity_check_scope, "reported-only");
    assert!(PhantomBridge::cancel_active());
    notified(&state.cancel_entered).await;
    state.cancel_release.notify_one();
    assert!(tokio::time::timeout(WAIT, first)
        .await
        .unwrap()
        .unwrap()
        .is_err());
    state.preview_release.notify_one();
    assert_eq!(state.seen.lock().unwrap().readiness, 1);
    assert_eq!(state.seen.lock().unwrap().cancellations, 1);
}

#[tokio::test]
async fn task_drop_during_cancel_acknowledgement_releases_only_local_lease() {
    let _serial = ENVIRONMENT.lock().await;
    let (state, _server, _env) = fixture().await;
    let first = tokio::spawn(PhantomBridge::materialize("hold-first".into()));
    notified(&state.preview_entered).await;
    assert!(PhantomBridge::cancel_active());
    notified(&state.cancel_entered).await;
    assert!(generate("still-busy").await.is_err());
    first.abort();
    assert!(first.await.unwrap_err().is_cancelled());
    assert!(!PhantomBridge::cancel_active());
    assert_eq!(
        generate("after-cancel-task-abort").await.unwrap(),
        "Reviewed 🌍"
    );
    state.cancel_release.notify_one();
    state.preview_release.notify_one();
    let seen = state.seen.lock().unwrap();
    assert_eq!(seen.previews.len(), 2);
    assert_eq!(seen.cancellations, 1);
}

#[tokio::test]
async fn false_failed_and_malformed_cancel_acknowledgements_release_local_admission() {
    let _serial = ENVIRONMENT.lock().await;
    for mode in [1, 2, 3] {
        let (state, _server, _env) = fixture().await;
        state.cancel_mode.store(mode, Ordering::SeqCst);
        let first = tokio::spawn(PhantomBridge::materialize("hold-first".into()));
        notified(&state.preview_entered).await;
        assert!(PhantomBridge::cancel_active());
        notified(&state.cancel_entered).await;
        assert!(generate("still-busy").await.is_err());
        assert!(!first.is_finished(), "cancel attempt must still be pending");
        assert_eq!(state.seen.lock().unwrap().previews.len(), 1);
        state.cancel_release.notify_one();
        assert!(tokio::time::timeout(WAIT, first)
            .await
            .unwrap()
            .unwrap()
            .is_err());
        assert!(!PhantomBridge::cancel_active());
        assert_eq!(
            generate("after-failed-cancel").await.unwrap(),
            "Reviewed 🌍"
        );
        state.preview_release.notify_one();
        assert_eq!(state.seen.lock().unwrap().previews.len(), 2);
        assert_eq!(state.seen.lock().unwrap().cancellations, 1);
    }
}
