import argparse
import asyncio
import json
import os
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from . import service
from .prompts import InteractivePromptError, prompt_ui
from .skill_installer import (
    SKILL_NAME,
    SKILL_TARGETS,
    SkillInstallError,
    canonical_skill_path,
    detect_skill_targets,
    install_skill_targets,
    parse_skill_names,
    parse_skill_targets,
    skill_target_path,
    status_skill_targets,
    uninstall_skill_targets,
    update_skill_targets,
)


class SmartSearchArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        if any(flag in message for flag in ("--instructions", "--max-depth", "--max-breadth")):
            message += "; Tavily Map parameters were removed, use Firecrawl --search/--sitemap/subdomain options"
        elif "--mode" in message:
            message += "; Exa search strategy is configured with EXA_SEARCH_TYPE"
        elif "--ref" in message:
            message += "; ZRead does not support repository refs"
        super().error(message)


def _get_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    try:
        return metadata.version("smart-search")
    except metadata.PackageNotFoundError:
        pass
    return "unknown"


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["json", "markdown", "content"], default="json")
    parser.add_argument("--output", default="")


def _add_skill_selection_args(parser: argparse.ArgumentParser, *, include_copy: bool = False) -> None:
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("-p", "--project", dest="project_scope", action="store_true")
    scope.add_argument("-g", "--global", dest="global_scope", action="store_true")
    parser.add_argument("-a", "--agent", dest="agents", action="append", default=[])
    parser.add_argument("--all-agents", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true")
    if include_copy:
        parser.add_argument("--copy", action="store_true", help="Copy files instead of linking Agent directories.")


def _markdown(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return f"# Error\n\n- type: `{data.get('error_type', 'provider_error')}`\n- message: {data.get('error', 'operation failed')}"
    lines = [f"# Smart Search: {data.get('capability') or data.get('mode') or 'result'}"]
    content = data.get("content")
    if content:
        lines.extend(["", str(content)])
    for key in ("results", "candidates", "entries", "sources", "checks", "cases"):
        rows = data.get(key)
        if not rows:
            continue
        lines.extend(["", f"## {key}"])
        for row in rows:
            if isinstance(row, dict):
                title = row.get("title") or row.get("id") or row.get("url") or row.get("operation") or row.get("name") or "item"
                lines.append(f"- **{title}**")
                for field in ("url", "description", "snippet", "responsible_provider", "error"):
                    if row.get(field):
                        lines.append(f"  - {field}: {row[field]}")
            else:
                lines.append(f"- {row}")
    if data.get("data") is not None:
        lines.extend(["", "## data", "", "```json", json.dumps(data["data"], ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines)


def _content(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return str(data.get("error") or "operation failed")
    if data.get("content"):
        return str(data["content"])
    if data.get("data") is not None:
        return json.dumps(data["data"], ensure_ascii=False, indent=2)
    for key in ("results", "candidates", "entries", "sources", "checks", "cases"):
        if data.get(key):
            return json.dumps(data[key], ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False, indent=2)


def _print_result(data: dict[str, Any], output_format: str, output: str = "") -> int:
    if output_format == "markdown":
        rendered = _markdown(data)
    elif output_format == "content":
        rendered = _content(data)
    else:
        rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        service.write_output(output, rendered)
    else:
        print(rendered)
    return 0 if data.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = SmartSearchArgumentParser(prog="smart-search", description="Deterministic web and documentation retrieval for AI agents.")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {_get_version()}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=SmartSearchArgumentParser, metavar="{search,docs,fetch,map,setup,doctor,diagnose,config,skills,dev}")

    search = sub.add_parser("search", help="Answer web questions or discover sources.")
    search_sub = search.add_subparsers(dest="operation", required=True, parser_class=SmartSearchArgumentParser)
    answer = search_sub.add_parser("answer", help="Generate a web-backed answer through the Responses API.")
    answer.add_argument("query")
    answer.add_argument("--timeout", type=float, default=90, metavar="SECONDS")
    answer.add_argument("--debug", action="store_true")
    _add_output_args(answer)
    sources = search_sub.add_parser("sources", help="Search sources through Exa.")
    sources.add_argument("query")
    sources.add_argument("--limit", type=int, default=5)
    sources.add_argument("--start-published-date", default="")
    sources.add_argument("--include-domains", nargs="+", default=[])
    sources.add_argument("--exclude-domains", nargs="+", default=[])
    sources.add_argument("--category", default="")
    sources.add_argument("--include-text", action="store_true")
    sources.add_argument("--include-highlights", action="store_true")
    sources.add_argument("--debug", action="store_true")
    _add_output_args(sources)

    docs = sub.add_parser("docs", help="Search documentation and GitHub repositories.")
    docs_sub = docs.add_subparsers(dest="operation", required=True, parser_class=SmartSearchArgumentParser)
    resolve = docs_sub.add_parser("resolve")
    resolve.add_argument("name")
    resolve.add_argument("query", nargs="?", default="")
    resolve.add_argument("--debug", action="store_true")
    _add_output_args(resolve)
    docs_search = docs_sub.add_parser("search")
    docs_search.add_argument("query")
    docs_search.add_argument("--source", default="")
    docs_search.add_argument("--debug", action="store_true")
    _add_output_args(docs_search)
    tree = docs_sub.add_parser("tree")
    tree.add_argument("repo")
    tree.add_argument("--path", default="")
    tree.add_argument("--debug", action="store_true")
    _add_output_args(tree)
    read = docs_sub.add_parser("read")
    read.add_argument("repo")
    read.add_argument("path")
    read.add_argument("--debug", action="store_true")
    _add_output_args(read)

    fetch = sub.add_parser("fetch", help="Extract a known URL through Firecrawl.")
    fetch_sub = fetch.add_subparsers(dest="operation", required=True, parser_class=SmartSearchArgumentParser)
    fetch_content = fetch_sub.add_parser("content")
    fetch_content.add_argument("url")
    fetch_content.add_argument("--debug", action="store_true")
    _add_output_args(fetch_content)
    extract = fetch_sub.add_parser("extract", description="Extract structured data; provide --schema or --prompt, or combine both.")
    extract.add_argument("url")
    extract.add_argument("--schema", default="", help="JSON Schema object for the extracted data.")
    extract.add_argument("--prompt", default="", help="Natural-language extraction intent; required when --schema is omitted.")
    extract.add_argument("--max-length", type=int, default=20000, help="Maximum raw_evidence length. Default: 20000.")
    extract.add_argument("--debug", action="store_true")
    _add_output_args(extract)

    site_map = sub.add_parser("map", help="Explore site URL structure through Firecrawl Map.")
    map_sub = site_map.add_subparsers(dest="operation", required=True, parser_class=SmartSearchArgumentParser)
    site = map_sub.add_parser("site")
    site.add_argument("url")
    site.add_argument("--search", default="")
    site.add_argument("--sitemap", choices=["include", "skip", "only"], default="include")
    site.add_argument("--include-subdomains", action=argparse.BooleanOptionalAction, default=True)
    site.add_argument("--ignore-query-parameters", action=argparse.BooleanOptionalAction, default=True)
    site.add_argument("--ignore-cache", action="store_true")
    site.add_argument("--limit", type=int, default=5000)
    site.add_argument("--timeout", type=int, default=150)
    site.add_argument("--location", default="")
    site.add_argument("--debug", action="store_true")
    _add_output_args(site)

    setup = sub.add_parser("setup", help="Configure the fixed provider set.")
    setup.add_argument("--non-interactive", action="store_true")
    _add_skill_selection_args(setup, include_copy=True)
    for flag in (
        "search-answer-api-url", "search-answer-api-key", "search-answer-model", "search-answer-tools",
        "exa-api-key", "exa-base-url", "exa-search-type",
        "context7-api-key", "context7-base-url",
        "zhipu-mcp-api-key", "zhipu-mcp-zread-api-url",
        "firecrawl-api-key", "firecrawl-api-url",
    ):
        setup.add_argument(f"--{flag}", default="")
    _add_output_args(setup)

    doctor = sub.add_parser("doctor", help="Report every operation executor and configuration state.")
    _add_output_args(doctor)

    diagnose = sub.add_parser("diagnose", help="Troubleshoot operations, providers, routing, and smoke checks.")
    diagnose_sub = diagnose.add_subparsers(dest="diagnose_command", required=True, parser_class=SmartSearchArgumentParser)
    for capability, operations in {"search": ["answer", "sources"], "docs": ["resolve", "search", "tree", "read"], "fetch": ["content", "extract"], "map": ["site"]}.items():
        item = diagnose_sub.add_parser(capability)
        item.add_argument("operation", nargs="?", choices=operations, default="")
        _add_output_args(item)
    provider = diagnose_sub.add_parser("provider")
    provider.add_argument("provider", choices=["responses", "exa", "context7", "zhipu-mcp-zread", "firecrawl"])
    provider.add_argument("--live", action="store_true")
    provider.add_argument("--timeout", type=float, default=30)
    _add_output_args(provider)
    diagnose_route = diagnose_sub.add_parser("route")
    diagnose_route.add_argument("query")
    diagnose_route.add_argument("--validation", choices=["fast", "balanced", "strict"], default="")
    diagnose_route.add_argument("--router-mode", choices=["hybrid", "rules", "off"], default="")
    _add_output_args(diagnose_route)
    calibrate = diagnose_sub.add_parser("route-calibrate")
    calibrate.add_argument("--models", default="")
    _add_output_args(calibrate)
    diagnose_smoke = diagnose_sub.add_parser("smoke")
    diagnose_smoke.add_argument("--mode", choices=["mock", "live"], default="mock")
    _add_output_args(diagnose_smoke)

    config = sub.add_parser("config", help="Read or edit the local config file.")
    config_sub = config.add_subparsers(dest="config_command", required=True, parser_class=SmartSearchArgumentParser)
    for name in ("path", "list"):
        item = config_sub.add_parser(name)
        _add_output_args(item)
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    _add_output_args(config_set)
    config_unset = config_sub.add_parser("unset")
    config_unset.add_argument("key")
    _add_output_args(config_unset)

    skills = sub.add_parser("skills", help="Install, inspect, update, or uninstall bundled Agent skills.")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True, parser_class=SmartSearchArgumentParser)
    for name in ("install", "uninstall", "status", "update"):
        item = skills_sub.add_parser(name)
        item.add_argument("name", nargs="?", default=SKILL_NAME)
        _add_skill_selection_args(item, include_copy=name == "install")
        _add_output_args(item)

    dev = sub.add_parser("dev", help="Developer commands.")
    dev_sub = dev.add_subparsers(dest="dev_command", required=True, parser_class=SmartSearchArgumentParser)
    regression = dev_sub.add_parser("regression")
    _add_output_args(regression)
    return parser


def _setup_argument_values(args: argparse.Namespace) -> dict[str, str]:
    return {
        "SEARCH_ANSWER_API_URL": args.search_answer_api_url,
        "SEARCH_ANSWER_API_KEY": args.search_answer_api_key,
        "SEARCH_ANSWER_MODEL": args.search_answer_model,
        "SEARCH_ANSWER_TOOLS": args.search_answer_tools,
        "EXA_API_KEY": args.exa_api_key,
        "EXA_BASE_URL": args.exa_base_url,
        "EXA_SEARCH_TYPE": args.exa_search_type,
        "CONTEXT7_API_KEY": args.context7_api_key,
        "CONTEXT7_BASE_URL": args.context7_base_url,
        "ZHIPU_MCP_API_KEY": args.zhipu_mcp_api_key,
        "ZHIPU_MCP_ZREAD_API_URL": args.zhipu_mcp_zread_api_url,
        "FIRECRAWL_API_KEY": args.firecrawl_api_key,
        "FIRECRAWL_API_URL": args.firecrawl_api_url,
    }


def _setup_required_keys() -> list[str]:
    return [
        "SEARCH_ANSWER_API_URL",
        "SEARCH_ANSWER_API_KEY",
        "SEARCH_ANSWER_MODEL",
        "EXA_API_KEY",
        "CONTEXT7_API_KEY",
        "ZHIPU_MCP_API_KEY",
        "FIRECRAWL_API_KEY",
    ]


def _is_secret_key(key: str) -> bool:
    return key.endswith("_API_KEY")


def _masked_value(key: str, value: str) -> str:
    if not value:
        return "(missing)"
    if not _is_secret_key(key):
        return value
    return "****" + value[-4:] if len(value) > 4 else "****"


def _current_setup_value(key: str, saved: dict[str, str]) -> tuple[str, str]:
    source = service.config.get_config_source(key)
    if source == "environment":
        return os.getenv(key, ""), source
    return saved.get(key, ""), source


def _setup_values(args: argparse.Namespace) -> dict[str, str]:
    explicit = _setup_argument_values(args)
    if args.non_interactive:
        return {key: value for key, value in explicit.items() if value != ""}

    prompt_ui.require_tty(
        "Interactive setup requires a terminal; use --non-interactive with explicit provider options"
    )
    saved = service.config.get_saved_config(masked=False)
    legacy = service.config.legacy_search_answer_values()

    for key in _setup_required_keys():
        if explicit.get(key):
            continue
        current, source = _current_setup_value(key, saved)
        if source == "environment" and current:
            if not prompt_ui.confirm(
                f"{key} is provided by the environment. Continue using it?",
                default=True,
            ):
                raise InteractivePromptError(
                    f"{key} is managed by the environment; change or unset that environment variable before rerunning setup"
                )
            continue
        if current and prompt_ui.confirm(
            f"Keep current {key} ({_masked_value(key, current)})?",
            default=True,
        ):
            continue
        if not current and key in legacy:
            origin, old_value = legacy[key]
            if prompt_ui.confirm(f"Reuse {origin} ({_masked_value(key, old_value)}) as {key}?", default=True):
                explicit[key] = old_value
                continue
        value = (
            prompt_ui.secret(key, required=True)
            if _is_secret_key(key)
            else prompt_ui.text(key, default=current, required=True)
        )
        explicit[key] = value
    return {key: value for key, value in explicit.items() if value != ""}


def _skill_scope(args: argparse.Namespace, *, non_interactive: bool = False) -> str:
    if getattr(args, "global_scope", False):
        return "global"
    if getattr(args, "project_scope", False):
        return "project"
    if non_interactive or getattr(args, "yes", False):
        return "project"
    prompt_ui.require_tty(
        "Interactive skill selection requires a terminal; use --project/--global, --agent and --yes"
    )
    return str(prompt_ui.select(
        "Skill scope",
        [
            {"name": "Project - current working directory", "value": "project"},
            {"name": "Global - current user", "value": "global"},
        ],
        default="project",
    ))


def _skill_targets(args: argparse.Namespace, scope: str, *, non_interactive: bool = False) -> list[str]:
    if getattr(args, "all_agents", False):
        return [target.target_id for target in SKILL_TARGETS if scope == "project" or target.global_root is not None]
    explicit = parse_skill_targets(getattr(args, "agents", []))
    if explicit:
        return explicit

    detected = detect_skill_targets(scope)
    if non_interactive or getattr(args, "yes", False):
        if detected:
            return detected
        raise SkillInstallError("No Agent was detected; specify --agent or --all-agents")

    prompt_ui.require_tty(
        "Interactive skill selection requires a terminal; use --project/--global, --agent and --yes"
    )
    candidates = [target for target in SKILL_TARGETS if scope == "project" or target.global_root is not None]
    choices = [
        {
            "name": f"{target.label} (detected)" if target.target_id in detected else target.label,
            "value": target.target_id,
        }
        for target in candidates
    ]
    return list(prompt_ui.checkbox(
        "Agent targets",
        choices,
        enabled=[target.target_id for target in candidates if target.target_id in detected],
        required=True,
    ))


def _show_skill_preview(scope: str, targets: list[str], skill_name: str) -> None:
    print(f"Canonical: {canonical_skill_path(skill_name, scope=scope)}", file=sys.stderr)
    for target_id in targets:
        print(f"  {target_id}: {skill_target_path(target_id, scope, skill_name=skill_name)}", file=sys.stderr)


def _skill_copy_mode(
    args: argparse.Namespace,
    scope: str,
    targets: list[str],
    *,
    non_interactive: bool = False,
) -> bool:
    if getattr(args, "copy", False):
        return True
    if non_interactive or getattr(args, "yes", False):
        return False
    canonical = canonical_skill_path(SKILL_NAME, scope=scope)
    if targets and all(skill_target_path(target, scope) == canonical for target in targets):
        return False
    prompt_ui.require_tty(
        "Interactive skill selection requires a terminal; use --copy or --yes"
    )
    return prompt_ui.select(
        "Installation method",
        [
            {"name": "Symlink (Recommended) - single source of truth", "value": "symlink"},
            {"name": "Copy - independent copies", "value": "copy"},
        ],
        default="symlink",
    ) == "copy"


def _skill_scope_from_args(args: argparse.Namespace, *, non_interactive: bool = False) -> str:
    selected = getattr(args, "_selected_skill_scope", "")
    if selected:
        return selected
    scope = _skill_scope(args, non_interactive=non_interactive)
    args._selected_skill_scope = scope
    return scope


def _run_skill_command(args: argparse.Namespace) -> dict[str, Any]:
    names = parse_skill_names(args.name)
    scope = _skill_scope_from_args(args)
    targets = _skill_targets(args, scope)
    if not targets:
        raise SkillInstallError("No Agent target selected")
    copy_mode = _skill_copy_mode(args, scope, targets) if args.skills_command == "install" else False
    mutating = args.skills_command in {"install", "uninstall", "update"}
    if mutating and not args.yes:
        prompt_ui.require_tty(
            "Interactive skill confirmation requires a terminal; pass --yes after reviewing --project/--global and --agent"
        )
        for skill_name in names:
            _show_skill_preview(scope, targets, skill_name)
        if not prompt_ui.confirm(f"Continue with skills {args.skills_command}?", default=False):
            return {"ok": True, "cancelled": True, "operation": args.skills_command}

    results: list[dict[str, Any]] = []
    for skill_name in names:
        kwargs = {"scope": scope, "skill_name": skill_name}
        if args.skills_command == "install":
            result = install_skill_targets(targets, copy=copy_mode, **kwargs)
        elif args.skills_command == "uninstall":
            result = uninstall_skill_targets(targets, **kwargs)
        elif args.skills_command == "update":
            result = update_skill_targets(targets, **kwargs)
        else:
            result = status_skill_targets(targets, **kwargs)
        results.append(result)
    if len(results) == 1:
        return results[0]
    return {"ok": all(result.get("ok") for result in results), "operation": args.skills_command, "results": results}


def _setup_skill_plan(args: argparse.Namespace) -> dict[str, Any] | None:
    explicit_targets = bool(args.agents or args.all_agents)
    if args.non_interactive and not explicit_targets:
        return None
    if not args.non_interactive and not explicit_targets and not prompt_ui.confirm("Install the bundled Agent skill?", default=False):
        return None
    scope = _skill_scope_from_args(args, non_interactive=args.non_interactive)
    targets = _skill_targets(args, scope, non_interactive=args.non_interactive)
    if not targets:
        return None
    copy_mode = _skill_copy_mode(args, scope, targets, non_interactive=args.non_interactive)
    return {"scope": scope, "targets": targets, "copy": copy_mode}


def _show_setup_preview(values: dict[str, str], skill_plan: dict[str, Any] | None) -> None:
    saved = service.config.get_saved_config(masked=False)
    print("Configuration summary:", file=sys.stderr)
    keys = list(dict.fromkeys(_setup_required_keys() + sorted(values)))
    for key in keys:
        current, source = _current_setup_value(key, saved)
        value = values.get(key, current)
        if value:
            value_source = "new" if key in values else source
            print(f"  {key}: {_masked_value(key, value)} ({value_source})", file=sys.stderr)
    if skill_plan:
        print("Skill installation:", file=sys.stderr)
        _show_skill_preview(skill_plan["scope"], skill_plan["targets"], SKILL_NAME)
        print(f"  method: {'copy' if skill_plan['copy'] else 'symlink/direct'}", file=sys.stderr)


def _run_setup(args: argparse.Namespace) -> dict[str, Any]:
    values = _setup_values(args)
    skill_plan = _setup_skill_plan(args)
    if not args.non_interactive and not args.yes:
        _show_setup_preview(values, skill_plan)
        if not prompt_ui.confirm("Apply this setup?", default=False):
            return {
                "ok": True,
                "cancelled": True,
                "config_file": str(service.config.config_file),
                "saved": [],
                "errors": [],
                "skill_install": None,
            }

    errors = []
    for key, value in values.items():
        result = service.config_set(key, value)
        if not result.get("ok"):
            errors.append(result.get("error", key))
    skill_install = None
    if not errors and skill_plan:
        skill_install = install_skill_targets(
            skill_plan["targets"],
            scope=skill_plan["scope"],
            copy=skill_plan["copy"],
        )
    return {
        "ok": not errors and (skill_install is None or skill_install.get("ok", False)),
        "config_file": str(service.config.config_file),
        "saved": sorted(values),
        "errors": errors,
        "skill_install": skill_install,
    }


async def _run_async(args: argparse.Namespace) -> int:
    if args.command == "search":
        data = await service.search_answer(args.query, timeout_seconds=args.timeout, debug=args.debug) if args.operation == "answer" else await service.search_sources(args.query, limit=args.limit, start_published_date=args.start_published_date, include_domains=args.include_domains, exclude_domains=args.exclude_domains, category=args.category, include_text=args.include_text, include_highlights=args.include_highlights, debug=args.debug)
    elif args.command == "docs":
        if args.operation == "resolve":
            data = await service.docs_resolve(args.name, args.query, debug=args.debug)
        elif args.operation == "search":
            data = await service.docs_search(args.query, source=args.source, debug=args.debug)
        elif args.operation == "tree":
            data = await service.docs_tree(args.repo, path=args.path, debug=args.debug)
        else:
            data = await service.docs_read(args.repo, args.path, debug=args.debug)
    elif args.command == "fetch":
        if args.operation == "content":
            data = await service.fetch_content(args.url, debug=args.debug)
        else:
            try:
                schema = json.loads(args.schema) if args.schema else None
            except json.JSONDecodeError as exc:
                data = {"ok": False, "capability": "fetch", "operation": "extract", "content": "", "sources": [], "elapsed_ms": 0, "data": None, "error_type": "parameter_error", "error": f"--schema must be valid JSON: {exc}"}
            else:
                data = await service.fetch_extract(args.url, max_length=args.max_length, schema=schema, prompt=args.prompt, debug=args.debug)
    elif args.command == "map":
        data = await service.map_site_operation(args.url, search=args.search, sitemap=args.sitemap, include_subdomains=args.include_subdomains, ignore_query_parameters=args.ignore_query_parameters, ignore_cache=args.ignore_cache, limit=args.limit, timeout=args.timeout, location=args.location, debug=args.debug)
    elif args.command == "doctor":
        data = await service.doctor()
    elif args.command == "diagnose":
        if args.diagnose_command in {"search", "docs", "fetch", "map"}:
            data = await service.diagnose_operation(args.diagnose_command, args.operation)
        elif args.diagnose_command == "provider":
            data = await service.diagnose_provider(args.provider, live=args.live, timeout_seconds=args.timeout)
        elif args.diagnose_command == "route":
            data = await service.route(args.query, validation=args.validation, mode=args.router_mode)
        elif args.diagnose_command == "route-calibrate":
            data = await service.route_calibrate(args.models)
        else:
            data = await service.smoke(args.mode)
    elif args.command == "config":
        if args.config_command == "path":
            data = service.config_path()
        elif args.config_command == "list":
            data = service.config_list()
        elif args.config_command == "set":
            data = service.config_set(args.key, args.value)
        else:
            data = service.config_unset(args.key)
    else:
        data = await service.smoke("mock")
    return _print_result(data, args.format, args.output)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "setup":
            return _print_result(_run_setup(args), args.format, args.output)
        if args.command == "skills":
            return _print_result(_run_skill_command(args), args.format, args.output)
        return asyncio.run(_run_async(args))
    except (SkillInstallError, InteractivePromptError) as exc:
        return _print_result(
            {"ok": False, "error_type": "parameter_error", "error": str(exc)},
            getattr(args, "format", "json"),
            getattr(args, "output", ""),
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
