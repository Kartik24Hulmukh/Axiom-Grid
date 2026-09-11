//! Per-user, OS-protected IPC pairing token shared by the runtime and the overlay.
//!
//! The token is 32 random bytes encoded as 64 lowercase hex characters. It is
//! persisted in a per-user location that the operating system already protects
//! (mode `0700` directory, mode `0600` file on Unix). `AXIOM_API_TOKEN` remains an
//! explicit override for CI and tests; when it is unset, both processes pair via
//! the file and no secret ever appears in a process environment or shell history.
//!
//! Unix filesystem operations use descriptor-relative, no-follow opens and
//! serialized atomic publication. Both consumers include this same implementation.
//! File pairing on other platforms fails closed until protected storage is implemented.
use std::{fmt, io, path::PathBuf};

#[cfg(unix)]
use std::{fs, io::Read};

/// Explicit override honoured for CI and tests.
pub const ENV_OVERRIDE: &str = "AXIOM_API_TOKEN";
/// Test/deployment override for the pairing file location.
pub const ENV_PAIRING_FILE: &str = "AXIOM_PAIRING_FILE";
/// Length of the hex-encoded token.
pub const TOKEN_LEN: usize = 64;
const RANDOM_BYTES: usize = TOKEN_LEN / 2;
const DIR_NAME: &str = "axiom-grid";
const FILE_NAME: &str = "ipc.token";

#[derive(Debug)]
pub enum PairingError {
    /// The token (from the environment or the pairing file) is malformed.
    Invalid(&'static str),
    /// No per-user directory could be resolved on this platform.
    NoUserDirectory,
    /// Secure random generation is not available on this platform.
    NoSecureRandom,
    /// Filesystem error while reading or writing the pairing file.
    Io(io::Error),
}
impl fmt::Display for PairingError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Invalid(msg) => f.write_str(msg),
            Self::NoUserDirectory => {
                f.write_str("No per-user directory is available for the IPC pairing token")
            }
            Self::NoSecureRandom => f.write_str(
                "Secure random generation is unavailable on this platform; set AXIOM_API_TOKEN",
            ),
            Self::Io(err) => write!(f, "IPC pairing file error: {err}"),
        }
    }
}
impl std::error::Error for PairingError {}
impl From<io::Error> for PairingError {
    fn from(err: io::Error) -> Self {
        Self::Io(err)
    }
}

/// Validate the canonical token shape: exactly 64 ASCII hex digits.
pub fn validate(value: &str) -> Result<(), PairingError> {
    if value.len() != TOKEN_LEN || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(PairingError::Invalid(
            "IPC token must be 64 hexadecimal characters (32 random bytes)",
        ));
    }
    Ok(())
}

fn non_empty_env(name: &str) -> Option<PathBuf> {
    std::env::var_os(name)
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
}
/// Resolve the per-user pairing file path without touching the filesystem.
///
/// Unix: `$XDG_RUNTIME_DIR/axiom-grid/ipc.token` (per-UID tmpfs), then
/// `$XDG_CONFIG_HOME/axiom-grid/ipc.token`, then `$HOME/.config/axiom-grid/ipc.token`.
/// Windows: `%LOCALAPPDATA%\AxiomGrid\ipc.token`, then `%USERPROFILE%\.axiom-grid\ipc.token`.
/// `AXIOM_PAIRING_FILE` overrides all of the above (tests, custom deployments).
pub fn pairing_file_path() -> Result<PathBuf, PairingError> {
    if let Some(explicit) = non_empty_env(ENV_PAIRING_FILE) {
        return Ok(explicit);
    }
    if cfg!(windows) {
        if let Some(dir) = non_empty_env("LOCALAPPDATA") {
            return Ok(dir.join("AxiomGrid").join(FILE_NAME));
        }
        if let Some(dir) = non_empty_env("USERPROFILE") {
            return Ok(dir.join(".axiom-grid").join(FILE_NAME));
        }
        return Err(PairingError::NoUserDirectory);
    }
    for var in ["XDG_RUNTIME_DIR", "XDG_CONFIG_HOME"] {
        if let Some(dir) = non_empty_env(var) {
            return Ok(dir.join(DIR_NAME).join(FILE_NAME));
        }
    }
    if let Some(home) = non_empty_env("HOME") {
        return Ok(home.join(".config").join(DIR_NAME).join(FILE_NAME));
    }
    Err(PairingError::NoUserDirectory)
}

/// Generate a fresh 64-hex token from the operating system CSPRNG.
pub fn generate_random() -> Result<String, PairingError> {
    let mut bytes = [0u8; RANDOM_BYTES];
    fill_random(&mut bytes)?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

#[cfg(unix)]
fn fill_random(buf: &mut [u8]) -> Result<(), PairingError> {
    fs::File::open("/dev/urandom")?.read_exact(buf)?;
    Ok(())
}
#[cfg(not(unix))]
fn fill_random(_buf: &mut [u8]) -> Result<(), PairingError> {
    Err(PairingError::NoSecureRandom)
}

#[cfg(unix)]
#[path = "ipc_pairing_unix.rs"]
mod unix;

fn file_pairing(create: bool) -> Result<String, PairingError> {
    #[cfg(unix)]
    {
        unix::load(&pairing_file_path()?, create)
    }
    #[cfg(not(unix))]
    {
        let _ = create;
        Err(PairingError::Invalid(
            "Protected file pairing is unsupported on this platform; use an explicit IPC token",
        ))
    }
}

/// Load the explicit override or securely read the existing per-user credential.
/// Unsafe permissions, links and malformed files fail closed; never repair a
/// possibly disclosed credential silently. See the pairing recovery runbook.
pub fn load_paired() -> Result<String, PairingError> {
    if let Ok(env_token) = std::env::var(ENV_OVERRIDE) {
        validate(&env_token)?;
        return Ok(env_token);
    }
    file_pairing(false)
}

/// Serialize first-time pairing and atomically publish a fully written token.
/// Existing credentials are validated identically by runtime and overlay.
pub fn load_or_create_paired() -> Result<String, PairingError> {
    if let Ok(env_token) = std::env::var(ENV_OVERRIDE) {
        validate(&env_token)?;
        return Ok(env_token);
    }
    file_pairing(true)
}
