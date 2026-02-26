from pathlib import Path

from creative_automation_cli.compliance.legal import evaluate_legal_text
from creative_automation_cli.compliance.legal_policy import load_legal_policy


def test_load_legal_policy_yaml(tmp_path: Path) -> None:
    policy_path = tmp_path / "legal_policy.yaml"
    policy_path.write_text(
        """
version: 1
default_action: warn
checks:
  blocked_keywords: ["forbidden"]
  blocked_regex: ["\\\\bbad\\\\s+claim\\\\b"]
locale_overrides:
  es:
    blocked_keywords: ["prohibido"]
    blocked_regex: []
""".strip(),
        encoding="utf-8",
    )

    policy = load_legal_policy(policy_path)
    assert policy.default_action == "warn"
    assert "forbidden" in policy.checks.blocked_keywords


def test_legal_evaluation_detects_hits_as_violations() -> None:
    policy = load_legal_policy(Path("config/legal_policy.yaml"))
    result = evaluate_legal_text(
        text="This includes free money and no side effects claims",
        locale="en",
        policy=policy,
        strict_legal=False,
    )
    assert result.flagged is True
    assert result.should_block is False
    assert result.passed is True
    assert len(result.violations) > 0
    assert result.warnings == []


def test_legal_evaluation_handles_joined_word_boundaries(tmp_path: Path) -> None:
    policy_path = tmp_path / "legal_policy.yaml"
    policy_path.write_text(
        """
version: 1
default_action: warn
checks:
  blocked_keywords: []
  blocked_regex: ["\\\\bfree\\\\s+money\\\\b"]
locale_overrides: {}
""".strip(),
        encoding="utf-8",
    )
    policy = load_legal_policy(policy_path)

    joined_text = "artifactFree money suffix"
    result = evaluate_legal_text(
        text=joined_text,
        locale="en",
        policy=policy,
        strict_legal=False,
    )
    assert result.flagged is True
    assert any(hit.startswith("regex:") for hit in result.hits)
