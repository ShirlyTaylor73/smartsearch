from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from importlib import resources
from pathlib import Path
from typing import Any, Iterable


SKILL_NAME = "smart-search-cli"
BUNDLED_SKILLS = (SKILL_NAME,)
PACKAGE_ROOT_ENV = "SMART_SEARCH_PACKAGE_ROOT"
CANONICAL_ROOT = Path(".agents/skills")
MANIFEST_NAME = ".smart-search-installations.json"
MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SkillTarget:
    target_id: str
    label: str
    project_root: str
    global_root: str | None
    executables: tuple[str, ...] = ()


SKILL_TARGETS: tuple[SkillTarget, ...] = (
    SkillTarget("codex", "Codex", ".agents/skills", ".codex/skills", ("codex",)),
    SkillTarget("claude", "Claude Code", ".claude/skills", ".claude/skills", ("claude",)),
    SkillTarget("cursor", "Cursor", ".agents/skills", ".cursor/skills", ("cursor",)),
    SkillTarget("opencode", "OpenCode", ".agents/skills", ".config/opencode/skills", ("opencode",)),
    SkillTarget("copilot", "GitHub Copilot", ".agents/skills", ".copilot/skills", ("gh",)),
    SkillTarget("gemini", "Gemini CLI", ".agents/skills", ".gemini/skills", ("gemini",)),
    SkillTarget("kiro", "Kiro CLI", ".kiro/skills", ".kiro/skills", ("kiro-cli", "kiro")),
    SkillTarget("qoder", "Qoder", ".qoder/skills", ".qoder/skills", ("qoder",)),
    SkillTarget("codebuddy", "CodeBuddy", ".codebuddy/skills", ".codebuddy/skills", ("codebuddy",)),
    SkillTarget("droid", "Factory Droid", ".factory/skills", ".factory/skills", ("droid",)),
    SkillTarget("pi", "Pi Agent", ".pi/skills", ".pi/agent/skills", ("pi",)),
    SkillTarget("kilo", "Kilo Code", ".kilocode/skills", ".kilocode/skills", ("kilo",)),
    SkillTarget("antigravity", "Antigravity", ".agents/skills", ".gemini/antigravity/skills"),
    SkillTarget("windsurf", "Windsurf", ".windsurf/skills", ".codeium/windsurf/skills", ("windsurf",)),
    SkillTarget("hermes", "Hermes Agent", ".hermes/skills", ".hermes/skills", ("hermes",)),
)

SKILL_TARGET_BY_ID = {target.target_id: target for target in SKILL_TARGETS}

_TARGET_ALIASES = {
    "agents": "codex",
    "agentskills": "codex",
    "agent-skills": "codex",
    "claude-code": "claude",
    "github-copilot": "copilot",
    "gh-copilot": "copilot",
    "gemini-cli": "gemini",
    "kiro-cli": "kiro",
    "factory": "droid",
    "factory-droid": "droid",
    "pi-agent": "pi",
    "kilo-cli": "kilo",
    "hermes-agent": "hermes",
    "nous-hermes": "hermes",
}


class SkillInstallError(ValueError):
    pass


def _tokens(raw: str | Iterable[str]) -> list[str]:
    if isinstance(raw, str):
        values = [raw]
    else:
        values = list(raw)
    tokens: list[str] = []
    for value in values:
        normalized = value.replace(";", ",").replace("+", ",")
        for part in normalized.split(","):
            tokens.extend(piece for piece in part.strip().lower().split() if piece)
    return tokens


def parse_skill_targets(raw: str | Iterable[str]) -> list[str]:
    selected: list[str] = []
    invalid: list[str] = []
    for token in _tokens(raw):
        if token in {"skip", "none", "no", "n", "跳过", "无", "否"}:
            return []
        if token in {"all", "*", "全部"}:
            return [target.target_id for target in SKILL_TARGETS]
        target_id = _TARGET_ALIASES.get(token, token)
        if target_id not in SKILL_TARGET_BY_ID:
            invalid.append(token)
        elif target_id not in selected:
            selected.append(target_id)
    if invalid:
        valid = ", ".join(target.target_id for target in SKILL_TARGETS)
        raise SkillInstallError(f"Unknown skill target(s): {', '.join(invalid)}. Valid targets: {valid}")
    return selected


def parse_skill_names(raw: str | Iterable[str] | None) -> list[str]:
    tokens = _tokens(raw or SKILL_NAME)
    if not tokens:
        return [SKILL_NAME]
    if any(token in {"all", "*"} for token in tokens):
        return list(BUNDLED_SKILLS)
    invalid = [token for token in tokens if token not in BUNDLED_SKILLS]
    if invalid:
        raise SkillInstallError(
            f"Unknown bundled skill(s): {', '.join(invalid)}. Valid skills: {', '.join(BUNDLED_SKILLS)}"
        )
    return list(dict.fromkeys(tokens))


def _scope_base(
    scope: str,
    *,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
) -> Path:
    if scope not in {"project", "global"}:
        raise SkillInstallError("scope must be 'project' or 'global'")
    if scope == "project":
        return Path(project_root or Path.cwd()).expanduser().resolve()
    return Path(home or Path.home()).expanduser().resolve()


def canonical_skill_path(
    skill_name: str = SKILL_NAME,
    *,
    scope: str,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
) -> Path:
    parse_skill_names(skill_name)
    return _scope_base(scope, project_root=project_root, home=home) / CANONICAL_ROOT / skill_name


def skill_target_path(
    target_id: str,
    scope: str,
    *,
    skill_name: str = SKILL_NAME,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
) -> Path:
    target_id = _TARGET_ALIASES.get(target_id, target_id)
    if target_id not in SKILL_TARGET_BY_ID:
        raise SkillInstallError(f"Unknown skill target: {target_id}")
    base = _scope_base(scope, project_root=project_root, home=home)
    target = SKILL_TARGET_BY_ID[target_id]
    relative_root = target.project_root if scope == "project" else target.global_root
    if relative_root is None:
        raise SkillInstallError(f"{target.label} does not support {scope} skill installation")
    return base / Path(relative_root) / skill_name


def detect_skill_targets(
    scope: str,
    *,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
) -> list[str]:
    base = _scope_base(scope, project_root=project_root, home=home)
    home_base = Path(home or Path.home()).expanduser().resolve()
    detected: list[str] = []
    for target in SKILL_TARGETS:
        relative_root = target.project_root if scope == "project" else target.global_root
        if relative_root is None:
            continue
        marker = base / Path(relative_root).parts[0]
        global_marker = home_base / Path(target.global_root).parts[0] if target.global_root else None
        marker_detected = marker.exists() and target.project_root != CANONICAL_ROOT.as_posix()
        if marker_detected or (global_marker is not None and global_marker.exists()) or any(
            shutil.which(command) for command in target.executables
        ):
            detected.append(target.target_id)
    return detected


def _resource_skill_root(skill_name: str) -> Any:
    try:
        root = resources.files("smart_search").joinpath("assets", "skills", skill_name)
        if root.is_dir():
            return root
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):
        pass
    return None


def _filesystem_skill_root(skill_name: str) -> Path | None:
    candidates: list[Path] = []
    package_root = os.getenv(PACKAGE_ROOT_ENV, "").strip()
    if package_root:
        base = Path(package_root)
        candidates.append(base / "src" / "smart_search" / "assets" / "skills" / skill_name)
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "src" / "smart_search" / "assets" / "skills" / skill_name)
    return next((candidate for candidate in candidates if candidate.is_dir()), None)


def _iter_resource_files(root: Any) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []

    def visit(node: Any, prefix: str = "") -> None:
        for child in node.iterdir():
            rel = f"{prefix}/{child.name}" if prefix else child.name
            if child.is_dir():
                visit(child, rel)
            elif child.is_file():
                files.append((rel, child.read_bytes()))

    visit(root)
    return files


def _iter_filesystem_files(root: Path) -> list[tuple[str, bytes]]:
    return [
        (str(path.relative_to(root)).replace("\\", "/"), path.read_bytes())
        for path in root.rglob("*")
        if path.is_file()
    ]


def _load_skill_files(skill_name: str = SKILL_NAME, source_root: Path | None = None) -> list[tuple[str, bytes]]:
    parse_skill_names(skill_name)
    if source_root is not None:
        if not source_root.is_dir():
            raise SkillInstallError(f"Skill source directory not found: {source_root}")
        files = _iter_filesystem_files(source_root)
    else:
        resource_root = _resource_skill_root(skill_name)
        files = _iter_resource_files(resource_root) if resource_root is not None else []
        if not files:
            filesystem_root = _filesystem_skill_root(skill_name)
            files = _iter_filesystem_files(filesystem_root) if filesystem_root is not None else []
    if not files:
        raise SkillInstallError(f"Bundled {skill_name} skill files were not found.")
    return files


def _skill_digest(files: list[tuple[str, bytes]]) -> str:
    digest = sha256()
    for rel_path, content in sorted(files, key=lambda item: item[0]):
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def _remove_path(path: Path) -> None:
    if path.is_symlink():
        path.unlink(missing_ok=True)
    elif path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _write_files(path: Path, files: list[tuple[str, bytes]]) -> None:
    _remove_path(path)
    path.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files:
        destination = path / Path(rel_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def _copy_directory(source: Path, destination: Path) -> None:
    _remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(str(right.resolve(strict=False)))


def _same_location(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _create_windows_junction(target: Path, link_path: Path) -> bool:
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target.resolve())],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _create_directory_link(target: Path, link_path: Path) -> str | None:
    _remove_path(link_path)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        try:
            if _create_windows_junction(target, link_path):
                return "junction"
        except OSError:
            pass
        try:
            link_path.symlink_to(target.resolve(), target_is_directory=True)
            return "symlink"
        except OSError:
            return None
    try:
        real_parent = link_path.parent.resolve()
        relative_target = Path(os.path.relpath(target.resolve(), real_parent))
        link_path.symlink_to(relative_target, target_is_directory=True)
        return "symlink"
    except OSError:
        return None


def _manifest_path(base: Path) -> Path:
    return base / CANONICAL_ROOT / MANIFEST_NAME


def _empty_manifest() -> dict[str, Any]:
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "skills": {}}


def _read_manifest(base: Path) -> dict[str, Any]:
    path = _manifest_path(base)
    if not path.exists():
        return _empty_manifest()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillInstallError(f"Invalid skill installation manifest: {exc}") from exc
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION or not isinstance(data.get("skills"), dict):
        raise SkillInstallError("Unsupported skill installation manifest schema")
    return data


def _write_manifest(base: Path, manifest: dict[str, Any]) -> None:
    path = _manifest_path(base)
    if not manifest.get("skills"):
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _relative_to_scope(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError as exc:
        raise SkillInstallError(f"Skill target escapes selected scope: {path}") from exc


def _source_path(source_root: str | Path | None) -> Path | None:
    return Path(source_root).expanduser().resolve() if source_root is not None else None


def install_skill_targets(
    target_ids: list[str],
    *,
    scope: str = "global",
    skill_name: str = SKILL_NAME,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
    source_root: str | Path | None = None,
    copy: bool = False,
) -> dict[str, Any]:
    parse_skill_names(skill_name)
    selected_ids = parse_skill_targets(target_ids)
    base = _scope_base(scope, project_root=project_root, home=home)
    canonical = canonical_skill_path(skill_name, scope=scope, project_root=project_root, home=home)
    if not selected_ids:
        return {
            "ok": True,
            "scope": scope,
            "root": str(base),
            "canonical_path": str(canonical),
            "skill": skill_name,
            "selected": [],
            "installed": [],
            "failed": [],
            "installed_count": 0,
            "failed_count": 0,
        }
    files = _load_skill_files(skill_name, _source_path(source_root))
    bundled_hash = _skill_digest(files)
    manifest = _read_manifest(base)
    _write_files(canonical, files)
    skill_record = manifest["skills"].setdefault(skill_name, {"bundled_hash": bundled_hash, "targets": {}})
    skill_record["bundled_hash"] = bundled_hash
    installed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for target_id in selected_ids:
        target = SKILL_TARGET_BY_ID[target_id]
        destination = skill_target_path(
            target_id, scope, skill_name=skill_name, project_root=project_root, home=home
        )
        try:
            fallback_to_copy = False
            if _same_location(destination, canonical):
                mode = "direct"
            elif copy:
                _copy_directory(canonical, destination)
                mode = "copy"
            else:
                link_mode = _create_directory_link(canonical, destination)
                if link_mode is None:
                    _copy_directory(canonical, destination)
                    mode = "copy"
                    fallback_to_copy = True
                else:
                    mode = link_mode
            skill_record["targets"][target_id] = {
                "path": _relative_to_scope(destination, base),
                "mode": mode,
            }
            installed.append(
                {
                    "target": target_id,
                    "label": target.label,
                    "path": str(destination),
                    "mode": mode,
                    "fallback_to_copy": fallback_to_copy,
                    "files": len(files),
                }
            )
        except OSError as exc:
            failed.append(
                {"target": target_id, "label": target.label, "path": str(destination), "error": str(exc)}
            )

    _write_manifest(base, manifest)
    return {
        "ok": not failed,
        "scope": scope,
        "root": str(base),
        "canonical_path": str(canonical),
        "skill": skill_name,
        "selected": selected_ids,
        "installed": installed,
        "failed": failed,
        "installed_count": len(installed),
        "failed_count": len(failed),
    }


def status_skill_targets(
    target_ids: list[str],
    *,
    scope: str = "global",
    skill_name: str = SKILL_NAME,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
    source_root: str | Path | None = None,
) -> dict[str, Any]:
    selected_ids = parse_skill_targets(target_ids)
    base = _scope_base(scope, project_root=project_root, home=home)
    canonical = canonical_skill_path(skill_name, scope=scope, project_root=project_root, home=home)
    source_files = _load_skill_files(skill_name, _source_path(source_root))
    source_by_path = dict(source_files)
    bundled_hash = _skill_digest(source_files)
    manifest = _read_manifest(base)
    records = manifest.get("skills", {}).get(skill_name, {}).get("targets", {})
    targets: list[dict[str, Any]] = []

    for target_id in selected_ids:
        target = SKILL_TARGET_BY_ID[target_id]
        destination = skill_target_path(
            target_id, scope, skill_name=skill_name, project_root=project_root, home=home
        )
        record = records.get(target_id, {})
        item: dict[str, Any] = {
            "target": target_id,
            "label": target.label,
            "path": str(destination),
            "canonical_path": str(canonical),
            "mode": record.get("mode", "unmanaged"),
            "status": "missing",
            "bundled_hash": bundled_hash,
            "installed_hash": "",
            "extra_files": [],
            "missing_files": sorted(source_by_path),
            "stale_files": [],
        }
        try:
            if destination.is_symlink() and not destination.exists():
                item["status"] = "broken_link"
                targets.append(item)
                continue
            if not destination.exists():
                targets.append(item)
                continue
            if not destination.is_dir():
                item.update(status="error", error="Installed skill path exists but is not a directory.")
                targets.append(item)
                continue
            if record.get("mode") in {"symlink", "junction"} and not _same_path(destination, canonical):
                item["status"] = "broken_link"
                targets.append(item)
                continue
            installed_files = _iter_filesystem_files(destination)
            installed_by_path = dict(installed_files)
            missing = sorted(path for path in source_by_path if path not in installed_by_path)
            stale = sorted(
                path for path, content in source_by_path.items() if installed_by_path.get(path) not in {None, content}
            )
            extra = sorted(path for path in installed_by_path if path not in source_by_path)
            item.update(
                installed_hash=_skill_digest(installed_files) if installed_files else "",
                missing_files=missing,
                stale_files=stale,
                extra_files=extra,
            )
            if missing or stale:
                item["status"] = "stale"
            elif extra:
                item["status"] = "extra_files"
            else:
                item["status"] = "up_to_date"
        except OSError as exc:
            item.update(status="error", error=str(exc))
        targets.append(item)

    counts: dict[str, int] = {}
    for item in targets:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "ok": not any(item["status"] == "error" for item in targets),
        "scope": scope,
        "root": str(base),
        "canonical_path": str(canonical),
        "skill": skill_name,
        "selected": selected_ids,
        "bundled_files": len(source_files),
        "bundled_hash": bundled_hash,
        "targets": targets,
        "status_counts": counts,
    }


def update_skill_targets(
    target_ids: list[str],
    *,
    scope: str = "global",
    skill_name: str = SKILL_NAME,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
    source_root: str | Path | None = None,
) -> dict[str, Any]:
    selected_ids = parse_skill_targets(target_ids)
    base = _scope_base(scope, project_root=project_root, home=home)
    manifest = _read_manifest(base)
    skill_record = manifest.get("skills", {}).get(skill_name)
    if not skill_record:
        return {
            "ok": True,
            "scope": scope,
            "skill": skill_name,
            "updated": [],
            "skipped": selected_ids,
            "updated_count": 0,
        }
    registered = skill_record.get("targets", {})
    requested_installed = [target_id for target_id in selected_ids if target_id in registered]
    if not requested_installed:
        return {
            "ok": True,
            "scope": scope,
            "skill": skill_name,
            "updated": [],
            "skipped": selected_ids,
            "updated_count": 0,
        }

    files = _load_skill_files(skill_name, _source_path(source_root))
    canonical = canonical_skill_path(skill_name, scope=scope, project_root=project_root, home=home)
    _write_files(canonical, files)
    skill_record["bundled_hash"] = _skill_digest(files)
    updated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    # Canonical content is shared, so every registered copy must be refreshed.
    for target_id, record in registered.items():
        destination = skill_target_path(
            target_id, scope, skill_name=skill_name, project_root=project_root, home=home
        )
        try:
            mode = record.get("mode", "copy")
            fallback_to_copy = False
            if mode == "direct":
                pass
            elif mode == "copy":
                _copy_directory(canonical, destination)
            elif not destination.exists() or not _same_path(destination, canonical):
                link_mode = _create_directory_link(canonical, destination)
                if link_mode is None:
                    _copy_directory(canonical, destination)
                    mode = "copy"
                    fallback_to_copy = True
                else:
                    mode = link_mode
                record["mode"] = mode
            updated.append(
                {
                    "target": target_id,
                    "path": str(destination),
                    "mode": mode,
                    "fallback_to_copy": fallback_to_copy,
                }
            )
        except OSError as exc:
            failed.append({"target": target_id, "path": str(destination), "error": str(exc)})
    _write_manifest(base, manifest)
    return {
        "ok": not failed,
        "scope": scope,
        "skill": skill_name,
        "canonical_path": str(canonical),
        "updated": updated,
        "failed": failed,
        "updated_count": len(updated),
        "failed_count": len(failed),
    }


def uninstall_skill_targets(
    target_ids: list[str],
    *,
    scope: str = "global",
    skill_name: str = SKILL_NAME,
    project_root: str | Path | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    selected_ids = parse_skill_targets(target_ids)
    base = _scope_base(scope, project_root=project_root, home=home)
    canonical = canonical_skill_path(skill_name, scope=scope, project_root=project_root, home=home)
    if not selected_ids:
        return {
            "ok": True,
            "scope": scope,
            "skill": skill_name,
            "canonical_path": str(canonical),
            "canonical_removed": False,
            "removed": [],
            "failed": [],
            "removed_count": 0,
            "failed_count": 0,
        }
    manifest = _read_manifest(base)
    had_skill_record = skill_name in manifest.get("skills", {})
    skill_record = manifest.get("skills", {}).get(skill_name, {"targets": {}})
    records = skill_record.get("targets", {})
    removed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    selected_canonical = False

    for target_id in selected_ids:
        destination = skill_target_path(
            target_id, scope, skill_name=skill_name, project_root=project_root, home=home
        )
        record = records.pop(target_id, None)
        try:
            if not _same_location(destination, canonical):
                existed = destination.exists() or destination.is_symlink()
                _remove_path(destination)
            else:
                existed = canonical.exists()
                selected_canonical = True
            removed.append(
                {
                    "target": target_id,
                    "path": str(destination),
                    "mode": (record or {}).get("mode", "unmanaged"),
                    "existed": existed,
                }
            )
        except OSError as exc:
            failed.append({"target": target_id, "path": str(destination), "error": str(exc)})

    canonical_removed = False
    if not records:
        if had_skill_record or selected_canonical:
            try:
                _remove_path(canonical)
                canonical_removed = True
                manifest.get("skills", {}).pop(skill_name, None)
            except OSError as exc:
                failed.append({"target": "canonical", "path": str(canonical), "error": str(exc)})
    else:
        skill_record["targets"] = records
        manifest["skills"][skill_name] = skill_record
    _write_manifest(base, manifest)
    return {
        "ok": not failed,
        "scope": scope,
        "skill": skill_name,
        "canonical_path": str(canonical),
        "canonical_removed": canonical_removed,
        "removed": removed,
        "failed": failed,
        "removed_count": len(removed),
        "failed_count": len(failed),
    }
