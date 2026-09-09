use axiom_grid::{api_security::ApiToken, router, AppState};
use axum::{
    body::{to_bytes, Body},
    http::{Request, StatusCode},
    routing::post,
    Json, Router,
};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::Duration;
use tower::ServiceExt;

fn token() -> ApiToken {
    ApiToken::parse("b".repeat(64)).unwrap()
}
fn authed(method: &str, uri: &str) -> axum::http::request::Builder {
    Request::builder()
        .method(method)
        .uri(uri)
        .header("host", "127.0.0.1:7437")
        .header("authorization", format!("Bearer {}", "b".repeat(64)))
        .header("content-type", "application/json")
}

/// Mock local model that takes `delay` to answer and records whether it ran to completion.
async fn slow_model(
    delay: Duration,
) -> (
    Router,
    Arc<tokio::sync::Notify>,
    Arc<AtomicBool>,
    tokio::task::JoinHandle<()>,
) {
    let entered = Arc::new(tokio::sync::Notify::new());
    let completed = Arc::new(AtomicBool::new(false));
    let (e, c) = (entered.clone(), completed.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let mock = Router::new().route(
        "/api/generate",
        post(move || {
            let (e, c) = (e.clone(), c.clone());
            async move {
                e.notify_one();
                tokio::time::sleep(delay).await;
                c.store(true, Ordering::SeqCst);
                Json(serde_json::json!({"response":"finished anyway","done":true}))
            }
        }),
    );
    let server = tokio::spawn(async move {
        axum::serve(listener, mock).await.unwrap();
    });
    let app = router(
        AppState::local("test".into())
            .unwrap()
            .with_loopback_port(port),
        token(),
    );
    (app, entered, completed, server)
}

#[tokio::test]
async fn cancel_aborts_in_flight_generation_and_frees_the_slot() {
    let (app, entered, completed, server) = slow_model(Duration::from_millis(1200)).await;
    let first = app.clone();
    let running = tokio::spawn(async move {
        first
            .oneshot(
                authed("POST", "/materialize")
                    .body(Body::from(r#"{"context":"slow"}"#))
                    .unwrap(),
            )
            .await
            .unwrap()
    });
    tokio::time::timeout(Duration::from_secs(3), entered.notified())
        .await
        .expect("model request must start");
    let cancel = app
        .clone()
        .oneshot(authed("POST", "/cancel").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(cancel.status(), StatusCode::OK);
    let body: serde_json::Value =
        serde_json::from_slice(&to_bytes(cancel.into_body(), 1000).await.unwrap()).unwrap();
    assert_eq!(body["cancelled"], true);

    let aborted = tokio::time::timeout(Duration::from_millis(500), running)
        .await
        .expect("cancel must return promptly, not wait for the model")
        .unwrap();
    assert_eq!(aborted.status().as_u16(), 499);
    let text =
        String::from_utf8(to_bytes(aborted.into_body(), 1000).await.unwrap().to_vec()).unwrap();
    assert!(text.contains("cancelled") && !text.contains("finished anyway"));

    // The model connection was dropped, so the mock never ran to completion.
    tokio::time::sleep(Duration::from_millis(1800)).await;
    assert!(
        !completed.load(Ordering::SeqCst),
        "local model kept generating after cancel"
    );

    // The single generation slot is released for the next explicit request.
    let next = app
        .oneshot(
            authed("POST", "/materialize")
                .body(Body::from(r#"{"context":"again"}"#))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(next.status(), StatusCode::OK);
    server.abort();
}

#[tokio::test]
async fn cancel_is_idempotent_when_nothing_is_running() {
    let app = router(AppState::local("test".into()).unwrap(), token());
    for _ in 0..2 {
        let res = app
            .clone()
            .oneshot(authed("POST", "/cancel").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::OK);
        let body: serde_json::Value =
            serde_json::from_slice(&to_bytes(res.into_body(), 1000).await.unwrap()).unwrap();
        assert_eq!(body["cancelled"], false);
    }
}

#[tokio::test]
async fn cancel_requires_native_authentication() {
    let app = router(AppState::local("test".into()).unwrap(), token());
    let anonymous = Request::builder()
        .method("POST")
        .uri("/cancel")
        .header("host", "127.0.0.1:7437")
        .body(Body::empty())
        .unwrap();
    assert_eq!(
        app.clone().oneshot(anonymous).await.unwrap().status(),
        StatusCode::UNAUTHORIZED
    );
    let browser = authed("POST", "/cancel")
        .header("origin", "https://evil.example")
        .body(Body::empty())
        .unwrap();
    assert_eq!(
        app.oneshot(browser).await.unwrap().status(),
        StatusCode::FORBIDDEN
    );
}
