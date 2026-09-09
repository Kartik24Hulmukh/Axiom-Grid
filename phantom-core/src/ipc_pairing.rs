//! Per-user, OS-protected IPC pairing token shared by the runtime and the overlay.
//!
//! The token is 32 random bytes encoded as 64 lowercase hex characters. It is
//! persisted in a per-user location that the operating system already protects
//! (mode `0700` directory, mode `0600` file on Unix). `AXIOM_API_TOKEN` remains an
//! explicit override for CI and tests; when it is unset, both processes pair via
//! the file and no secret ever appears in a process environment or shell history.
//!
//! This module is intentionally `std`-only so both crates can include it via
//! `#[path]` without sharing a dependency graph.
use std::{
    fmt, fs,
    io::{self, Read, Write},
    path::{Path, PathBuf},
};

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
fn restrict_permissions(path: &Path, mode: u32) -> io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    if fs::metadata(path)?.permissions().mode() & 0o777 != mode {
        fs::set_permissions(path, fs::Permissions::from_mode(mode))?;
    }
    Ok(())
}
#[cfg(not(unix))]
fn restrict_permissions(_path: &Path, _mode: u32) -> io::Result<()> {
    Ok(())
}

fn read_token_file(path: &Path) -> io::Result<String> {
    let mut raw = String::new();
    fs::File::open(path)?.take(1024).read_to_string(&mut raw)?;
    Ok(raw.trim().to_owned())
}

/// Read a previously paired token from `AXIOM_API_TOKEN` or the pairing file.
/// Fails closed when neither is present or the value is malformed.
pub fn load_paired() -> Result<String, PairingError> {
    if let Ok(env_token) = std::env::var(ENV_OVERRIDE) {
        validate(&env_token)?;
        return Ok(env_token);
    }
    let token = read_token_file(&pairing_file_path()?)?;
    validate(&token)?;
    Ok(token)
}

/// Load the paired token, creating a fresh OS-protected one when none exists.
/// Existing permissive permissions are tightened to `0700` / `0600`; a corrupt
/// pairing file is replaced rather than trusted.
pub fn load_or_create_paired() -> Result<String, PairingError> {
    if let Ok(env_token) = std::env::var(ENV_OVERRIDE) {
        validate(&env_token)?;
        return Ok(env_token);
    }
    let path = pairing_file_path()?;
    let dir = path.parent().ok_or(PairingError::NoUserDirectory)?;
    fs::create_dir_all(dir)?;
    restrict_permissions(dir, 0o700)?;
    match read_token_file(&path) {
        Ok(existing) if validate(&existing).is_ok() => {
            restrict_permissions(&path, 0o600)?;
            return Ok(existing);
        }
        Ok(_) => {}
        Err(err) if err.kind() == io::ErrorKind::NotFound => {}
        Err(err) => return Err(err.into()),
    }
    let token = generate_random()?;
    let mut options = fs::OpenOptions::new();
    options.write(true).create(true).truncate(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(&path)?;
    file.write_all(token.as_bytes())?;
    file.sync_all()?;
    restrict_permissions(&path, 0o600)?;
    Ok(token)
}
