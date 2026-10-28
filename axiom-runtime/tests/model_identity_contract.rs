//! Independent model-identity contracts; loopback mocks only, never a real model.
//!
//! These tests are authored for CI. They were not compiled or executed in the
//! agent workspace, which has no Rust toolchain. Inventory identity is reported
//! metadata, not independent verification of model bytes.
use axiom_grid::{ai::KAIRO_SYSTEM_PROMPT, api_security::ApiToken, router, AppState};
use axum::{
    body::{to_bytes, Body, Bytes},
    extract::State,
    http::{header, Request, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
use serde_json::{json, Value};
use std::{
    sync::{
        atomic::{AtomicUsize, Ordering},
        Arc, Mutex,
    },
    time::Duration,
};
use tokio::{sync::Notify, task::JoinHandle};
use tower::ServiceExt;

const MODEL: &str = "identity-contract:latest";
const PROMPT: &str = "  PRIVATE_IDENTITY_CONTRACT_PROMPT: \"hello\" 🌍\nSecond line.\t  ";
const OUTPUT: &str = "Validated suggestion 🌍";
const REJECTED_OUTPUT: &str = "SENSITIVE_BACKEND_OUTPUT_MUST_NOT_ESCAPE";

fn digest() -> String {
    "0123456789abcdef".repeat(4)
}

fn entry(name: &str, value: &str, size: u64) -> Value {
    json!({"name": name, "digest": value, "size": size})
}

fn approved_inventory() -> Value {
    json!({"models": [entry(MODEL, &digest(), 1024)]})
}

fn valid_output() -> Value {
    json!({"model": MODEL, "response": OUTPUT, "done": true})
}

#[derive(Clone)]
struct WireReply {
    status: StatusCode,
    body: String,
}

impl WireReply {
    fn json(value: Value) -> Self {
        Self {
            status: StatusCode::OK,
            body: value.to_string(),
        }
    }

    fn response(self) -> Response {
        let status = self.status;
        let mut response = (
            status,
            [(header::CONTENT_TYPE, "application/json")],
            self.body,
        )
            .into_response();
        if status.is_redirection() {
            response
                .headers_mut()
                .insert(header::LOCATION, "/redirected-tags".parse().unwrap());
        }
        response
    }
}

#[derive(Clone)]
struct TagsPause {
    entered: Arc<Notify>,
    release: Arc<Notify>,
}

#[derive(Clone)]
struct MockState {
    tags: Arc<Mutex<WireReply>>,
    output: Arc<Mutex<WireReply>>,
    tag_gets: Arc<AtomicUsize>,
    prompt_posts: Arc<AtomicUsize>,
    captured_bodies: Arc<Mutex<Vec<Vec<u8>>>>,
    events: Arc<Mutex<Vec<&'static str>>>,
    next_tags_pause: Arc<Mutex<Option<TagsPause>>>,
}

async fn tags_handler(State(state): State<MockState>) -> Response {
    state.tag_gets.fetch_add(1, Ordering::SeqCst);
    state.events.lock().unwrap().push("tags");
    // No std::sync::MutexGuard lives across this await.
    let pause = { state.next_tags_pause.lock().unwrap().take() };
    if let Some(pause) = pause {
        pause.entered.notify_one();
        pause.release.notified().await;
    }
    let reply = { state.tags.lock().unwrap().clone() };
    reply.response()
}

async fn generate_handler(State(state): State<MockState>, body: Bytes) -> Response {
    // Count/capture every POST, even one with invalid JSON. Rejected preflights
    // must leave both this counter and captured bytes empty.
    state.prompt_posts.fetch_add(1, Ordering::SeqCst);
    state.captured_bodies.lock().unwrap().push(body.to_vec());
    state.events.lock().unwrap().push("generate");
    let reply = { state.output.lock().unwrap().clone() };
    reply.response()
}

struct Fixture {
    app: Router,
    backend: MockState,
    server: Option<JoinHandle<()>>,
}

impl Drop for Fixture {
    fn drop(&mut self) {
        if let Some(server) = &self.server {
            server.abort();
        }
    }
}

impl Fixture {
    async fn new(inventory: Value, output: Value, expected: String) -> Self {
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let backend = MockState {
            tags: Arc::new(Mutex::new(WireReply::json(inventory))),
            output: Arc::new(Mutex::new(WireReply::json(output))),
            tag_gets: Arc::new(AtomicUsize::new(0)),
            prompt_posts: Arc::new(AtomicUsize::new(0)),
            captured_bodies: Arc::new(Mutex::new(Vec::new())),
            events: Arc::new(Mutex::new(Vec::new())),
            next_tags_pause: Arc::new(Mutex::new(None)),
        };
        let mock = Router::new()
            .route("/api/tags", get(tags_handler))
            // Following a redirect would lead to an otherwise approved report;
            // a 502 assertion therefore detects redirects being followed.
            .route(
                "/redirected-tags",
                get(|| async { axum::Json(approved_inventory()) }),
            )
            .route("/api/generate", post(generate_handler))
            .with_state(backend.clone());
        let server = tokio::spawn(async move {
            axum::serve(listener, mock).await.unwrap();
        });
        let app = router(
            AppState::local(MODEL.to_string(), expected)
                .unwrap()
                .with_loopback_port(port),
            ApiToken::parse("a".repeat(64)).unwrap(),
        );
        Self {
            app,
            backend,
            server: Some(server),
        }
    }

    fn inventory(&self, inventory: Value) {
        *self.backend.tags.lock().unwrap() = WireReply::json(inventory);
    }

    fn no_prompt(&self) {
        self.no_additional_prompt_after(0);
    }

    fn no_additional_prompt_after(&self, count: usize) {
        assert_eq!(self.backend.prompt_posts.load(Ordering::SeqCst), count);
        assert_eq!(self.backend.captured_bodies.lock().unwrap().len(), count);
    }

    fn pause_next_tags(&self) -> TagsPause {
        let pause = TagsPause {
            entered: Arc::new(Notify::new()),
            release: Arc::new(Notify::new()),
        };
        *self.backend.next_tags_pause.lock().unwrap() = Some(pause.clone());
        pause
    }

    async fn request(&self, method: &str, path: &str, body: Value) -> (StatusCode, Vec<u8>) {
        request(self.app.clone(), method, path, body).await
    }
}

async fn request(app: Router, method: &str, path: &str, body: Value) -> (StatusCode, Vec<u8>) {
    let input = if method == "GET" {
        Body::empty()
    } else {
        Body::from(body.to_string())
    };
    let response = tokio::time::timeout(
        Duration::from_secs(5),
        app.oneshot(
            Request::builder()
                .method(method)
                .uri(path)
                .header("host", "127.0.0.1:7437")
                .header("authorization", format!("Bearer {}", "a".repeat(64)))
                .header("content-type", "application/json")
                .body(input)
                .unwrap(),
        ),
    )
    .await
    .expect("loopback contract request must complete without sleeps")
    .unwrap();
    let status = response.status();
    let body = to_bytes(response.into_body(), 64 * 1024)
        .await
        .unwrap()
        .to_vec();
    (status, body)
}

fn assert_not_disclosed(body: &[u8]) {
    let text = String::from_utf8_lossy(body);
    assert!(
        !text.contains(REJECTED_OUTPUT),
        "rejected model output escaped"
    );
    assert!(
        !text.contains("\"suggestion\""),
        "rejection must not be a preview"
    );
    assert!(
        !text.contains("PRIVATE_IDENTITY_CONTRACT_PROMPT"),
        "prompt must not be echoed in an error"
    );
}

fn invalid_inventories() -> Vec<(&'static str, Value)> {
    let approved = entry(MODEL, &digest(), 1024);
    vec![
        ("missing configured name", json!({"models": []})),
        (
            "wrong name with approved digest",
            json!({"models": [entry("other:latest", &digest(), 1024)]}),
        ),
        (
            "prefix is not exact name",
            json!({"models": [entry("identity-contract:latest-extra", &digest(), 1024)]}),
        ),
        (
            "missing digest",
            json!({"models": [{"name": MODEL, "size": 1024}]}),
        ),
        ("empty digest", json!({"models": [entry(MODEL, "", 1024)]})),
        (
            "missing size",
            json!({"models": [{"name": MODEL, "digest": digest()}]}),
        ),
        ("zero size", json!({"models": [entry(MODEL, &digest(), 0)]})),
        (
            "malformed digest",
            json!({"models": [entry(MODEL, "sha256:short", 1024)]}),
        ),
        (
            "nonhex digest",
            json!({"models": [entry(MODEL, &"g".repeat(64), 1024)]}),
        ),
        (
            "double digest prefix",
            json!({"models": [entry(MODEL, &format!("sha256:sha256:{}", digest()), 1024)]}),
        ),
        (
            "different digest",
            json!({"models": [entry(MODEL, &"f".repeat(64), 1024)]}),
        ),
        (
            "identical duplicate",
            json!({"models": [approved.clone(), approved.clone()]}),
        ),
        (
            "duplicate with mismatch",
            json!({"models": [approved.clone(), entry(MODEL, &"f".repeat(64), 1024)]}),
        ),
        (
            "duplicate with missing digest",
            json!({"models": [approved, {"name": MODEL, "size": 1024}]}),
        ),
    ]
}

#[tokio::test]
async fn invalid_or_missing_configured_digest_refuses_state() {
    for expected in [
        "".to_string(),
        " ".to_string(),
        "a".repeat(63),
        "a".repeat(65),
        "g".repeat(64),
        "sha256:".to_string(),
        format!("sha256:{}", "a".repeat(63)),
        format!("sha512:{}", digest()),
        format!("sha256:sha256:{}", digest()),
        format!("{} {}", "a".repeat(32), "a".repeat(31)),
        "é".repeat(32),
    ] {
        assert!(
            AppState::local(MODEL.into(), expected.clone()).is_err(),
            "accepted {expected:?}"
        );
    }
}

#[tokio::test]
async fn configured_model_name_must_be_nonempty_bounded_ascii_graphic() {
    for model in [
        "".to_string(),
        " ".to_string(),
        " model".to_string(),
        "model ".to_string(),
        "model\ttag".to_string(),
        "model\nother".to_string(),
        "model\0tag".to_string(),
        "mödél".to_string(),
        "x".repeat(257),
    ] {
        assert!(
            AppState::local(model.clone(), digest()).is_err(),
            "accepted {model:?}"
        );
    }
    for model in ["m".to_string(), "model/path:tag".to_string(), "x".repeat(256)] {
        assert!(AppState::local(model, digest()).is_ok());
    }
}

#[tokio::test]
async fn approved_digest_forms_normalize_and_valid_prompt_is_unchanged() {
    for expected in [
        digest(),
        digest().to_uppercase(),
        format!("sha256:{}", digest()),
        format!("SHA256:{}", digest().to_uppercase()),
    ] {
        for reported in [
            digest(),
            digest().to_uppercase(),
            format!("sha256:{}", digest()),
            format!("SHA256:{}", digest().to_uppercase()),
        ] {
            let fixture = Fixture::new(
                json!({"models": [
                    entry("unrelated:latest", &"f".repeat(64), 5),
                    entry(MODEL, &reported, 1024)
                ]}),
                valid_output(),
                expected.clone(),
            )
            .await;
            let (status, body) = fixture.request("GET", "/readiness", Value::Null).await;
            assert_eq!(status, StatusCode::OK);
            let ready: Value = serde_json::from_slice(&body).unwrap();
            assert_eq!(ready["ready"], true);
            assert_eq!(ready["configured_model"], MODEL);
            assert_eq!(ready["expected_digest"], digest());
            assert_eq!(ready["identity_check_scope"], "reported-only");
            fixture.no_prompt();
            let (status, body) = fixture
                .request("POST", "/materialize", json!({"context": PROMPT}))
                .await;
            assert_eq!(status, StatusCode::OK);
            let output: Value = serde_json::from_slice(&body).unwrap();
            assert_eq!(output["suggestion"], OUTPUT);
            assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 2);
            assert_eq!(fixture.backend.prompt_posts.load(Ordering::SeqCst), 1);
            let captured = fixture.backend.captured_bodies.lock().unwrap();
            assert_eq!(captured.len(), 1);
            let forwarded: Value = serde_json::from_slice(&captured[0]).unwrap();
            assert_eq!(
                forwarded,
                json!({
                    "model": MODEL, "prompt": PROMPT, "system": KAIRO_SYSTEM_PROMPT,
                    "stream": false, "options": {"num_predict": 2048}
                })
            );
            assert_eq!(
                *fixture.backend.events.lock().unwrap(),
                vec!["tags", "tags", "generate"]
            );
        }
    }
}

#[tokio::test]
async fn invalid_identity_is_not_ready_and_direct_materialize_never_posts_prompt() {
    for (case, inventory) in invalid_inventories() {
        let fixture = Fixture::new(inventory.clone(), valid_output(), digest()).await;
        // Direct generation MUST fail without requiring an earlier readiness call.
        let (status, body) = fixture
            .request("POST", "/materialize", json!({"context": PROMPT}))
            .await;
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE, "{case}");
        assert_not_disclosed(&body);
        fixture.no_prompt();
        assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 1, "{case}");
        let (status, body) = fixture.request("GET", "/readiness", Value::Null).await;
        assert_eq!(status, StatusCode::OK, "{case}");
        let ready: Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(ready["ready"], false, "{case}: {ready}");
        fixture.no_prompt();
        assert_eq!(*fixture.backend.events.lock().unwrap(), vec!["tags", "tags"]);
    }
}

#[tokio::test]
async fn successful_readiness_is_not_cached_for_subsequent_generation() {
    let fixture = Fixture::new(approved_inventory(), valid_output(), digest()).await;
    let (_, body) = fixture.request("GET", "/readiness", Value::Null).await;
    assert_eq!(serde_json::from_slice::<Value>(&body).unwrap()["ready"], true);
    let pause = fixture.pause_next_tags();
    let app = fixture.app.clone();
    let running = tokio::spawn(async move {
        request(app, "POST", "/materialize", json!({"context": PROMPT})).await
    });
    tokio::time::timeout(Duration::from_secs(5), pause.entered.notified())
        .await
        .expect("fresh inventory request must start before prompt POST");
    fixture.no_prompt();
    assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 2);
    fixture.inventory(json!({"models": [entry(MODEL, &"f".repeat(64), 1024)]}));
    pause.release.notify_one();
    let (status, body) = tokio::time::timeout(Duration::from_secs(5), running)
        .await
        .unwrap()
        .unwrap();
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_not_disclosed(&body);
    fixture.no_prompt();

    // Failed preflight must release the generation slot; no cached failure either.
    fixture.inventory(approved_inventory());
    let (status, body) = fixture
        .request("POST", "/materialize", json!({"context": PROMPT}))
        .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(
        serde_json::from_slice::<Value>(&body).unwrap()["suggestion"],
        OUTPUT
    );
    assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 3);
    assert_eq!(fixture.backend.prompt_posts.load(Ordering::SeqCst), 1);

    // Even a successful generation cannot authorize a later changed inventory.
    fixture.inventory(json!({"models": []}));
    let (status, body) = fixture
        .request("POST", "/materialize", json!({"context": PROMPT}))
        .await;
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_not_disclosed(&body);
    fixture.no_additional_prompt_after(1);
    assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 4);
}

#[tokio::test]
async fn readiness_tracks_inventory_changes_in_both_directions() {
    let fixture = Fixture::new(approved_inventory(), valid_output(), digest()).await;
    for ready in [true, false, true] {
        fixture.inventory(if ready {
            approved_inventory()
        } else {
            json!({"models": []})
        });
        let (status, body) = fixture.request("GET", "/readiness", Value::Null).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(serde_json::from_slice::<Value>(&body).unwrap()["ready"], ready);
        fixture.no_prompt();
    }
    assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 3);
}

#[tokio::test]
async fn malformed_status_redirect_and_oversize_inventory_fail_before_prompt() {
    let replies = vec![
        WireReply {
            status: StatusCode::OK,
            body: "not-json".into(),
        },
        WireReply {
            status: StatusCode::OK,
            body: json!({"models": "not-an-array"}).to_string(),
        },
        WireReply {
            status: StatusCode::OK,
            body: json!({"models": [{
                "name": MODEL, "size": "not-a-number", "digest": digest()
            }]})
            .to_string(),
        },
        WireReply {
            status: StatusCode::OK,
            body: "x".repeat(256 * 1024 + 1),
        },
        WireReply {
            status: StatusCode::FOUND,
            body: approved_inventory().to_string(),
        },
        WireReply {
            status: StatusCode::TEMPORARY_REDIRECT,
            body: approved_inventory().to_string(),
        },
        WireReply {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            body: approved_inventory().to_string(),
        },
    ];
    for reply in replies {
        let fixture = Fixture::new(approved_inventory(), valid_output(), digest()).await;
        *fixture.backend.tags.lock().unwrap() = reply;
        let (status, body) = fixture.request("GET", "/readiness", Value::Null).await;
        assert_eq!(status, StatusCode::BAD_GATEWAY);
        assert_not_disclosed(&body);
        let (status, body) = fixture
            .request("POST", "/materialize", json!({"context": PROMPT}))
            .await;
        assert_eq!(status, StatusCode::BAD_GATEWAY);
        assert_not_disclosed(&body);
        fixture.no_prompt();
        assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 2);
    }
}

#[tokio::test]
async fn unavailable_inventory_transport_is_503_without_prompt_post() {
    let mut fixture = Fixture::new(approved_inventory(), valid_output(), digest()).await;
    let server = fixture.server.take().unwrap();
    server.abort();
    assert!(server.await.unwrap_err().is_cancelled());
    let (status, body) = fixture.request("GET", "/readiness", Value::Null).await;
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_not_disclosed(&body);
    let (status, body) = fixture
        .request("POST", "/materialize", json!({"context": PROMPT}))
        .await;
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_not_disclosed(&body);
    fixture.no_prompt();
    assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn generation_response_requires_exact_configured_model_and_discloses_no_rejected_output() {
    let mut outputs = vec![json!({"response": REJECTED_OUTPUT, "done": true})];
    for reported in [
        json!("other:latest"),
        json!("identity-contract"),
        json!("IDENTITY-CONTRACT:latest"),
        Value::Null,
        json!(123),
    ] {
        outputs.push(json!({"model": reported, "response": REJECTED_OUTPUT, "done": true}));
    }
    for output in outputs {
        let fixture = Fixture::new(approved_inventory(), output, digest()).await;
        let (status, body) = fixture
            .request("POST", "/materialize", json!({"context": PROMPT}))
            .await;
        assert_eq!(status, StatusCode::BAD_GATEWAY);
        assert_not_disclosed(&body);
        assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 1);
        assert_eq!(fixture.backend.prompt_posts.load(Ordering::SeqCst), 1);
        assert_eq!(fixture.backend.captured_bodies.lock().unwrap().len(), 1);
        assert_eq!(*fixture.backend.events.lock().unwrap(), vec!["tags", "generate"]);
        // Wrong response identity must also release the slot for a new request.
        *fixture.backend.output.lock().unwrap() = WireReply::json(valid_output());
        let (status, body) = fixture
            .request("POST", "/materialize", json!({"context": PROMPT}))
            .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            serde_json::from_slice::<Value>(&body).unwrap()["suggestion"],
            OUTPUT
        );
        assert_eq!(fixture.backend.tag_gets.load(Ordering::SeqCst), 2);
        assert_eq!(fixture.backend.prompt_posts.load(Ordering::SeqCst), 2);
    }
}
