//! OS-protected per-user pairing replaces manual AXIOM_API_TOKEN provisioning.
//! Environment variables are process-global, so the scenarios run in one test.
use axiom_grid::api_security::{ipc_pairing, ApiToken, PairingError};
use std::fs;

#[cfg(unix)]
fn mode(path: &std::path::Path) -> u32 {
    use std::os::unix::fs::PermissionsExt;
    fs::metadata(path).unwrap().permissions().mode() & 0o777
}

#[test]
fn pairing_lifecycle_is_os_protected_and_fails_closed() {
    let dir = std::env::temp_dir().join(format!("axiom-grid-pairing-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    let file = dir.join("nested").join("ipc.token");
    std::env::remove_var(ipc_pairing::ENV_OVERRIDE);
    std::env::set_var(ipc_pairing::ENV_PAIRING_FILE, &file);
    assert_eq!(ApiToken::pairing_file_path().unwrap(), file);

    // Nothing paired yet: readers fail closed instead of inventing a token.
    assert!(matches!(ApiToken::load_paired(), Err(PairingError::Io(_))));

    // First runtime start pairs: 64 hex chars, private directory and file.
    ApiToken::load_or_create_paired().unwrap();
    let first = fs::read_to_string(&file).unwrap();
    assert!(ipc_pairing::validate(&first).is_ok());
    assert!(first.bytes().all(|b| b.is_ascii_hexdigit()) && first.len() == 64);
    #[cfg(unix)]
    {
        assert_eq!(mode(&dir.join("nested")), 0o700);
        assert_eq!(mode(&file), 0o600);
    }

    // The overlay reads the same token; restarts keep it stable.
    assert!(ApiToken::load_paired().is_ok());
    ApiToken::load_or_create_paired().unwrap();
    assert_eq!(fs::read_to_string(&file).unwrap(), first);

    // Overly permissive permissions are tightened, not trusted.
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&file, fs::Permissions::from_mode(0o644)).unwrap();
        fs::set_permissions(dir.join("nested"), fs::Permissions::from_mode(0o755)).unwrap();
        ApiToken::load_or_create_paired().unwrap();
        assert_eq!(mode(&file), 0o600);
        assert_eq!(mode(&dir.join("nested")), 0o700);
    }

    // A corrupt pairing file is rejected by readers and replaced by the runtime.
    fs::write(&file, "not-a-token\n").unwrap();
    assert!(matches!(
        ApiToken::load_paired(),
        Err(PairingError::Invalid(_))
    ));
    ApiToken::load_or_create_paired().unwrap();
    let replaced = fs::read_to_string(&file).unwrap();
    assert!(ipc_pairing::validate(&replaced).is_ok());
    assert_ne!(replaced, first);

    // Fresh tokens are random, never reused.
    assert_ne!(
        ipc_pairing::generate_random().unwrap(),
        ipc_pairing::generate_random().unwrap()
    );

    // Explicit environment override still wins (CI/tests) and is validated.
    std::env::set_var(ipc_pairing::ENV_OVERRIDE, "c".repeat(64));
    assert!(ApiToken::load_paired().is_ok());
    assert!(ApiToken::load_or_create_paired().is_ok());
    assert_eq!(fs::read_to_string(&file).unwrap(), replaced);
    std::env::set_var(ipc_pairing::ENV_OVERRIDE, "short");
    assert!(matches!(
        ApiToken::load_or_create_paired(),
        Err(PairingError::Invalid(_))
    ));
    std::env::remove_var(ipc_pairing::ENV_OVERRIDE);
    std::env::remove_var(ipc_pairing::ENV_PAIRING_FILE);
    let _ = fs::remove_dir_all(&dir);
}
