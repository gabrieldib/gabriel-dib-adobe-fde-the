from pathlib import Path

from creative_automation_cli.cli import _load_env_file


def test_load_env_file_sets_variables(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text('GEMINI_API_KEY="abc123"\nOTHER=value\n', encoding="utf-8")

    _load_env_file(env_path)

    assert __import__("os").environ["GEMINI_API_KEY"] == "abc123"
    assert __import__("os").environ["OTHER"] == "value"


def test_load_env_file_does_not_override_existing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "existing")
    env_path = tmp_path / ".env"
    env_path.write_text("GEMINI_API_KEY=new_value\n", encoding="utf-8")

    _load_env_file(env_path)

    assert __import__("os").environ["GEMINI_API_KEY"] == "existing"
