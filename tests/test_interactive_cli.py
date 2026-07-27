import json

import pytest

from smart_search import cli


class FakePromptUI:
    def __init__(self, *, selects=None, checks=None, confirms=None, texts=None, secrets=None, tty=True):
        self.selects = list(selects or [])
        self.checks = list(checks or [])
        self.confirms = list(confirms or [])
        self.texts = list(texts or [])
        self.secrets = list(secrets or [])
        self.tty = tty
        self.calls = []

    def require_tty(self, hint):
        self.calls.append(("require_tty", hint))
        if not self.tty:
            raise cli.InteractivePromptError(hint)

    def select(self, message, choices, *, default=None):
        self.calls.append(("select", message, choices, default))
        return self.selects.pop(0)

    def checkbox(self, message, choices, *, enabled=None, required=False):
        self.calls.append(("checkbox", message, choices, enabled, required))
        return self.checks.pop(0)

    def confirm(self, message, *, default=False):
        self.calls.append(("confirm", message, default))
        return self.confirms.pop(0)

    def text(self, message, *, default="", required=False):
        self.calls.append(("text", message, default, required))
        return self.texts.pop(0)

    def secret(self, message, *, required=False):
        self.calls.append(("secret", message, required))
        return self.secrets.pop(0)


def _reset_config(monkeypatch, tmp_path):
    monkeypatch.setenv("SMART_SEARCH_CONFIG_DIR", str(tmp_path / "config"))
    cli.service.config._config_file = None
    cli.service.config._config_dir_source = None


def test_interactive_setup_uses_select_secret_and_single_final_confirmation(monkeypatch, tmp_path, capsys):
    _reset_config(monkeypatch, tmp_path)
    prompt = FakePromptUI(
        selects=["xai-responses"],
        confirms=[False, True],
        secrets=["xai", "exa", "context7", "zread", "firecrawl"],
    )
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["ok"] is True
    assert result["skill_install"] is None
    assert cli.service.config.get_saved_config(masked=False)["XAI_API_KEY"] == "xai"
    assert [call[0] for call in prompt.calls].count("select") == 1
    assert [call[0] for call in prompt.calls].count("secret") == 5
    assert prompt.calls[-1][:2] == ("confirm", "Apply this setup?")


def test_interactive_setup_keeps_existing_values_without_echoing_secrets(monkeypatch, tmp_path, capsys):
    _reset_config(monkeypatch, tmp_path)
    for key, value in {
        "SMART_SEARCH_GROK_TRANSPORT": "xai-responses",
        "XAI_API_KEY": "xai-secret",
        "EXA_API_KEY": "exa-secret",
        "CONTEXT7_API_KEY": "context-secret",
        "ZHIPU_MCP_API_KEY": "zread-secret",
        "FIRECRAWL_API_KEY": "firecrawl-secret",
    }.items():
        cli.service.config.set_config_value(key, value)
    prompt = FakePromptUI(selects=["xai-responses"], confirms=[True, True, True, True, True, False, True])
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup"]) == 0
    captured = capsys.readouterr()

    assert "xai-secret" not in captured.out
    assert "xai-secret" not in captured.err
    assert not any(call[0] == "secret" for call in prompt.calls)
    assert cli.service.config.get_saved_config(masked=False)["XAI_API_KEY"] == "xai-secret"


def test_setup_final_no_does_not_write_config_or_skill(monkeypatch, tmp_path, capsys):
    _reset_config(monkeypatch, tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    prompt = FakePromptUI(
        selects=["xai-responses", "project"],
        checks=[["codex"]],
        confirms=[True, False],
        secrets=["xai", "exa", "context7", "zread", "firecrawl"],
    )
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["cancelled"] is True
    assert cli.service.config.get_saved_config(masked=False) == {}
    assert not (project / ".agents/skills/smart-search-cli").exists()


def test_interactive_skills_use_scope_and_agent_selectors(monkeypatch, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    prompt = FakePromptUI(selects=["project"], checks=[["codex"]], confirms=[True])
    monkeypatch.setattr(cli, "prompt_ui", prompt)
    monkeypatch.setattr(cli, "detect_skill_targets", lambda scope: ["codex"])

    assert cli.main(["skills", "install"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["installed_count"] == 1
    checkbox_call = next(call for call in prompt.calls if call[0] == "checkbox")
    assert checkbox_call[3] == ["codex"]
    assert not any(call[0] == "select" and call[1] == "Installation method" for call in prompt.calls)


def test_interactive_skill_install_offers_copy_for_noncanonical_target(monkeypatch, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    prompt = FakePromptUI(
        selects=["project", "copy"],
        checks=[["claude"]],
        confirms=[True],
    )
    monkeypatch.setattr(cli, "prompt_ui", prompt)
    monkeypatch.setattr(cli, "detect_skill_targets", lambda scope: ["claude"])

    assert cli.main(["skills", "install"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["installed"][0]["mode"] == "copy"
    assert any(call[0] == "select" and call[1] == "Installation method" for call in prompt.calls)


def test_setup_uses_environment_secret_without_copying_it_to_config(monkeypatch, tmp_path, capsys):
    _reset_config(monkeypatch, tmp_path)
    monkeypatch.setenv("XAI_API_KEY", "environment-xai-secret")
    prompt = FakePromptUI(
        selects=["xai-responses"],
        confirms=[True, False, True],
        secrets=["exa", "context7", "zread", "firecrawl"],
    )
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup"]) == 0
    captured = capsys.readouterr()
    saved = cli.service.config.get_saved_config(masked=False)

    assert "environment-xai-secret" not in captured.out
    assert "environment-xai-secret" not in captured.err
    assert "XAI_API_KEY" not in saved
    assert saved["EXA_API_KEY"] == "exa"


def test_interactive_skill_status_does_not_ask_for_execution_confirmation(monkeypatch, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    prompt = FakePromptUI(selects=["project"], checks=[["codex"]])
    monkeypatch.setattr(cli, "prompt_ui", prompt)
    monkeypatch.setattr(cli, "detect_skill_targets", lambda scope: ["codex"])

    assert cli.main(["skills", "status"]) == 0
    assert json.loads(capsys.readouterr().out)["targets"][0]["target"] == "codex"
    assert not any(call[0] == "confirm" for call in prompt.calls)


def test_non_tty_interactive_setup_returns_actionable_parameter_error(monkeypatch, tmp_path, capsys):
    _reset_config(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "prompt_ui", FakePromptUI(tty=False))

    assert cli.main(["setup"]) == 1
    result = json.loads(capsys.readouterr().out)

    assert result["error_type"] == "parameter_error"
    assert "--non-interactive" in result["error"]


def test_non_tty_interactive_skills_return_actionable_parameter_error(monkeypatch, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr(cli, "prompt_ui", FakePromptUI(tty=False))

    assert cli.main(["skills", "install", "--project", "--agent", "codex"]) == 1
    result = json.loads(capsys.readouterr().out)

    assert result["error_type"] == "parameter_error"
    assert "--yes" in result["error"]


def test_noninteractive_setup_never_uses_prompt_backend(monkeypatch, tmp_path, capsys):
    _reset_config(monkeypatch, tmp_path)
    prompt = FakePromptUI(tty=False)
    monkeypatch.setattr(cli, "prompt_ui", prompt)

    assert cli.main(["setup", "--non-interactive", "--grok-transport", "xai-responses", "--xai-api-key", "xai"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert prompt.calls == []
