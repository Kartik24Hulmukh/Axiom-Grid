"""
Kairo Phantom — Security Filter (SPEC §S4 line 5)

Local prompt-injection classifier + PII detection/redaction.
BLOCKS on detection — never soft-warns.
Uses keyword patterns + heuristic scoring (not just regex).

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from kernel.core.contracts import ScanResult

# ---------------------------------------------------------------------------
# Injection classifier — keyword patterns with weighted scoring
# ---------------------------------------------------------------------------
# Each pattern carries a weight. If total score >= threshold, we BLOCK.


@dataclass(frozen=True)
class _InjectionSignal:
    """A weighted signal for injection detection."""
    pattern: re.Pattern[str]
    weight: float
    label: str


_INJECTION_THRESHOLD: Final[float] = 1.0

_INJECTION_SIGNALS: Final[tuple[_InjectionSignal, ...]] = (
    # --- Direct instruction overrides (high weight) ---
    _InjectionSignal(
        re.compile(r"ignore\s+(all\s+|previous\s+|your\s+|system\s+|safety\s+)*(instructions|guidelines|rules|prompts?)", re.IGNORECASE),
        weight=1.0, label="direct_override:ignore_previous",
    ),
    _InjectionSignal(
        re.compile(r"disregard\s+(your\s+)?(previous\s+|prior\s+)?instructions", re.IGNORECASE),
        weight=1.0, label="direct_override:disregard",
    ),
    _InjectionSignal(
        re.compile(r"forget\s+(everything|all)\s+(above|before|previous)", re.IGNORECASE),
        weight=1.0, label="direct_override:forget",
    ),
    _InjectionSignal(
        re.compile(r"override\s+(your\s+)?(safety|security|instructions|rules)", re.IGNORECASE),
        weight=1.0, label="direct_override:override_safety",
    ),
    _InjectionSignal(
        re.compile(r"do\s+not\s+follow\s+(any\s+of\s+)?(your\s+)?(programmed\s+)?rules", re.IGNORECASE),
        weight=1.0, label="direct_override:dont_follow_rules",
    ),
    _InjectionSignal(
        re.compile(r"new\s+(task|instructions?)\s*:", re.IGNORECASE),
        weight=0.6, label="direct_override:new_task",
    ),
    _InjectionSignal(
        re.compile(r"abandon\s+(the\s+)?(current|previous)", re.IGNORECASE),
        weight=0.6, label="direct_override:abandon_current",
    ),
    _InjectionSignal(
        re.compile(r"stop\s+being\s+a", re.IGNORECASE),
        weight=0.7, label="direct_override:stop_being",
    ),
    _InjectionSignal(
        re.compile(r"your\s+(real|true|actual)\s+purpose", re.IGNORECASE),
        weight=0.5, label="direct_override:real_purpose",
    ),
    _InjectionSignal(
        re.compile(r"(reveal|output|show|print)\s+(all\s+|your\s+|system\s+|the\s+)*(prompt|instructions|secrets|configuration|data)", re.IGNORECASE),
        weight=0.8, label="exfil:reveal_prompt",
    ),
    _InjectionSignal(
        re.compile(r"replace\s+(all\s+)?(outputs?|values?|text|responses?|answers?)\s*(?:with\b|[:=]|$)", re.IGNORECASE),
        weight=1.0, label="direct_override:replace_output",
    ),

    # --- Role-playing / jailbreak (high weight) ---
    _InjectionSignal(
        re.compile(r"you\s+are\s+(now\s+)?(DAN|an?\s+unrestricted)", re.IGNORECASE),
        weight=1.0, label="jailbreak:dan_unrestricted",
    ),
    _InjectionSignal(
        re.compile(r"(pretend|act\s+as)\s+(you\s+are\s+)?.*unrestricted", re.IGNORECASE),
        weight=1.0, label="jailbreak:pretend_unrestricted",
    ),
    _InjectionSignal(
        re.compile(r"jailbreak\s+mode", re.IGNORECASE),
        weight=1.0, label="jailbreak:explicit",
    ),
    _InjectionSignal(
        re.compile(r"(developer|maintenance|debug)\s*(\w+\s+)?mode", re.IGNORECASE),
        weight=1.0, label="jailbreak:dev_mode",
    ),
    _InjectionSignal(
        re.compile(r"no\s+(restrictions?|filters?|safety)", re.IGNORECASE),
        weight=0.6, label="jailbreak:no_restrictions",
    ),
    _InjectionSignal(
        re.compile(r"safety\s+(restrictions?|filters?)\s+(are\s+)?(disabled|removed|off)", re.IGNORECASE),
        weight=1.0, label="jailbreak:safety_disabled",
    ),
    _InjectionSignal(
        re.compile(r"without\s+restrictions\s+(or\s+)?filters?", re.IGNORECASE),
        weight=0.7, label="jailbreak:without_restrictions",
    ),
    _InjectionSignal(
        re.compile(r"unrestricted\s+mode", re.IGNORECASE),
        weight=0.7, label="jailbreak:unrestricted_mode",
    ),
    _InjectionSignal(
        re.compile(r"(disable|bypass)\s+(all\s+)?(content\s+|security\s+)?(filtering|filters?|safety|checks|override)", re.IGNORECASE),
        weight=0.8, label="jailbreak:disable_filtering",
    ),

    # --- Context manipulation (medium-high weight) ---
    _InjectionSignal(
        re.compile(r"\[SYSTEM\]", re.IGNORECASE),
        weight=0.7, label="context_manip:fake_system_tag",
    ),
    _InjectionSignal(
        re.compile(r"<<<\s*ADMIN\s*>>>", re.IGNORECASE),
        weight=0.8, label="context_manip:fake_admin_tag",
    ),
    _InjectionSignal(
        re.compile(r"(BEGIN|END)\s+(CONFIDENTIAL|SECRET)\s+INSTRUCTIONS?", re.IGNORECASE),
        weight=0.8, label="context_manip:fake_confidential",
    ),
    _InjectionSignal(
        re.compile(r"---\s*END\s+OF\s+DOCUMENT\s*---", re.IGNORECASE),
        weight=0.5, label="context_manip:fake_delimiter",
    ),
    _InjectionSignal(
        re.compile(r"</instruction>|<instruction>", re.IGNORECASE),
        weight=0.7, label="context_manip:xml_injection",
    ),
    _InjectionSignal(
        re.compile(r"system\s*:\s*(the\s+user|override|grant|disable)", re.IGNORECASE),
        weight=0.8, label="context_manip:fake_system_colon",
    ),
    _InjectionSignal(
        re.compile(r"User\s+input\s+ends\s+here", re.IGNORECASE),
        weight=0.7, label="context_manip:fake_user_end",
    ),
    _InjectionSignal(
        re.compile(r"new\s+system\s+instruction", re.IGNORECASE),
        weight=0.9, label="context_manip:new_system_instruction",
    ),

    # --- Indirect / obfuscated (medium weight, combine) ---
    _InjectionSignal(
        re.compile(r"base64\b.*\b(phrase|instruct|translate)", re.IGNORECASE),
        weight=0.5, label="indirect:base64_mention",
    ),
    _InjectionSignal(
        re.compile(r"aWdub3Jl", re.IGNORECASE),  # base64 of "ignore"
        weight=0.6, label="indirect:base64_ignore",
    ),
    _InjectionSignal(
        re.compile(r"<!--.*?(ignore|override|bypass|inject).*?-->", re.IGNORECASE | re.DOTALL),
        weight=0.8, label="indirect:html_comment_injection",
    ),
    _InjectionSignal(
        re.compile(r"i\.g.*?n\.o.*?r\.e", re.IGNORECASE),
        weight=1.0, label="indirect:dot_separated",
    ),
    _InjectionSignal(
        re.compile(r"prompt\s+injection", re.IGNORECASE),
        weight=0.5, label="indirect:self_referential",
    ),

    # --- Exfiltration / command injection ---
    _InjectionSignal(
        re.compile(r"(output|send|exfil)\s+.*\s+to\s+https?://", re.IGNORECASE),
        weight=0.8, label="exfil:url_output",
    ),
    _InjectionSignal(
        re.compile(r"execute\s+(the\s+following\s+)?(shell\s+)?command", re.IGNORECASE),
        weight=0.9, label="exfil:shell_command",
    ),
    _InjectionSignal(
        re.compile(r"(rm\s+-rf|/etc/passwd|eval\(|exec\()", re.IGNORECASE),
        weight=0.7, label="exfil:dangerous_command",
    ),

    # --- Pwned test ---
    _InjectionSignal(
        re.compile(r"(I\s+have\s+been|you\s+have\s+been)\s+pwned", re.IGNORECASE),
        weight=0.7, label="indirect:pwned_test",
    ),
    _InjectionSignal(
        re.compile(r"repeat\s+after\s+me", re.IGNORECASE),
        weight=0.4, label="indirect:repeat_after_me",
    ),

    # --- Privilege claim ---
    _InjectionSignal(
        re.compile(r"I\s+am\s+the\s+(system\s+)?administrator", re.IGNORECASE),
        weight=0.5, label="privilege:admin_claim",
    ),
    _InjectionSignal(
        re.compile(r"I\s+authorize\s+this", re.IGNORECASE),
        weight=0.4, label="privilege:authorize_claim",
    ),
    _InjectionSignal(
        re.compile(r"(admin|user)\s+(has\s+)?(privileges|access)", re.IGNORECASE),
        weight=0.4, label="privilege:privilege_claim",
    ),
    _InjectionSignal(
        re.compile(r"grant\s+all\s+requests", re.IGNORECASE),
        weight=0.6, label="privilege:grant_all",
    ),
)

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------
# US SSN: ###-##-####
_SSN_RE: Final[re.Pattern[str]] = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b"
)

# Email
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# US Phone numbers: (###) ###-####, ###-###-####, ### ### ####
_PHONE_RE: Final[re.Pattern[str]] = re.compile(
    r"\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Simple name pattern: capitalized first + last (conservative)
_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Z][a-z]{1,20}\s[A-Z][a-z]{1,20}\b"
)

_PII_PATTERNS: Final[list[tuple[str, re.Pattern[str], str]]] = [
    ("ssn", _SSN_RE, "[SSN_REDACTED]"),
    ("email", _EMAIL_RE, "[EMAIL_REDACTED]"),
    ("phone", _PHONE_RE, "[PHONE_REDACTED]"),
    ("name", _NAME_RE, "[NAME_REDACTED]"),
]


# ---------------------------------------------------------------------------
# SecurityFilter implementation
# ---------------------------------------------------------------------------
class LocalSecurityFilter:
    """Local prompt-injection classifier + PII scanner.

    Implements the SecurityFilter Protocol.
    Uses weighted heuristic scoring — NOT just regex matching.
    BLOCKS on detection. Never soft-warns.
    """

    def __init__(
        self,
        *,
        injection_threshold: float = _INJECTION_THRESHOLD,
        enable_pii_scan: bool = True,
    ) -> None:
        self._injection_threshold = injection_threshold
        self._enable_pii_scan = enable_pii_scan

    def scan(self, text: str) -> ScanResult:
        """Scan text for prompt injection and PII. BLOCKS, never soft-warns."""
        if not text:
            return ScanResult(blocked=False, reasons=[])

        reasons: list[str] = []

        # Phase 1: injection classification via weighted scoring
        injection_reasons = self._classify_injection(text)
        reasons.extend(injection_reasons)

        # Phase 2: PII detection
        if self._enable_pii_scan:
            pii_reasons = self._detect_pii(text)
            reasons.extend(pii_reasons)

        blocked = len(reasons) > 0
        return ScanResult(blocked=blocked, reasons=reasons)

    def redact_pii(self, text: str) -> str:
        """Redact all detected PII from text before model sees it."""
        result = text
        for _label, pattern, replacement in _PII_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    def _classify_injection(self, text: str) -> list[str]:
        """Heuristic injection classifier with weighted scoring.

        Accumulates signal weights. If total >= threshold → BLOCK.
        Multiple weak signals can combine to trigger blocking.
        """
        total_score = 0.0
        triggered: list[str] = []

        for signal in _INJECTION_SIGNALS:
            if signal.pattern.search(text):
                total_score += signal.weight
                triggered.append(signal.label)

        if total_score >= self._injection_threshold:
            return [
                (f"INJECTION_BLOCKED: score={total_score:.2f} "
                f"(threshold={self._injection_threshold:.2f}), "
                f"signals=[{', '.join(triggered)}]")
            ]
        return []

    def _detect_pii(self, text: str) -> list[str]:
        """Detect PII in text using pattern matching."""
        found: list[str] = []
        for label, pattern, _repl in _PII_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                found.append(
                    f"PII_DETECTED: {label} ({len(matches)} occurrence(s))"
                )
        return found
