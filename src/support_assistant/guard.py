"""Guards decide what may enter or leave the assistant. Fail closed."""
from __future__ import annotations

from typing import Protocol


class GuardUnavailable(RuntimeError):
    """The guard could not give a verdict. Callers must treat this as 'no'."""


class Guard(Protocol):
    name: str

    def check_input(self, text: str) -> tuple[bool, list[str]]: ...
    def scan_chunk(self, text: str) -> tuple[bool, list[str]]: ...
    def redact_output(self, text: str) -> tuple[str, bool]: ...  # (text, blocked)


class NoGuard:
    """Baseline for comparison only. Lets everything through."""
    name = "none"

    def check_input(self, text):
        return True, []

    def scan_chunk(self, text):
        return True, []

    def redact_output(self, text):
        return text, False


class HttpGuard:
    """Uses a running Sentinel gateway (ai-sentinel /v1/scan and /v1/scan-output)."""
    name = "sentinel"

    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0):
        from ai_sentinel.client import SentinelClient  # optional dependency
        self._c = SentinelClient(base_url, api_key, timeout)

    def _scan(self, text):
        from ai_sentinel.client import SentinelError
        try:
            v = self._c.scan(text)
        except SentinelError as e:
            raise GuardUnavailable(str(e)) from e
        return v.get("action") == "ALLOW", list(v.get("reasons", []))

    def check_input(self, text):
        return self._scan(text)

    def scan_chunk(self, text):
        return self._scan(text)

    def redact_output(self, text):
        from ai_sentinel.client import SentinelError
        try:
            v = self._c.scan_output(text)
        except SentinelError as e:
            raise GuardUnavailable(str(e)) from e
        action = v.get("action")
        if action == "BLOCK":
            return "", True
        if action == "REDACT":
            return v.get("redacted_text", ""), False
        return text, False


class LocalGuard:
    """In-process Sentinel (no server): rule shield, plus the semantic router if sentinel-semantic is installed.
    Needs `pip install ai-sentinel` (and optionally sentinel-semantic). Same checks as the gateway, minus HTTP."""
    name = "sentinel-local"

    def __init__(self):
        from ai_sentinel.core.shield import SecurityShield
        from ai_sentinel.core.output_scanner import scan_output
        self._shield = SecurityShield(block_threshold=0.7)
        self._scan_output = scan_output
        try:
            from sentinel_semantic.router import SemanticRouter
            self._router = SemanticRouter(engine="keyword")
        except ImportError:
            self._router = None

    def _scan(self, text):
        v = self._shield.inspect(prompt=text)
        blocked = v.action == "BLOCK"
        reasons = list(getattr(v, "reasons", []) or [])
        if self._router is not None and self._router.route(text).guardrail_profile == "maximum_security_block":
            blocked, reasons = True, reasons + ["semantic"]
        return (not blocked), reasons

    def check_input(self, text):
        return self._scan(text)

    def scan_chunk(self, text):
        return self._scan(text)

    def redact_output(self, text):
        v = self._scan_output(text)
        if v.action == "BLOCK":
            return "", True
        if v.action == "REDACT":
            return v.redacted_text, False
        return text, False
