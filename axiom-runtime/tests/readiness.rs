use axiom_grid::{api_security::ApiToken, router, AppState};
use axum::{
    body::{to_bytes, Body},
    http::{Request, StatusCode},
    routing::get,
    Router,
};
use tower::ServiceExt;
fn request() -> axum::http::request::Builder {
    Request::builder()
        .uri("/readiness")
        .header("host", "127.0.0.1:7437")
        .header("authorization", format!("Bearer {}", "a".repeat(64)))
}
async fn mock(body: String, status: StatusCode) -> (Router, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let server = Router::new().route("/api/tags", get(move || async move { (status, body) }));
    let task = tokio::spawn(async move {
        axum::serve(listener, server).await.unwrap();
    });
    let app = router(
        AppState::local("test:latest".into())
            .unwrap()
            .with_loopback_port(port),
        ApiToken::parse("a".repeat(64)).unwrap(),
    );
    (app, task)
}
#[tokio::test]
async fn inventory_requires_exact_tag_and_never_claims_inference() {
    for (name, ready) in [
        ("test:latest", true),
        ("test:other", false),
        ("test:latest-remote", false),
    ] {
        let (app, task) = mock(
            serde_json::json!({"models":[{"name":name,"size":1234}]}).to_string(),
            StatusCode::OK,
        )
        .await;
        let response = app
            .oneshot(request().body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let body: serde_json::Value =
            serde_json::from_slice(&to_bytes(response.into_body(), 10000).await.unwrap()).unwrap();
        assert_eq!(body["ready"], ready);
        assert_eq!(body["configured_model"], "test:latest");
        if ready {
            assert!(body["message"]
                .as_str()
                .unwrap()
                .contains("not yet verified"));
        }
        task.abort();
    }
}
#[tokio::test]
async fn absent_inventory_is_actionable() {
    let (app, task) = mock(r#"{"models":[]}"#.into(), StatusCode::OK).await;
    let response = app
        .oneshot(request().body(Body::empty()).unwrap())
        .await
        .unwrap();
    let body: serde_json::Value =
        serde_json::from_slice(&to_bytes(response.into_body(), 10000).await.unwrap()).unwrap();
    assert_eq!(body["ready"], false);
    assert!(body["message"].as_str().unwrap().contains("No download"));
    task.abort();
}
#[tokio::test]
async fn inventory_is_authenticated_and_browser_denied() {
    let (app, task) = mock(r#"{"models":[]}"#.into(), StatusCode::OK).await;
    let r = Request::builder()
        .uri("/readiness")
        .header("host", "127.0.0.1:7437")
        .body(Body::empty())
        .unwrap();
    assert_eq!(
        app.clone().oneshot(r).await.unwrap().status(),
        StatusCode::UNAUTHORIZED
    );
    let r = request()
        .header("origin", "https://example.com")
        .body(Body::empty())
        .unwrap();
    assert_eq!(
        app.oneshot(r).await.unwrap().status(),
        StatusCode::FORBIDDEN
    );
    task.abort();
}
#[tokio::test]
async fn malformed_oversized_and_failed_inventory_are_sanitized() {
    for (body, status) in [
        (
            "private backend failure".into(),
            StatusCode::INTERNAL_SERVER_ERROR,
        ),
        ("private malformed".into(), StatusCode::OK),
        ("private".repeat(40000), StatusCode::OK),
        (
            serde_json::json!({"models":[{"name":"bad\nname","size":1}]}).to_string(),
            StatusCode::OK,
        ),
        (
            serde_json::json!({"models":[{"name":"x".repeat(257),"size":1}]}).to_string(),
            StatusCode::OK,
        ),
        ("redirect".into(), StatusCode::FOUND),
    ] {
        let (app, task) = mock(body, status).await;
        let response = app
            .oneshot(request().body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::BAD_GATEWAY);
        let body = to_bytes(response.into_body(), 1000).await.unwrap();
        assert!(!String::from_utf8_lossy(&body).contains("private"));
        task.abort();
    }
}
#[tokio::test]
async fn daemon_down_is_not_ready() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    drop(listener);
    let app = router(
        AppState::local("test:latest".into())
            .unwrap()
            .with_loopback_port(port),
        ApiToken::parse("a".repeat(64)).unwrap(),
    );
    assert_eq!(
        app.oneshot(request().body(Body::empty()).unwrap())
            .await
            .unwrap()
            .status(),
        StatusCode::BAD_GATEWAY
    );
}

#[test]
fn invalid_configured_models_are_rejected() {
    for model in [
        "".to_string(),
        " ".to_string(),
        "x".repeat(257),
        "bad\nmodel".to_string(),
    ] {
        assert!(AppState::local(model).is_err());
    }
}
