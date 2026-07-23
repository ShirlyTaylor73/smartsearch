import json
import os
from pathlib import Path

import pytest

from smart_search import skill_installer


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: smart-search-cli\n---\n", encoding="utf-8")
    (root / "references" / "search.md").write_text("search", encoding="utf-8")
    return root


def test_official_target_paths_are_split_by_scope(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"

    assert skill_installer.skill_target_path("codex", "project", project_root=project, home=home) == project / ".agents/skills/smart-search-cli"
    assert skill_installer.skill_target_path("codex", "global", project_root=project, home=home) == home / ".codex/skills/smart-search-cli"
    assert skill_installer.skill_target_path("opencode", "global", project_root=project, home=home) == home / ".config/opencode/skills/smart-search-cli"
    assert skill_installer.skill_target_path("pi", "project", project_root=project, home=home) == project / ".pi/skills/smart-search-cli"
    assert skill_installer.skill_target_path("windsurf", "global", project_root=project, home=home) == home / ".codeium/windsurf/skills/smart-search-cli"


@pytest.mark.parametrize(
    ("target", "project_path", "global_path"),
    [
        ("codex", ".agents/skills", ".codex/skills"),
        ("claude", ".claude/skills", ".claude/skills"),
        ("cursor", ".agents/skills", ".cursor/skills"),
        ("opencode", ".agents/skills", ".config/opencode/skills"),
        ("copilot", ".agents/skills", ".copilot/skills"),
        ("gemini", ".agents/skills", ".gemini/skills"),
        ("kiro", ".kiro/skills", ".kiro/skills"),
        ("qoder", ".qoder/skills", ".qoder/skills"),
        ("codebuddy", ".codebuddy/skills", ".codebuddy/skills"),
        ("droid", ".factory/skills", ".factory/skills"),
        ("pi", ".pi/skills", ".pi/agent/skills"),
        ("kilo", ".kilocode/skills", ".kilocode/skills"),
        ("antigravity", ".agents/skills", ".gemini/antigravity/skills"),
        ("windsurf", ".windsurf/skills", ".codeium/windsurf/skills"),
        ("hermes", ".hermes/skills", ".hermes/skills"),
    ],
)
def test_all_supported_targets_use_official_scope_paths(tmp_path, target, project_path, global_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    suffix = Path("smart-search-cli")

    assert skill_installer.skill_target_path(target, "project", project_root=project, home=home) == project / project_path / suffix
    assert skill_installer.skill_target_path(target, "global", project_root=project, home=home) == home / global_path / suffix


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink assertion")
def test_install_uses_one_canonical_copy_and_relative_symlinks(tmp_path):
    project = tmp_path / "project"
    source = _source(tmp_path)

    result = skill_installer.install_skill_targets(
        ["codex", "claude"],
        scope="project",
        project_root=project,
        source_root=source,
    )

    canonical = project / ".agents/skills/smart-search-cli"
    claude = project / ".claude/skills/smart-search-cli"
    assert result["ok"] is True
    assert canonical.is_dir()
    assert not canonical.is_symlink()
    assert claude.is_symlink()
    assert not Path(os.readlink(claude)).is_absolute()
    assert claude.resolve() == canonical.resolve()
    assert result["installed_count"] == 2

    manifest = json.loads((project / ".agents/skills/.smart-search-installations.json").read_text())
    targets = manifest["skills"]["smart-search-cli"]["targets"]
    assert targets["codex"]["mode"] == "direct"
    assert targets["claude"]["mode"] == "symlink"
    assert not Path(targets["claude"]["path"]).is_absolute()


def test_link_failure_falls_back_to_copy(monkeypatch, tmp_path):
    project = tmp_path / "project"
    source = _source(tmp_path)
    monkeypatch.setattr(skill_installer, "_create_directory_link", lambda *args, **kwargs: None)

    result = skill_installer.install_skill_targets(
        ["claude"],
        scope="project",
        project_root=project,
        source_root=source,
    )

    installed = result["installed"][0]
    target = project / ".claude/skills/smart-search-cli"
    assert installed["mode"] == "copy"
    assert installed["fallback_to_copy"] is True
    assert target.is_dir()
    assert not target.is_symlink()


def test_windows_prefers_directory_junction(monkeypatch, tmp_path):
    target = tmp_path / "canonical"
    link = tmp_path / "agent" / "skill"
    target.mkdir()
    monkeypatch.setattr(skill_installer.platform, "system", lambda: "Windows")
    monkeypatch.setattr(skill_installer, "_create_windows_junction", lambda *args: True)

    assert skill_installer._create_directory_link(target, link) == "junction"


def test_update_refreshes_canonical_and_copy_targets(monkeypatch, tmp_path):
    project = tmp_path / "project"
    source = _source(tmp_path)
    skill_installer.install_skill_targets(
        ["claude"], scope="project", project_root=project, source_root=source, copy=True
    )
    (source / "references/search.md").write_text("updated", encoding="utf-8")

    result = skill_installer.update_skill_targets(
        ["claude"], scope="project", project_root=project, source_root=source
    )

    assert result["ok"] is True
    assert (project / ".agents/skills/smart-search-cli/references/search.md").read_text() == "updated"
    assert (project / ".claude/skills/smart-search-cli/references/search.md").read_text() == "updated"


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink assertion")
def test_uninstall_preserves_canonical_until_last_target(tmp_path):
    project = tmp_path / "project"
    source = _source(tmp_path)
    skill_installer.install_skill_targets(
        ["codex", "claude"], scope="project", project_root=project, source_root=source
    )

    first = skill_installer.uninstall_skill_targets(
        ["claude"], scope="project", project_root=project
    )
    assert first["ok"] is True
    assert not (project / ".claude/skills/smart-search-cli").exists()
    assert (project / ".agents/skills/smart-search-cli").is_dir()

    second = skill_installer.uninstall_skill_targets(
        ["codex"], scope="project", project_root=project
    )
    assert second["ok"] is True
    assert not (project / ".agents/skills/smart-search-cli").exists()
    assert not (project / ".agents/skills/.smart-search-installations.json").exists()


def test_uninstall_unmanaged_noncanonical_target_does_not_remove_canonical(tmp_path):
    project = tmp_path / "project"
    canonical = project / ".agents/skills/smart-search-cli"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text("manual", encoding="utf-8")

    result = skill_installer.uninstall_skill_targets(
        ["claude"], scope="project", project_root=project
    )

    assert result["canonical_removed"] is False
    assert canonical.is_dir()


def test_empty_target_selection_is_a_noop(tmp_path):
    project = tmp_path / "project"
    source = _source(tmp_path)

    installed = skill_installer.install_skill_targets(
        [], scope="project", project_root=project, source_root=source
    )
    removed = skill_installer.uninstall_skill_targets([], scope="project", project_root=project)

    assert installed["installed_count"] == 0
    assert removed["removed_count"] == 0
    assert not (project / ".agents/skills/smart-search-cli").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX broken symlink assertion")
def test_status_reports_broken_link(tmp_path):
    project = tmp_path / "project"
    source = _source(tmp_path)
    target = project / ".claude/skills/smart-search-cli"
    target.parent.mkdir(parents=True)
    target.symlink_to(project / "missing", target_is_directory=True)

    result = skill_installer.status_skill_targets(
        ["claude"], scope="project", project_root=project, source_root=source
    )

    assert result["targets"][0]["status"] == "broken_link"


def test_cli_skill_contract_rejects_removed_arguments():
    from smart_search import cli

    parser = cli.build_parser()
    args = parser.parse_args(["skills", "install", "--project", "--agent", "codex", "--copy", "--yes"])
    assert args.skills_command == "install"
    assert args.project_scope is True
    assert args.agents == ["codex"]
    assert args.copy is True

    for removed in ("--targets", "--project-root", "--source-root"):
        with pytest.raises(SystemExit):
            parser.parse_args(["skills", "install", removed, "value"])


def test_setup_accepts_noninteractive_skill_selection():
    from smart_search import cli

    args = cli.build_parser().parse_args(
        ["setup", "--non-interactive", "--global", "--agent", "codex", "--copy"]
    )
    assert args.global_scope is True
    assert args.agents == ["codex"]
    assert args.copy is True


def test_cli_install_status_update_uninstall_lifecycle(monkeypatch, tmp_path, capsys):
    from smart_search import cli

    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    assert cli.main(["skills", "install", "--project", "--agent", "codex", "--yes"]) == 0
    installed = json.loads(capsys.readouterr().out)
    assert installed["installed"][0]["mode"] == "direct"

    assert cli.main(["skills", "status", "--project", "--agent", "codex", "--yes"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["targets"][0]["status"] == "up_to_date"

    assert cli.main(["skills", "update", "--project", "--agent", "codex", "--yes"]) == 0
    assert json.loads(capsys.readouterr().out)["updated_count"] == 1

    assert cli.main(["skills", "uninstall", "--project", "--agent", "codex", "--yes"]) == 0
    assert json.loads(capsys.readouterr().out)["canonical_removed"] is True


def test_noninteractive_setup_installs_only_with_explicit_agent(monkeypatch, tmp_path, capsys):
    from smart_search import cli

    project = tmp_path / "project"
    config = tmp_path / "config"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("SMART_SEARCH_CONFIG_DIR", str(config))
    cli.service.config._config_file = None
    cli.service.config._config_dir_source = None

    assert cli.main(["setup", "--non-interactive"]) == 0
    without_target = json.loads(capsys.readouterr().out)
    assert without_target["skill_install"] is None
    assert not (project / ".agents/skills/smart-search-cli").exists()

    assert cli.main(["setup", "--non-interactive", "--project", "--agent", "codex"]) == 0
    with_target = json.loads(capsys.readouterr().out)
    assert with_target["skill_install"]["ok"] is True
    assert (project / ".agents/skills/smart-search-cli").is_dir()
