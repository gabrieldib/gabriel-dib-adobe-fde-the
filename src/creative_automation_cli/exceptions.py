"""
Domain-specific exceptions for the Creative Automation pipeline.

Catching these at the CLI entry point allows clean exit codes and targeted error
messages.  All exceptions inherit from ``CreativeAutomationError`` so callers can
also use a single broad catch when needed.
"""

from __future__ import annotations


class CreativeAutomationError(Exception):
    """Base exception for all pipeline errors."""


class ComplianceViolationError(CreativeAutomationError):
    """Raised when a strict brand or legal policy check blocks execution.

    Attributes
    ----------
    violations:
        Human-readable list of individual rule failures.
    """

    def __init__(self, message: str, violations: list[str] | None = None) -> None:
        super().__init__(message)
        self.violations: list[str] = violations or []


class ProviderGenerationError(CreativeAutomationError):
    """Raised when a GenAI backend (Gemini Developer, Vertex AI) fails."""


class ConfigurationError(CreativeAutomationError):
    """Raised when required configuration (policy files, env vars) is missing."""
