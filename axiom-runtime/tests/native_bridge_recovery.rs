//! Exact bridge recovery contracts with synthetic loopback responses only.
#[allow(dead_code)]
#[path = "../../phantom-overlay/src-tauri/src/phantom_bridge.rs"]
mod bridge;

use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
use bridge::PhantomBridge;
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
const MARKER: &str = "PRIVATE_CONTEXT_PATH_TOKEN_SENTINEL";
const SUCCESS: &str = r#"{"suggestion":"reviewed","word_count":1,"ready":true,"configured_model":"fixture","expected_digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","identity_check_scope":"reported-only","installed_models":[]}"#;
struct Environment(Vec<(&'static str, Option<OsString>)>);
impl Environment {
    fn new(port: u16) -> Self {
        let keys = [
            "AXIOM_RUNTIME_PORT",
            "AXIOM_API_TOKEN",
            "AXIOM_PAIRING_FILE",
            "HOME",
            "XDG_RUNTIME_DIR",
            "XDG_CONFIG_HOME",
        ];
        let old = keys.into_iter().map(|k| (k, std::env::var_os(k))).collect();
        std::env::set_var("AXIOM_RUNTIME_PORT", port.to_string());
        std::env::set_var("AXIOM_API_TOKEN", "b".repeat(64));
        Self(old)
    }
}
impl Drop for Environment {
    fn drop(&mut self) {
        for (k, v) in &self.0 {
            match v {
                Some(v) => std::env::set_var(k, v),
                None => std::env::remove_var(k),
            }
        }
    }
}
#[derive(Clone)]
struct Mock {
    response: Arc<Mutex<(u16, String)>>,
    calls: Arc<AtomicUsize>,
    hold: Arc<Notify>,
    blocked: Arc<AtomicUsize>,
}
async fn respond(State(s): State<Mock>) -> Response {
    s.calls.fetch_add(1, Ordering::SeqCst);
    if s.blocked.load(Ordering::SeqCst) != 0 {
        s.hold.notified().await;
    }
    let (status, body) = s.response.lock().unwrap().clone();
    (StatusCode::from_u16(status).unwrap(), body).into_response()
}
struct Server(tokio::task::JoinHandle<()>);
impl Drop for Server {
    fn drop(&mut self) {
        self.0.abort();
    }
}
async fn fixture() -> (Mock, Server, Environment) {
    let s = Mock {
        response: Arc::new(Mutex::new((200, SUCCESS.into()))),
        calls: Arc::new(AtomicUsize::new(0)),
        hold: Arc::new(Notify::new()),
        blocked: Arc::new(AtomicUsize::new(0)),
    };
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let env = Environment::new(listener.local_addr().unwrap().port());
    let app = Router::new()
        .route("/materialize", post(respond))
        .route("/readiness", get(respond))
        .with_state(s.clone());
    let task = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });
    (s, Server(task), env)
}
fn diagnostic(error: anyhow::Error, code: &str) {
    let forms = [
        format!("{error}"),
        format!("{error:#}"),
        format!("{error:?}"),
        error
            .chain()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join("\n"),
    ];
    assert!(forms[0].contains(code), "{code}: {}", forms[0]);
    for text in forms {
        for forbidden in [MARKER, "http://", "127.0.0.1", "/tmp/", "bbbbbbbbbbbbbbbb"] {
            assert!(!text.contains(forbidden), "reflected {forbidden}: {text}");
        }
    }
}
#[tokio::test]
async fn non_success_statuses_reject_success_shaped_bodies_and_recover() {
    let _lock = ENVIRONMENT.lock().await;
    let (s, _server, _env) = fixture().await;
    for (status, code) in [
        (401, "PAIRING_AUTH_FAILED"),
        (403, "POLICY_DENIED"),
        (429, "RUNTIME_BUSY"),
        (499, "CANCEL_REQUESTED"),
        (502, "BACKEND_RESPONSE_INVALID"),
        (500, "RUNTIME_SERVER_ERROR"),
        (302, "HTTP_UNEXPECTED_STATUS"),
        (307, "HTTP_UNEXPECTED_STATUS"),
    ] {
        *s.response.lock().unwrap() = (status, SUCCESS.replace("reviewed", MARKER));
        diagnostic(
            PhantomBridge::materialize(MARKER.into())
                .await
                .err()
                .unwrap(),
            code,
        );
        diagnostic(PhantomBridge::readiness().await.err().unwrap(), code);
        *s.response.lock().unwrap() = (200, SUCCESS.into());
        assert_eq!(
            PhantomBridge::materialize("explicit recovery".into())
                .await
                .unwrap(),
            "reviewed"
        );
    }
    assert_eq!(s.calls.load(Ordering::SeqCst), 24);
}
#[tokio::test]
async fn operation_specific_errors_do_not_invent_backend_identity_cause() {
    let _lock = ENVIRONMENT.lock().await;
    let (s, _server, _env) = fixture().await;
    for status in [400, 413] {
        *s.response.lock().unwrap() = (status, MARKER.into());
        diagnostic(
            PhantomBridge::materialize(MARKER.into())
                .await
                .err()
                .unwrap(),
            "PREVIEW_INPUT_REJECTED",
        );
        diagnostic(
            PhantomBridge::readiness().await.err().unwrap(),
            "HTTP_UNEXPECTED_STATUS",
        );
    }
    *s.response.lock().unwrap() = (503, MARKER.into());
    let error = PhantomBridge::materialize(MARKER.into())
        .await
        .err()
        .unwrap();
    assert!(error.to_string().contains("exact cause is not established"));
    diagnostic(error, "PREVIEW_UNAVAILABLE");
    diagnostic(
        PhantomBridge::readiness().await.err().unwrap(),
        "READINESS_UNAVAILABLE",
    );
}
#[tokio::test]
async fn malformed_success_responses_have_no_decode_source_leak() {
    let _lock = ENVIRONMENT.lock().await;
    let (s, _server, _env) = fixture().await;
    for body in [
        MARKER.to_string(),
        format!(r#"{{"suggestion":{{"{MARKER}":1}},"word_count":1}}"#),
        format!(r#"{{"ready":"{MARKER}"}}"#),
    ] {
        *s.response.lock().unwrap() = (200, body);
        diagnostic(
            PhantomBridge::materialize(MARKER.into())
                .await
                .err()
                .unwrap(),
            "RESPONSE_DECODE_FAILED",
        );
        diagnostic(
            PhantomBridge::readiness().await.err().unwrap(),
            "RESPONSE_DECODE_FAILED",
        );
    }
    *s.response.lock().unwrap() = (200, SUCCESS.into());
    assert!(PhantomBridge::readiness().await.unwrap().ready);
    assert_eq!(
        PhantomBridge::materialize("recovery".into()).await.unwrap(),
        "reviewed"
    );
}
#[tokio::test]
async fn connection_failure_is_sanitized_and_releases_preview_slot() {
    let _lock = ENVIRONMENT.lock().await;
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let _env = Environment::new(listener.local_addr().unwrap().port());
    drop(listener);
    diagnostic(
        PhantomBridge::materialize(MARKER.into())
            .await
            .err()
            .unwrap(),
        "TRANSPORT_CONNECTION_FAILED",
    );
    diagnostic(
        PhantomBridge::readiness().await.err().unwrap(),
        "TRANSPORT_CONNECTION_FAILED",
    );
    let (_s, _server, _second_env) = fixture().await;
    assert_eq!(
        PhantomBridge::materialize("recovered".into())
            .await
            .unwrap(),
        "reviewed"
    );
}
#[tokio::test]
async fn readiness_timeout_is_sanitized_not_a_backend_stop_claim() {
    let _lock = ENVIRONMENT.lock().await;
    let (s, _server, _env) = fixture().await;
    s.blocked.store(1, Ordering::SeqCst);
    let result = tokio::time::timeout(Duration::from_secs(7), PhantomBridge::readiness())
        .await
        .unwrap();
    diagnostic(result.err().unwrap(), "TRANSPORT_TIMEOUT");
    assert_eq!(s.calls.load(Ordering::SeqCst), 1);
    s.blocked.store(0, Ordering::SeqCst);
    s.hold.notify_one();
    assert!(PhantomBridge::readiness().await.unwrap().ready);
}
#[cfg(unix)]
struct PairingFixture(std::path::PathBuf);
#[cfg(unix)]
impl PairingFixture {
    fn new() -> Self {
        use std::os::unix::fs::PermissionsExt;
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let path = std::env::temp_dir().join(format!(
            "axiom-recovery-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::SeqCst)
        ));
        std::fs::create_dir(&path).unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
        let token = path.join(MARKER);
        std::fs::write(&token, "b".repeat(64)).unwrap();
        std::fs::set_permissions(&token, std::fs::Permissions::from_mode(0o600)).unwrap();
        std::env::set_var("AXIOM_PAIRING_FILE", &token);
        Self(path)
    }
    fn token(&self) -> std::path::PathBuf {
        self.0.join(MARKER)
    }
}
#[cfg(unix)]
impl Drop for PairingFixture {
    fn drop(&mut self) {
        std::fs::remove_dir_all(&self.0).unwrap();
    }
}
#[cfg(unix)]
#[tokio::test]
async fn explicit_invalid_overrides_never_fall_back_to_valid_storage() {
    use std::os::unix::ffi::OsStringExt;
    let _lock = ENVIRONMENT.lock().await;
    let (s, _server, _env) = fixture().await;
    let pairing = PairingFixture::new();
    for value in [
        OsString::from(""),
        OsString::from(MARKER),
        OsString::from("z".repeat(64)),
        OsString::from_vec(vec![0xff]),
    ] {
        std::env::set_var("AXIOM_API_TOKEN", value);
        diagnostic(
            PhantomBridge::materialize(MARKER.into())
                .await
                .err()
                .unwrap(),
            "PAIRING_OVERRIDE_INVALID",
        );
        diagnostic(
            PhantomBridge::readiness().await.err().unwrap(),
            "PAIRING_OVERRIDE_INVALID",
        );
    }
    assert_eq!(s.calls.load(Ordering::SeqCst), 0);
    assert_eq!(
        std::fs::read_to_string(pairing.token()).unwrap(),
        "b".repeat(64)
    );
    std::env::remove_var("AXIOM_API_TOKEN");
    assert!(PhantomBridge::readiness().await.unwrap().ready);
}
#[cfg(unix)]
#[tokio::test]
async fn pairing_storage_failures_have_distinct_non_mutating_recovery() {
    use std::os::unix::fs::PermissionsExt;
    let _lock = ENVIRONMENT.lock().await;
    let (s, _server, _env) = fixture().await;
    let pairing = PairingFixture::new();
    std::env::remove_var("AXIOM_API_TOKEN");
    std::fs::set_permissions(pairing.token(), std::fs::Permissions::from_mode(0o644)).unwrap();
    diagnostic(
        PhantomBridge::readiness().await.err().unwrap(),
        "PAIRING_STORAGE_INVALID",
    );
    assert_eq!(
        std::fs::metadata(pairing.token())
            .unwrap()
            .permissions()
            .mode()
            & 0o777,
        0o644
    );
    std::fs::set_permissions(pairing.token(), std::fs::Permissions::from_mode(0o600)).unwrap();
    std::fs::write(pairing.token(), MARKER).unwrap();
    diagnostic(
        PhantomBridge::readiness().await.err().unwrap(),
        "PAIRING_STORAGE_INVALID",
    );
    assert_eq!(std::fs::read_to_string(pairing.token()).unwrap(), MARKER);
    std::fs::remove_file(pairing.token()).unwrap();
    diagnostic(
        PhantomBridge::readiness().await.err().unwrap(),
        "PAIRING_MISSING",
    );
    assert!(!pairing.token().exists());
    std::env::remove_var("AXIOM_PAIRING_FILE");
    for key in ["HOME", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME"] {
        std::env::remove_var(key);
    }
    diagnostic(
        PhantomBridge::readiness().await.err().unwrap(),
        "PAIRING_USER_DIRECTORY_MISSING",
    );
    assert_eq!(s.calls.load(Ordering::SeqCst), 0);
}
