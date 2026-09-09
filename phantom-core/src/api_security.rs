//! Local IPC is privileged: loopback binding alone is not authorization.
use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::Response,
};
#[path = "ipc_pairing.rs"]
pub mod ipc_pairing;
pub use ipc_pairing::PairingError;
use std::path::PathBuf;

#[derive(Clone)]
pub struct ApiToken(String);
impl ApiToken {
    pub fn parse(value: String) -> Result<Self, &'static str> {
        if value.len() != 64 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err("AXIOM_API_TOKEN must be 64 hexadecimal characters (32 random bytes)");
        }
        Ok(Self(value))
    }
    /// Load the per-user paired token, creating an OS-protected one when absent.
    /// `AXIOM_API_TOKEN` still overrides for CI and tests; otherwise the token lives at
    /// [`ApiToken::pairing_file_path`] with `0700`/`0600` permissions and never in the environment.
    pub fn load_or_create_paired() -> Result<Self, PairingError> {
        Ok(Self(ipc_pairing::load_or_create_paired()?))
    }
    /// Load an already paired token (environment override or pairing file); fails closed.
    pub fn load_paired() -> Result<Self, PairingError> {
        Ok(Self(ipc_pairing::load_paired()?))
    }
    /// Generate a fresh random token from the OS CSPRNG without persisting it.
    pub fn generate_random() -> Result<Self, PairingError> {
        Ok(Self(ipc_pairing::generate_random()?))
    }
    /// Per-user pairing file location (see `ipc_pairing::pairing_file_path`).
    pub fn pairing_file_path() -> Result<PathBuf, PairingError> {
        ipc_pairing::pairing_file_path()
    }
    fn matches(&self, supplied: &str) -> bool {
        if supplied.len() != self.0.len() {
            return false;
        }
        self.0
            .bytes()
            .zip(supplied.bytes())
            .fold(0u8, |diff, (a, b)| diff | (a ^ b))
            == 0
    }
}

pub async fn authorize(
    State(token): State<ApiToken>,
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    // Native IPC only. Browser-origin requests are denied even with a token.
    if request.headers().contains_key("origin") || request.headers().contains_key("sec-fetch-site")
    {
        return Err(StatusCode::FORBIDDEN);
    }
    let expected_host = "127.0.0.1:7437";
    if request.headers().get("host").and_then(|h| h.to_str().ok()) != Some(expected_host) {
        return Err(StatusCode::FORBIDDEN);
    }
    let supplied = request
        .headers()
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;
    if !token.matches(supplied) {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(next.run(request).await)
}
