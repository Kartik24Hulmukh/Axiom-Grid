//! Actual runtime process, real sockets and OS signals; no model required.
#[cfg(unix)]
#[test]
fn sigterm_drains_idle_and_stalled_connections_within_deadline() {
    use std::{
        io::{BufRead, BufReader, Read, Write},
        net::TcpStream,
        process::{Command, Stdio},
        sync::mpsc,
        time::{Duration, Instant},
    };
    struct ChildGuard(std::process::Child);
    impl Drop for ChildGuard {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
    for stalled in [false, true] {
        let mut child = ChildGuard(
            Command::new(env!("CARGO_BIN_EXE_axiom-grid"))
                .env("AXIOM_MODEL", "shutdown-test-no-inference")
                .env("AXIOM_MODEL_DIGEST", "a".repeat(64))
                .env("AXIOM_API_TOKEN", "a".repeat(64))
                .stdout(Stdio::null())
                .stderr(Stdio::piped())
                .spawn()
                .unwrap(),
        );
        // The health endpoint alone can belong to a different process already
        // listening on 7437. Wait for this child's post-bind startup message
        // before probing, and keep draining stderr until the child exits.
        let stderr = child.0.stderr.take().unwrap();
        let (startup_tx, startup_rx) = mpsc::sync_channel(1);
        let drain = std::thread::spawn(move || {
            let mut startup_tx = Some(startup_tx);
            for line in BufReader::new(stderr).lines() {
                let Ok(line) = line else { break };
                if line == "Axiom-Grid preview on 127.0.0.1:7437; explicit context; no automatic insertion" {
                    if let Some(tx) = startup_tx.take() {
                        let _ = tx.send(());
                    }
                }
            }
        });
        startup_rx
            .recv_timeout(Duration::from_secs(10))
            .expect("own runtime did not bind and announce startup (port 7437 must be free)");
        let start = Instant::now();
        loop {
            assert!(
                child.0.try_wait().unwrap().is_none(),
                "runtime exited before readiness (port 7437 must be free)"
            );
            if let Ok(mut conn) = TcpStream::connect("127.0.0.1:7437") {
                conn.set_read_timeout(Some(Duration::from_secs(1))).unwrap();
                conn.write_all(
                    b"GET /health HTTP/1.1\r\nHost: 127.0.0.1:7437\r\nConnection: close\r\n\r\n",
                )
                .unwrap();
                let mut response = String::new();
                conn.read_to_string(&mut response).unwrap();
                assert!(response.contains("200 OK"));
                break;
            }
            assert!(start.elapsed() < Duration::from_secs(10), "startup timeout");
            std::thread::sleep(Duration::from_millis(25));
        }
        let mut held = None;
        if stalled {
            let mut conn = TcpStream::connect("127.0.0.1:7437").unwrap();
            conn.write_all(format!("POST /materialize HTTP/1.1\r\nHost: 127.0.0.1:7437\r\nAuthorization: Bearer {}\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{{", "a".repeat(64)).as_bytes()).unwrap();
            held = Some(conn);
            std::thread::sleep(Duration::from_millis(100));
        }
        let start = Instant::now();
        // SAFETY: PID belongs to the live child owned by this guard.
        assert_eq!(unsafe { libc::kill(child.0.id() as i32, libc::SIGTERM) }, 0);
        loop {
            if let Some(status) = child.0.try_wait().unwrap() {
                assert!(status.success());
                break;
            }
            assert!(
                start.elapsed() < Duration::from_secs(8),
                "shutdown exceeded drain budget"
            );
            std::thread::sleep(Duration::from_millis(25));
        }
        drop(held);
        drain.join().unwrap();
    }
}
