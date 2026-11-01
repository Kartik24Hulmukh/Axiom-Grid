//! PhantomBridge — connects the Tauri overlay to the local Axiom-Grid runtime
//! over authenticated loopback HTTP IPC (127.0.0.1:7437 by default).
//!
//! Authentication uses the per-user OS-protected pairing file written by the
//! runtime (see `phantom-core/src/ipc_pairing.rs`); `AXIOM_API_TOKEN` remains an
//! explicit override for CI and tests. No secret is ever logged.

#[allow(dead_code)]
#[path = "../../../phantom-core/src/ipc_pairing.rs"]
mod ipc_pairing;

use anyhow::Result;
use reqwest::{Client, Response};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::Duration;
use std::{fmt, io};
use tokio::sync::oneshot;

const DEFAULT_RUNTIME_PORT: u16 = 7437;

// These errors intentionally carry no source, URL, token, path, or response body.
// Display is the sanitized contract consumed by the existing String IPC boundary.
#[derive(Debug)]
enum Diagnostic {
    OverrideInvalid,
    PairingMissing,
    PairingUnsafe,
    PairingPermission,
    PairingIo,
    NoUserDirectory,
    StorageUnsupported,
    ClientSetup,
    Timeout,
    Connection,
    Transport,
    Decode,
    Http(Operation, u16),
}

#[derive(Clone, Copy, Debug)]
enum Operation {
    Preview,
    Readiness,
    Cancel,
}

impl fmt::Display for Diagnostic {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::OverrideInvalid => "PAIRING_OVERRIDE_INVALID: AXIOM_API_TOKEN must be 64 ASCII hexadecimal characters; file fallback is disabled for an explicit override",
            Self::PairingMissing => "PAIRING_MISSING: Start axiom-runtime under the same user to establish pairing",
            Self::PairingUnsafe => "PAIRING_STORAGE_INVALID: Pairing storage is invalid or unsafe; follow the pairing recovery runbook; do not silently change permissions or regenerate credentials",
            Self::PairingPermission => "PAIRING_PERMISSION_DENIED: Pairing storage access was denied; follow the pairing recovery runbook",
            Self::PairingIo => "PAIRING_IO_FAILURE: Pairing storage could not be read; follow the pairing recovery runbook",
            Self::NoUserDirectory => "PAIRING_USER_DIRECTORY_MISSING: No per-user pairing directory is available; configure a supported user directory",
            Self::StorageUnsupported => "PAIRING_STORAGE_UNSUPPORTED: Protected file pairing is unsupported on this platform; configure an explicit valid token without inferring approval",
            Self::ClientSetup => "HTTP_CLIENT_SETUP_FAILED: Local runtime HTTP client could not be initialized",
            Self::Timeout => "TRANSPORT_TIMEOUT: Local runtime request timed out",
            Self::Connection => "TRANSPORT_CONNECTION_FAILED: Could not connect to the local runtime",
            Self::Transport => "TRANSPORT_FAILED: Local runtime communication failed",
            Self::Decode => "RESPONSE_DECODE_FAILED: Local runtime response contains malformed JSON or an unexpected schema",
            Self::Http(operation, status) => {
                let operation_name = match operation {
                    Operation::Preview => "Preview",
                    Operation::Readiness => "Readiness",
                    Operation::Cancel => "Cancel",
                };
                let detail = match *status {
                    401 => "PAIRING_AUTH_FAILED: Runtime pairing authentication failed; follow the pairing recovery runbook",
                    403 => "POLICY_DENIED: Runtime policy denied the operation",
                    400 | 413 if matches!(operation, Operation::Preview) => "PREVIEW_INPUT_REJECTED: Preview input was rejected",
                    429 => "RUNTIME_BUSY: Runtime is busy; retry later",
                    499 => "CANCEL_REQUESTED: Cancellation was requested; backend compute is not confirmed stopped",
                    502 => "BACKEND_RESPONSE_INVALID: Backend response or identity validation failed",
                    503 => match operation {
                        Operation::Readiness => "READINESS_UNAVAILABLE: Readiness service is unavailable",
                        Operation::Preview => "PREVIEW_UNAVAILABLE: Preview service is unavailable or the expected-identity check failed; exact cause is not established",
                        Operation::Cancel => "CANCEL_UNAVAILABLE: Cancellation service is unavailable; backend compute is not confirmed stopped",
                    },
                    500..=599 => "RUNTIME_SERVER_ERROR: Runtime server operation failed",
                    _ => "HTTP_UNEXPECTED_STATUS: Runtime returned an unexpected non-success status",
                };
                return write!(f, "{operation_name} HTTP {status}: {detail}");
            }
        };
        f.write_str(message)
    }
}

impl std::error::Error for Diagnostic {}

fn transport_error(error: reqwest::Error) -> Diagnostic {
    if error.is_timeout() {
        Diagnostic::Timeout
    } else if error.is_connect() {
        Diagnostic::Connection
    } else {
        Diagnostic::Transport
    }
}

fn decode_error(error: reqwest::Error) -> Diagnostic {
    if error.is_timeout() {
        Diagnostic::Timeout
    } else if error.is_decode() {
        Diagnostic::Decode
    } else {
        transport_error(error)
    }
}

fn successful(response: Response, operation: Operation) -> Result<Response> {
    let status = response.status();
    if !status.is_success() {
        // Do not read or retain untrusted error bodies, including redirect bodies.
        return Err(Diagnostic::Http(operation, status.as_u16()).into());
    }
    Ok(response)
}

#[derive(Serialize)]
struct MaterializeRequest {
    context: String,
}

#[derive(Deserialize)]
struct MaterializeResponse {
    suggestion: String,
    #[allow(dead_code)]
    word_count: usize,
}

#[derive(Deserialize)]
struct CancelResponse {
    cancelled: bool,
}

#[derive(Deserialize, Serialize)]
pub struct ModelInfo {
    pub name: String,
    pub size: u64,
    pub digest: String,
}
#[derive(Deserialize, Serialize)]
pub struct ReadinessResponse {
    pub ready: bool,
    pub configured_model: String,
    pub expected_digest: String,
    pub identity_check_scope: String,
    pub installed_models: Vec<ModelInfo>,
}

struct ActiveMaterialize {
    owner: Arc<()>,
    cancel_tx: Option<oneshot::Sender<()>>,
}

fn cancel_slot() -> &'static Mutex<Option<ActiveMaterialize>> {
    static SLOT: OnceLock<Mutex<Option<ActiveMaterialize>>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(None))
}

/// Admission stays held even after the cancellation sender has been consumed.
/// Dropping the owning future releases its lease, including during cancel acknowledgement.
struct MaterializeLease {
    owner: Arc<()>,
}

impl MaterializeLease {
    fn reserve() -> Result<(Self, oneshot::Receiver<()>)> {
        let mut slot = cancel_slot()
            .lock()
            .map_err(|_| anyhow::anyhow!("Materialize admission lock poisoned"))?;
        if slot.is_some() {
            anyhow::bail!("A materialize request is already active");
        }
        let owner = Arc::new(());
        let (cancel_tx, cancel_rx) = oneshot::channel();
        *slot = Some(ActiveMaterialize {
            owner: Arc::clone(&owner),
            cancel_tx: Some(cancel_tx),
        });
        Ok((Self { owner }, cancel_rx))
    }
}

impl Drop for MaterializeLease {
    fn drop(&mut self) {
        // A poisoned lock is deliberately not recovered: admission fails closed.
        if let Ok(mut slot) = cancel_slot().lock() {
            if slot
                .as_ref()
                .map(|active| Arc::ptr_eq(&active.owner, &self.owner))
                .unwrap_or(false)
            {
                *slot = None;
            }
        }
    }
}

/// Runtime port: `AXIOM_RUNTIME_PORT` lets tests point at a loopback mock.
pub fn runtime_port() -> u16 {
    std::env::var("AXIOM_RUNTIME_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(DEFAULT_RUNTIME_PORT)
}

fn url(path: &str) -> String {
    format!("http://127.0.0.1:{}{path}", runtime_port())
}

fn client(timeout: Duration) -> Result<Client> {
    Ok(Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(timeout)
        .build()
        .map_err(|_| Diagnostic::ClientSetup)?)
}

/// Paired IPC token: environment override, else the OS-protected pairing file.
fn token() -> Result<String> {
    // Inspect before the shared loader: its non-Unicode override handling would
    // otherwise fall through to file pairing. Presence is never approval.
    match std::env::var(ipc_pairing::ENV_OVERRIDE) {
        Ok(value) => {
            ipc_pairing::validate(&value).map_err(|_| Diagnostic::OverrideInvalid)?;
            return Ok(value);
        }
        Err(std::env::VarError::NotUnicode(_)) => {
            return Err(Diagnostic::OverrideInvalid.into());
        }
        Err(std::env::VarError::NotPresent) => {}
    }
    if !cfg!(unix) {
        return Err(Diagnostic::StorageUnsupported.into());
    }
    ipc_pairing::load_paired().map_err(|error| {
        let diagnostic = match error {
            ipc_pairing::PairingError::Invalid(_) => Diagnostic::PairingUnsafe,
            ipc_pairing::PairingError::NoUserDirectory => Diagnostic::NoUserDirectory,
            ipc_pairing::PairingError::NoSecureRandom => Diagnostic::StorageUnsupported,
            ipc_pairing::PairingError::Io(error) => match error.kind() {
                io::ErrorKind::NotFound => Diagnostic::PairingMissing,
                io::ErrorKind::PermissionDenied => Diagnostic::PairingPermission,
                _ => Diagnostic::PairingIo,
            },
        };
        diagnostic.into()
    })
}

pub struct PhantomBridge;

impl PhantomBridge {
    /// Signal cancellation of the active materialize request, if any.
    /// Returns true only when the signal was delivered; repeated calls return false.
    /// Admission remains held until the owning future finishes or is dropped.
    /// The request connection is dropped and runtime cancellation is attempted, but
    /// neither a dropped connection nor an HTTP acknowledgement proves backend
    /// compute has stopped or data has been erased.
    pub fn cancel_active() -> bool {
        match cancel_slot().lock() {
            Ok(mut slot) => slot
                .as_mut()
                .and_then(|active| active.cancel_tx.take())
                .map(|tx| tx.send(()).is_ok())
                .unwrap_or(false),
            Err(_) => false,
        }
    }

    async fn abort_runtime_generation() -> Result<bool> {
        let response = client(Duration::from_secs(2))?
            .post(url("/cancel"))
            .bearer_auth(token()?)
            .send()
            .await
            .map_err(transport_error)?;
        let response = successful(response, Operation::Cancel)?
            .json::<CancelResponse>()
            .await
            .map_err(decode_error)?;
        Ok(response.cancelled)
    }

    /// Call the runtime to generate a preview suggestion for explicit context.
    pub async fn materialize(context: String) -> Result<String> {
        let (_lease, cancel_rx) = MaterializeLease::reserve()?;
        let client = client(Duration::from_secs(95))?;
        let token = token()?;
        let request = async {
            let resp = client
                .post(url("/materialize"))
                .bearer_auth(&token)
                .json(&MaterializeRequest { context })
                .send()
                .await
                .map_err(transport_error)?;
            let resp = successful(resp, Operation::Preview)?
                .json::<MaterializeResponse>()
                .await
                .map_err(decode_error)?;
            Ok::<String, anyhow::Error>(resp.suggestion)
        };
        tokio::select! {
            r = request => r,
            cancellation = cancel_rx => {
                match cancellation {
                    Ok(()) => {
                        // Best effort only; keep admission through acknowledgement.
                        let _ = Self::abort_runtime_generation().await;
                        Err(anyhow::anyhow!("Generation cancelled by the user"))
                    }
                    Err(_) => Err(anyhow::anyhow!("Materialize cancellation channel closed")),
                }
            }
        }
    }

    pub async fn readiness() -> Result<ReadinessResponse> {
        let response = client(Duration::from_secs(3))?
            .get(url("/readiness"))
            .bearer_auth(token()?)
            .send()
            .await
            .map_err(transport_error)?;
        Ok(successful(response, Operation::Readiness)?
            .json::<ReadinessResponse>()
            .await
            .map_err(decode_error)?)
    }

    /// Ping the runtime health endpoint (unauthenticated liveness only).
    #[allow(dead_code)]
    pub async fn ping() -> bool {
        let Ok(client) = client(Duration::from_secs(1)) else {
            return false;
        };
        client
            .get(url("/health"))
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false)
    }
}
