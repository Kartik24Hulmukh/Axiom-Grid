"""
Kairo Phantom — Tiered Inference Gateway (SPEC §S4 line 3)

Routes inference to Tier1 (local LiteLLM/Ollama) or Tier3 (cloud).
Tier3 is DEFAULT OFF. Air-gap safe: cloud calls raise when disabled.
Every call is logged with a unique call_id for provenance.

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from kernel.core.contracts import InferenceResult, InferenceTier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VALID_ROLES: Final[frozenset[str]] = frozenset({"router", "extractor", "reasoner"})
_DEFAULT_LITELLM_BASE: Final[str] = "http://127.0.0.1:4000"
_DEFAULT_LOG_DIR: Final[str] = os.path.join(os.getcwd(), ".kairo", "inference_logs")
_TEST_MODE_ENV: Final[str] = "KAIRO_GATEWAY_TEST_MODE"


class InferenceGatewayError(Exception):
    """Raised when the inference backend is unavailable or misconfigured."""


class AirGapViolationError(InferenceGatewayError):
    """Raised when a cloud call is attempted while Tier3 is disabled."""


class TieredInferenceGateway:
    """Tiered inference gateway implementing the InferenceGateway Protocol.

    Tier1 (on-device via LiteLLM proxy) is the default.
    Tier3 (cloud) is disabled by default — enable explicitly.
    """

    def __init__(
        self,
        *,
        tier3_enabled: bool = False,
        litellm_base_url: str = _DEFAULT_LITELLM_BASE,
        log_dir: str | None = None,
        tier1_model: str = "ollama/llama3.2",
        tier3_model: str = "gpt-4o-mini",
    ) -> None:
        self._tier3_enabled = tier3_enabled
        self._litellm_base_url = litellm_base_url.rstrip("/")
        self._log_dir = Path(log_dir) if log_dir else (
            Path(os.environ["AXIOM_STATE_DIR"]) / "inference_logs"
            if os.environ.get("AXIOM_STATE_DIR") else Path(_DEFAULT_LOG_DIR)
        )
        self._tier1_model = tier1_model
        self._tier3_model = tier3_model
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # -- Protocol method ----------------------------------------------------
    def complete(
        self,
        role: str,
        prompt: str,
        tier: InferenceTier = InferenceTier.TIER1_LOCAL,
    ) -> InferenceResult:
        """Execute a completion request through the tiered gateway."""
        if role not in _VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of: {sorted(_VALID_ROLES)}"
            )
        if not prompt or not prompt.strip():
            raise ValueError("Prompt must be non-empty.")

        call_id = str(uuid.uuid4())

        # Air-gap enforcement
        if tier == InferenceTier.TIER3_CLOUD and not self._tier3_enabled:
            self._log_call(call_id, role, tier, prompt, error="AIR_GAP_BLOCKED")
            raise AirGapViolationError(
                f"Tier3 (cloud) is disabled. call_id={call_id}. "
                "Enable tier3_enabled=True to allow cloud inference."
            )

        # Test mode: deterministic response for offline testing
        if os.environ.get(_TEST_MODE_ENV, "").lower() in ("1", "true", "yes"):
            return self._test_mode_complete(call_id, role, prompt, tier)

        # Real inference via LiteLLM
        return self._litellm_complete(call_id, role, prompt, tier)

    # -- Internal: LiteLLM completion ----------------------------------------
    def _litellm_complete(
        self,
        call_id: str,
        role: str,
        prompt: str,
        tier: InferenceTier,
    ) -> InferenceResult:
        """Call the LiteLLM proxy for real inference."""
        import urllib.error
        import urllib.request

        model = self._tier1_model if tier == InferenceTier.TIER1_LOCAL else self._tier3_model
        url = f"{self._litellm_base_url}/v1/chat/completions"

        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": f"You are a Kairo Phantom {role}."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            self._log_call(call_id, role, tier, prompt, error=str(exc))
            raise InferenceGatewayError(
                f"LiteLLM/Ollama unavailable at {self._litellm_base_url}. "
                f"call_id={call_id}. "
                f"Ensure LiteLLM proxy is running. Error: {exc}"
            ) from exc

        text = data["choices"][0]["message"]["content"]
        result = InferenceResult(text=text, call_id=call_id)
        self._log_call(call_id, role, tier, prompt, response_text=text)
        return result

    # -- Internal: test mode --------------------------------------------------
    def _test_mode_complete(
        self,
        call_id: str,
        role: str,
        prompt: str,
        tier: InferenceTier,
    ) -> InferenceResult:
        """Deterministic test-mode response. NOT for production use.

        This is clearly marked as test-only. The response is a stable,
        deterministic string derived from the role and prompt length.
        """
        # Deterministic but non-trivial response for meaningful test assertions
        text = (
            f"[TEST_MODE] role={role} tier={tier.name} "
            f"prompt_len={len(prompt)} "
            f"echo={prompt[:80]}"
        )
        result = InferenceResult(text=text, call_id=call_id)
        self._log_call(
            call_id, role, tier, prompt,
            response_text=text, test_mode=True,
        )
        return result

    # -- Internal: call logging -----------------------------------------------
    def _log_call(
        self,
        call_id: str,
        role: str,
        tier: InferenceTier,
        prompt: str,
        *,
        response_text: str | None = None,
        error: str | None = None,
        test_mode: bool = False,
    ) -> None:
        """Append a structured log entry for provenance."""
        entry = {
            "call_id": call_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "tier": tier.name,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:200],
            "response_length": len(response_text) if response_text else 0,
            "response_preview": response_text[:200] if response_text else None,
            "error": error,
            "test_mode": test_mode,
        }
        log_file = self._log_dir / "calls.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.warning("Failed to write inference log: %s", exc)

    # -- Inspection -----------------------------------------------------------
    @property
    def tier3_enabled(self) -> bool:
        return self._tier3_enabled

    @property
    def log_dir(self) -> Path:
        return self._log_dir
