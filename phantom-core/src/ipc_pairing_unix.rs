//! Descriptor-relative Unix pairing. Never follow a path supplied as a link.
use super::{generate_random, validate, PairingError, TOKEN_LEN};
use std::{
    ffi::{CString, OsStr},
    fs::File,
    io::{self, Read, Write},
    os::{
        fd::{AsRawFd, FromRawFd},
        unix::{ffi::OsStrExt, fs::MetadataExt},
    },
    path::{Component, Path},
    time::{Duration, Instant},
};

fn name(value: &OsStr) -> Result<CString, PairingError> {
    CString::new(value.as_bytes()).map_err(|_| PairingError::Invalid("NUL in pairing path"))
}

fn open_at(dir: &File, name: &CString, flags: i32, mode: libc::mode_t) -> io::Result<File> {
    // SAFETY: valid directory descriptor and NUL-terminated path; the returned
    // descriptor is owned exactly once. O_NOFOLLOW rejects final symlinks.
    let fd = unsafe {
        libc::openat(
            dir.as_raw_fd(),
            name.as_ptr(),
            flags | libc::O_CLOEXEC | libc::O_NOFOLLOW,
            mode,
        )
    };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(unsafe { File::from_raw_fd(fd) })
}

fn private_directory(path: &Path, create: bool) -> Result<File, PairingError> {
    let absolute = if path.is_absolute() {
        path.to_owned()
    } else {
        std::env::current_dir()?.join(path)
    };
    let mut dir = File::open("/")?;
    let parts: Vec<_> = absolute.components().collect();
    let uid = unsafe { libc::geteuid() };
    for part in parts {
        let component = match part {
            Component::RootDir | Component::CurDir => continue,
            Component::Normal(value) => name(value)?,
            _ => {
                return Err(PairingError::Invalid(
                    "Parent traversal is not allowed in pairing paths",
                ))
            }
        };
        let flags = libc::O_RDONLY | libc::O_DIRECTORY;
        let parent = dir.metadata()?;
        // A root-owned sticky temporary directory is a safe container for an
        // already owner-validated private child; other writable ancestors can
        // redirect future consumers to another credential and must be rejected.
        let sticky_root = parent.uid() == 0 && parent.mode() & 0o1000 != 0;
        if (parent.uid() != 0 && parent.uid() != uid)
            || (parent.mode() & 0o022 != 0 && !sticky_root)
        {
            return Err(PairingError::Invalid(
                "Untrusted pairing directory ancestor",
            ));
        }
        dir = match open_at(&dir, &component, flags, 0) {
            Ok(next) => next,
            Err(e) if create && e.kind() == io::ErrorKind::NotFound => {
                // SAFETY: directory is pinned by an owned descriptor. A racing
                // creator is accepted only after a subsequent no-follow open.
                if unsafe { libc::mkdirat(dir.as_raw_fd(), component.as_ptr(), 0o700) } < 0 {
                    let error = io::Error::last_os_error();
                    if error.kind() != io::ErrorKind::AlreadyExists {
                        return Err(error.into());
                    }
                }
                open_at(&dir, &component, flags, 0)?
            }
            Err(e) => return Err(e.into()),
        };
    }
    let metadata = dir.metadata()?;
    // SAFETY: geteuid takes no arguments and cannot fail.
    if metadata.uid() != unsafe { libc::geteuid() } || metadata.mode() & 0o777 != 0o700 {
        return Err(PairingError::Invalid(
            "Pairing directory must be owned by this user with mode 0700",
        ));
    }
    Ok(dir)
}

fn lock(dir: &File) -> Result<(), PairingError> {
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        // SAFETY: the descriptor remains alive for the whole transaction. Closing
        // it releases flock even after an error or process crash (no stale lock).
        if unsafe { libc::flock(dir.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } == 0 {
            return Ok(());
        }
        let e = io::Error::last_os_error();
        if e.kind() != io::ErrorKind::WouldBlock && e.kind() != io::ErrorKind::Interrupted {
            return Err(e.into());
        }
        if Instant::now() >= deadline {
            return Err(
                io::Error::new(io::ErrorKind::TimedOut, "IPC pairing busy; retry startup").into(),
            );
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

fn read(dir: &File, filename: &CString) -> Result<String, PairingError> {
    // O_NONBLOCK also prevents an attacker-controlled FIFO from hanging startup.
    let mut file = open_at(dir, filename, libc::O_RDONLY | libc::O_NONBLOCK, 0)?;
    let m = file.metadata()?;
    if !m.is_file()
        || m.nlink() != 1
        || m.uid() != unsafe { libc::geteuid() }
        || m.mode() & 0o777 != 0o600
    {
        return Err(PairingError::Invalid(
            "Pairing token must be a private, single-link regular file owned by this user",
        ));
    }
    if m.len() != TOKEN_LEN as u64 {
        return Err(PairingError::Invalid(
            "Invalid pairing token length; explicit recovery required",
        ));
    }
    let mut token = String::new();
    (&mut file)
        .take((TOKEN_LEN + 1) as u64)
        .read_to_string(&mut token)?;
    validate(&token)?;
    Ok(token)
}

pub(super) fn load(path: &Path, create: bool) -> Result<String, PairingError> {
    let filename = name(path.file_name().ok_or(PairingError::NoUserDirectory)?)?;
    let dir = private_directory(path.parent().ok_or(PairingError::NoUserDirectory)?, create)?;
    lock(&dir)?;
    match read(&dir, &filename) {
        Ok(token) => return Ok(token),
        Err(PairingError::Io(e)) if create && e.kind() == io::ErrorKind::NotFound => {}
        Err(e) => return Err(e),
    }
    let token = generate_random()?;
    // The temporary name is independent of the secret. Never put token bytes in
    // filenames, diagnostics or environment variables.
    let temporary = name(OsStr::new(&format!(".ipc-{}.tmp", generate_random()?)))?;
    let mut file = open_at(
        &dir,
        &temporary,
        libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL,
        0o600,
    )?;
    let result = (|| -> Result<(), PairingError> {
        file.write_all(token.as_bytes())?;
        file.sync_all()?;
        // SAFETY: both names are NUL-terminated and relative to the pinned private
        // directory. Cooperating readers/writers hold the same directory lock.
        if unsafe {
            libc::renameat(
                dir.as_raw_fd(),
                temporary.as_ptr(),
                dir.as_raw_fd(),
                filename.as_ptr(),
            )
        } < 0
        {
            return Err(io::Error::last_os_error().into());
        }
        dir.sync_all()?;
        Ok(())
    })();
    if result.is_err() {
        // SAFETY: cleanup affects only our random temporary name, never the token.
        unsafe {
            libc::unlinkat(dir.as_raw_fd(), temporary.as_ptr(), 0);
        }
    }
    result?;
    // Revalidate actual permissions (including unusual restrictive umasks).
    read(&dir, &filename)
}
