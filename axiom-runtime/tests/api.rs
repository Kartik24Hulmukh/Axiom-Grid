use axiom_grid::{api_security::ApiToken, router, AppState};
use axum::{
    body::{to_bytes, Body},
    http::{Request, StatusCode},
    routing::post,
    Json, Router,
};
use tower::ServiceExt;
fn token() -> ApiToken {
    ApiToken::parse("a".repeat(64)).unwrap()
}
fn request(body: &str) -> axum::http::request::Builder {
    let _ = body;
    Request::builder()
        .method("POST")
        .uri("/materialize")
        .header("host", "127.0.0.1:7437")
        .header("authorization", format!("Bearer {}", "a".repeat(64)))
        .header("content-type", "application/json")
}
async fn app_with_mock(response: serde_json::Value) -> (Router, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let server = Router::new().route(
        "/api/generate",
        post(move |Json(input): Json<serde_json::Value>| async move {
            assert_eq!(input["model"], "test:latest");
            assert_eq!(input["stream"], false);
            assert_eq!(input["prompt"], "Rewrite this");
            Json(response)
        }),
    );
    let task = tokio::spawn(async move {
        axum::serve(listener, server).await.unwrap();
    });
    (
        router(
            AppState::local("test:latest".into())
                .unwrap()
                .with_loopback_port(port),
            token(),
        ),
        task,
    )
}
#[test]
fn invalid_token_config_fails_closed() {
    for value in ["", "secret", &"g".repeat(64), &"a".repeat(63)] {
        assert!(ApiToken::parse(value.into()).is_err());
    }
}
#[tokio::test]
async fn authenticated_preview_roundtrip() {
    let (app, task) = app_with_mock(serde_json::json!({"response":"Hello 🌍", "done":true})).await;
    let res = app
        .oneshot(
            request("")
                .body(Body::from(r#"{"context":"Rewrite this"}"#))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(res.status(), StatusCode::OK);
    let value: serde_json::Value =
        serde_json::from_slice(&to_bytes(res.into_body(), 10000).await.unwrap()).unwrap();
    assert_eq!(value["suggestion"], "Hello 🌍");
    assert_eq!(value["char_count"], 7);
    assert_eq!(value["word_count"], 2);
    task.abort();
}
#[tokio::test]
async fn rejects_untrusted_clients() {
    let app = router(AppState::local("test".into()).unwrap(), token());
    let no_token = Request::builder()
        .method("POST")
        .uri("/materialize")
        .header("host", "127.0.0.1:7437")
        .body(Body::empty())
        .unwrap();
    assert_eq!(
        app.clone().oneshot(no_token).await.unwrap().status(),
        StatusCode::UNAUTHORIZED
    );
    for (name, value, status) in [
        ("origin", "https://evil.example", StatusCode::FORBIDDEN),
        ("sec-fetch-site", "same-origin", StatusCode::FORBIDDEN),
        ("host", "evil.example:7437", StatusCode::FORBIDDEN),
        ("authorization", "Bearer wrong", StatusCode::UNAUTHORIZED),
    ] {
        let mut r = request("").body(Body::from("{} ")).unwrap();
        r.headers_mut().insert(
            axum::http::HeaderName::from_bytes(name.as_bytes()).unwrap(),
            value.parse().unwrap(),
        );
        assert_eq!(app.clone().oneshot(r).await.unwrap().status(), status);
    }
}
#[tokio::test]
async fn bounded_explicit_input_and_removed_routes() {
    let app = router(AppState::local("test".into()).unwrap(), token());
    for (body, status) in [
        (r#"{"context":" "}"#.to_string(), 400),
        ("{}".into(), 422),
        (
            serde_json::json!({"context":"x".repeat(16001)}).to_string(),
            400,
        ),
        (
            serde_json::json!({"context":"x".repeat(70000)}).to_string(),
            413,
        ),
    ] {
        assert_eq!(
            app.clone()
                .oneshot(request("").body(Body::from(body)).unwrap())
                .await
                .unwrap()
                .status()
                .as_u16(),
            status
        );
    }
    for path in [
        "/inject",
        "/ask",
        "/context",
        "/mobile/sync",
        "/generate_image",
        "/kami/export",
    ] {
        let r = Request::builder()
            .method("POST")
            .uri(path)
            .body(Body::empty())
            .unwrap();
        assert_eq!(
            app.clone().oneshot(r).await.unwrap().status(),
            StatusCode::NOT_FOUND
        );
    }
}
#[tokio::test]
async fn invalid_model_output_fails_without_leaking_content() {
    for output in [
        serde_json::json!({"response":"", "done":true}),
        serde_json::json!({"response":"partial secret", "done":false}),
        serde_json::json!({"error":"secret"}),
        serde_json::json!({"response":"x".repeat(270000),"done":true}),
    ] {
        let (app, task) = app_with_mock(output).await;
        let r = app
            .oneshot(
                request("")
                    .body(Body::from(r#"{"context":"Rewrite this"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(r.status(), StatusCode::BAD_GATEWAY);
        assert!(
            !String::from_utf8(to_bytes(r.into_body(), 1000).await.unwrap().to_vec())
                .unwrap()
                .contains("secret")
        );
        task.abort();
    }
}

#[tokio::test]
async fn concurrent_generation_is_rejected() {
    let entered = std::sync::Arc::new(tokio::sync::Notify::new());
    let release = std::sync::Arc::new(tokio::sync::Notify::new());
    let a = entered.clone();
    let b = release.clone();
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let mock = Router::new().route(
        "/api/generate",
        post(move || async move {
            a.notify_one();
            b.notified().await;
            Json(serde_json::json!({"response":"Done","done":true}))
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
    let first = app.clone();
    let running = tokio::spawn(async move {
        first
            .oneshot(
                request("")
                    .body(Body::from(r#"{"context":"one"}"#))
                    .unwrap(),
            )
            .await
            .unwrap()
    });
    tokio::time::timeout(std::time::Duration::from_secs(3), entered.notified())
        .await
        .unwrap();
    let second = app
        .clone()
        .oneshot(
            request("")
                .body(Body::from(r#"{"context":"two"}"#))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(second.status(), StatusCode::TOO_MANY_REQUESTS);
    release.notify_one();
    assert_eq!(running.await.unwrap().status(), StatusCode::OK);
    server.abort();
}
#[tokio::test]
async fn redirects_and_http_errors_are_not_success() {
    for status in [
        StatusCode::FOUND,
        StatusCode::INTERNAL_SERVER_ERROR,
        StatusCode::NOT_FOUND,
    ] {
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let mock = Router::new().route(
            "/api/generate",
            post(move || async move {
                (
                    status,
                    [("location", "http://127.0.0.1:1/never-follow")],
                    "sensitive server detail",
                )
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
        let res = app
            .oneshot(
                request("")
                    .body(Body::from(r#"{"context":"test"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::BAD_GATEWAY);
        server.abort();
    }
}
#[tokio::test]
async fn health_is_not_model_readiness() {
    let app = router(AppState::local("missing".into()).unwrap(), token());
    let r = app
        .oneshot(
            Request::builder()
                .uri("/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::OK);
    let text = String::from_utf8(to_bytes(r.into_body(), 1000).await.unwrap().to_vec()).unwrap();
    assert!(text.contains("preview-only"));
}
