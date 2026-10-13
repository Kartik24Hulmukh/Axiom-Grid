"""Release builds must not expose the unauthenticated legacy LAN transport."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_lan_sync_network_entry_points_fail_closed_in_source():
    source = (ROOT / "phantom-core/src/lan_sync.rs").read_text()
    assert source.count("network_sync_disabled()") == 3
    assert "LAN_SYNC_DISABLED_REASON" in source
    for forbidden in (
        "std::net",
        "TcpListener",
        "TcpStream",
        "UdpSocket",
        "0.0.0.0",
        "255.255.255.255",
    ):
        assert forbidden not in source


def test_cli_and_compliance_docs_do_not_advertise_lan_sync():
    main = (ROOT / "phantom-core/src/main.rs").read_text()
    compliance = (ROOT / "docs/enterprise/SOC2_READINESS.md").read_text()
    assert "Unavailable pending authenticated encrypted pairing" in main
    assert "LAN memory sync is unavailable" in compliance