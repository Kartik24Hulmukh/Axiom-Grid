"""
Tests for TieredInferenceGateway.
"""

import shutil
import tempfile
import pytest
from pathlib import Path

from kernel.core.contracts import InferenceTier, InferenceResult
from kernel.sidecar.inference_gateway import (
    TieredInferenceGateway,
    AirGapViolationError,
)


@pytest.fixture
def temp_log_dir():
    """Fixture to create and clean up a temporary log directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_test_mode_completion(temp_log_dir, monkeypatch):
    """Test that completion works in test mode with correct return values."""
    monkeypatch.setenv("KAIRO_GATEWAY_TEST_MODE", "true")
    gateway = TieredInferenceGateway(tier3_enabled=False, log_dir=temp_log_dir)

    result = gateway.complete(role="extractor", prompt="Test prompt", tier=InferenceTier.TIER1_LOCAL)
    assert isinstance(result, InferenceResult)
    assert result.call_id != ""
    assert "[TEST_MODE]" in result.text
    assert "role=extractor" in result.text
    assert "tier=TIER1_LOCAL" in result.text


def test_tier3_blocked_when_off(temp_log_dir, monkeypatch):
    """Test that Tier3 calls raise AirGapViolationError if tier3_enabled is False."""
    monkeypatch.setenv("KAIRO_GATEWAY_TEST_MODE", "true")
    gateway = TieredInferenceGateway(tier3_enabled=False, log_dir=temp_log_dir)

    with pytest.raises(AirGapViolationError) as exc_info:
        gateway.complete(role="extractor", prompt="Test prompt", tier=InferenceTier.TIER3_CLOUD)
    
    assert "Tier3 (cloud) is disabled" in str(exc_info.value)


def test_tier3_allowed_when_on(temp_log_dir, monkeypatch):
    """Test that Tier3 calls succeed in test mode if tier3_enabled is True."""
    monkeypatch.setenv("KAIRO_GATEWAY_TEST_MODE", "true")
    gateway = TieredInferenceGateway(tier3_enabled=True, log_dir=temp_log_dir)

    result = gateway.complete(role="extractor", prompt="Test prompt", tier=InferenceTier.TIER3_CLOUD)
    assert isinstance(result, InferenceResult)
    assert "tier=TIER3_CLOUD" in result.text


def test_invalid_role(temp_log_dir):
    """Test that invalid roles raise ValueError."""
    gateway = TieredInferenceGateway(log_dir=temp_log_dir)
    with pytest.raises(ValueError) as exc_info:
        gateway.complete(role="invalid_role", prompt="Hello")
    assert "Invalid role" in str(exc_info.value)


def test_empty_prompt(temp_log_dir):
    """Test that empty prompt raises ValueError."""
    gateway = TieredInferenceGateway(log_dir=temp_log_dir)
    with pytest.raises(ValueError) as exc_info:
        gateway.complete(role="extractor", prompt="")
    assert "Prompt must be non-empty" in str(exc_info.value)


def test_call_logging(temp_log_dir, monkeypatch):
    """Test that every call is appended to calls.jsonl in log_dir."""
    monkeypatch.setenv("KAIRO_GATEWAY_TEST_MODE", "true")
    gateway = TieredInferenceGateway(tier3_enabled=False, log_dir=temp_log_dir)

    # Initial state: no calls logged
    log_file = Path(temp_log_dir) / "calls.jsonl"
    assert not log_file.exists()

    # Successful call
    gateway.complete(role="extractor", prompt="Hello", tier=InferenceTier.TIER1_LOCAL)
    assert log_file.exists()

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1
    assert "extractor" in lines[0]
    assert "TIER1_LOCAL" in lines[0]

    # Blocked call
    with pytest.raises(AirGapViolationError):
        gateway.complete(role="extractor", prompt="Hello", tier=InferenceTier.TIER3_CLOUD)

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 2
    assert "AIR_GAP_BLOCKED" in lines[1]
