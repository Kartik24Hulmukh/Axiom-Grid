//! Real-filesystem regressions; a separate test process isolates environment overrides.
#[cfg(unix)]
#[test]
fn pairing_rejects_symlinks_without_modifying_the_target() {
    use axiom_grid::api_security::ipc_pairing;
    use std::{
        fs,
        os::unix::fs::{symlink, PermissionsExt},
    };
    let dir = std::env::temp_dir().join(format!("axiom-symlink-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
    let target = dir.join("victim");
    fs::write(&target, "not a token").unwrap();
    let token = dir.join("ipc.token");
    symlink(&target, &token).unwrap();
    std::env::remove_var(ipc_pairing::ENV_OVERRIDE);
    std::env::set_var(ipc_pairing::ENV_PAIRING_FILE, &token);
    let result = ipc_pairing::load_or_create_paired();
    let unchanged = fs::read_to_string(&target).unwrap() == "not a token";
    assert!(result.is_err(), "symlink must fail closed");
    assert!(unchanged, "pairing must not overwrite a symlink target");
    fs::remove_file(&token).unwrap();
    fs::write(&target, "a".repeat(64)).unwrap();
    fs::set_permissions(&target, fs::Permissions::from_mode(0o600)).unwrap();
    fs::hard_link(&target, &token).unwrap();
    assert!(ipc_pairing::load_paired().is_err());
    assert!(ipc_pairing::load_or_create_paired().is_err());
    fs::remove_file(&token).unwrap();

    // Symlinked ancestor directories also fail closed, not just the final file.
    let alias = dir.join("alias");
    symlink(&dir, &alias).unwrap();
    std::env::set_var(ipc_pairing::ENV_PAIRING_FILE, alias.join("ipc.token"));
    assert!(ipc_pairing::load_or_create_paired().is_err());
    fs::remove_file(&alias).unwrap();
    std::env::set_var(ipc_pairing::ENV_PAIRING_FILE, &token);

    // A FIFO must fail promptly instead of blocking the runtime at startup.
    use std::{ffi::CString, os::unix::ffi::OsStrExt};
    let fifo = CString::new(token.as_os_str().as_bytes()).unwrap();
    assert_eq!(unsafe { libc::mkfifo(fifo.as_ptr(), 0o600) }, 0);
    let started = std::time::Instant::now();
    assert!(ipc_pairing::load_or_create_paired().is_err());
    assert!(started.elapsed() < std::time::Duration::from_secs(1));
    fs::remove_file(&token).unwrap();

    // Readers enforce the full length; oversized files never get prefix-trusted.
    fs::write(&token, "a".repeat(2048)).unwrap();
    fs::set_permissions(&token, fs::Permissions::from_mode(0o600)).unwrap();
    assert!(ipc_pairing::load_paired().is_err());
    assert!(ipc_pairing::load_or_create_paired().is_err());
    assert_eq!(fs::metadata(&token).unwrap().len(), 2048);
    fs::remove_file(&token).unwrap();

    // Writable non-sticky ancestors cannot redirect future pairing consumers.
    let unsafe_parent = dir.join("unsafe-parent");
    fs::create_dir(&unsafe_parent).unwrap();
    fs::set_permissions(&unsafe_parent, fs::Permissions::from_mode(0o777)).unwrap();
    std::env::set_var(
        ipc_pairing::ENV_PAIRING_FILE,
        unsafe_parent.join("private/ipc.token"),
    );
    assert!(ipc_pairing::load_or_create_paired().is_err());
    assert!(!unsafe_parent.join("private").exists());
    fs::remove_dir(&unsafe_parent).unwrap();
    std::env::set_var(ipc_pairing::ENV_PAIRING_FILE, &token);

    // Lock contention fails within a bounded budget, and close releases it.
    use std::os::fd::AsRawFd;
    let locked = fs::File::open(&dir).unwrap();
    assert_eq!(
        unsafe { libc::flock(locked.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) },
        0
    );
    let started = std::time::Instant::now();
    assert!(ipc_pairing::load_or_create_paired().is_err());
    assert!(started.elapsed() >= std::time::Duration::from_secs(2));
    assert!(started.elapsed() < std::time::Duration::from_secs(4));
    assert!(!token.exists());
    drop(locked);

    // Concurrent independent processes see one fully published credential.
    let mut children = Vec::new();
    for _ in 0..16 {
        children.push(
            std::process::Command::new(std::env::current_exe().unwrap())
                .args(["--exact", "pairing_child", "--nocapture"])
                .env("AXIOM_PAIRING_CHILD", "1")
                .stdout(std::process::Stdio::null())
                .spawn()
                .unwrap(),
        );
    }
    for mut child in children {
        assert!(child.wait().unwrap().success());
    }
    let stable = ipc_pairing::load_paired().unwrap();
    assert_eq!(stable, ipc_pairing::load_or_create_paired().unwrap());
    assert_eq!(
        fs::read_dir(&dir).unwrap().count(),
        2,
        "no temporary credentials remain"
    );
    fs::remove_dir_all(&dir).unwrap();
}

#[cfg(unix)]
#[test]
fn pairing_child() {
    if std::env::var_os("AXIOM_PAIRING_CHILD").is_none() {
        return;
    }
    use axiom_grid::api_security::ipc_pairing;
    let first = ipc_pairing::load_or_create_paired().unwrap();
    for _ in 0..20 {
        assert_eq!(first, ipc_pairing::load_or_create_paired().unwrap());
        assert_eq!(first, ipc_pairing::load_paired().unwrap());
    }
}
