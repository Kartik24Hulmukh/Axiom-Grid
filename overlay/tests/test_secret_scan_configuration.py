from pathlib import Path

import tomllib


def test_provider_secret_detection_is_enabled_without_global_exemptions():
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / ".gitleaks.toml").read_text())
    assert config["extend"]["useDefault"] is True
    assert "allowlist" not in config
    rule = next(rule for rule in config["rules"] if rule["id"] == "melious-token")
    assert rule["keywords"] == ["sk-mel-"]
    assert "{32,}" in rule["regex"]