from __future__ import annotations

import re
from dataclasses import dataclass, field

from .legal_policy import LegalChecksPolicy, LegalPolicy


@dataclass(slots=True)
class LegalCheckResult:
    passed: bool
    action: str
    flagged: bool
    should_block: bool
    hits: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "action": self.action,
            "flagged": self.flagged,
            "should_block": self.should_block,
            "hits": self.hits,
            "warnings": self.warnings,
            "violations": self.violations,
        }


def _checks_for_locale(policy: LegalPolicy, locale: str) -> LegalChecksPolicy:
    normalized = locale.lower().replace("-", "_")
    checks = LegalChecksPolicy(
        blocked_keywords=list(policy.checks.blocked_keywords),
        blocked_regex=list(policy.checks.blocked_regex),
    )

    override = policy.locale_overrides.get(normalized)
    if override is None and "_" in normalized:
        override = policy.locale_overrides.get(normalized.split("_", 1)[0])

    if override is not None:
        checks.blocked_keywords.extend(override.blocked_keywords)
        checks.blocked_regex.extend(override.blocked_regex)

    return checks


def _normalize_for_matching(text: str) -> str:
    separated = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    collapsed = re.sub(r"\s+", " ", separated)
    return collapsed.strip()


def evaluate_legal_text(text: str, locale: str, policy: LegalPolicy, strict_legal: bool = False) -> LegalCheckResult:
    checks = _checks_for_locale(policy, locale)
    normalized_text = _normalize_for_matching(text)
    lowered = normalized_text.lower()
    hits: list[str] = []

    for keyword in checks.blocked_keywords:
        if keyword.lower() in lowered:
            hits.append(f"keyword:{keyword}")

    for pattern in checks.blocked_regex:
        try:
            if re.search(pattern, normalized_text, flags=re.IGNORECASE):
                hits.append(f"regex:{pattern}")
        except re.error:
            hits.append(f"regex_error:{pattern}")

    flagged = len(hits) > 0
    action = policy.default_action
    should_block = flagged and (strict_legal or action == "block")

    warnings: list[str] = []
    violations: list[str] = []
    if flagged:
        message = "Legal content matched blocked rules: " + "; ".join(hits)
        violations.append(message)

    return LegalCheckResult(
        passed=not should_block,
        action=action,
        flagged=flagged,
        should_block=should_block,
        hits=hits,
        warnings=warnings,
        violations=violations,
    )
