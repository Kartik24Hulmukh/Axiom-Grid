use phantom_core::lan_sync::{LanSync, LAN_SYNC_DISABLED_REASON};

#[test]
fn network_entry_points_fail_closed_before_io() {
    let vault = tempfile::tempdir().unwrap();
    let sync = LanSync::new(vault.path());

    for error in [
        sync.discover_peers(0).unwrap_err(),
        sync.pull_from_peer("not-a-socket").unwrap_err(),
        sync.start_server().unwrap_err(),
    ] {
        assert_eq!(error.to_string(), LAN_SYNC_DISABLED_REASON);
    }
}

#[test]
fn source_contains_no_lan_socket_implementation() {
    let source = include_str!("../src/lan_sync.rs");
    for forbidden in [
        "std::net",
        "TcpListener",
        "TcpStream",
        "UdpSocket",
        "0.0.0.0",
        "255.255.255.255",
    ] {
        assert!(
            !source.contains(forbidden),
            "LAN transport primitive reintroduced: {forbidden}"
        );
    }
}