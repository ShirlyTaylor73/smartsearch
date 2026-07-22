import argparse
import asyncio
import json
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from . import service
from .skill_installer import DEFAULT_SKILL_TARGET_IDS, SkillInstallError, install_skill_targets, parse_skill_targets, status_skill_targets


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
    answer = search_sub.add_parser("answer", help="Generate a Grok web-backed answer.")
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
    extract = fetch_sub.add_parser("extract")
    extract.add_argument("url")
    extract.add_argument("--schema", default="")
    extract.add_argument("--max-length", type=int, default=20000)
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
    setup.add_argument("--grok-transport", choices=["xai-responses", "openai-compatible"], default="")
    for flag in (
        "xai-api-url", "xai-api-key", "xai-model", "xai-tools",
        "openai-compatible-api-url", "openai-compatible-api-key", "openai-compatible-model", "openai-compatible-stream",
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
    provider.add_argument("provider", choices=["xai-responses", "openai-compatible", "exa", "context7", "zhipu-mcp-zread", "firecrawl"])
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

    skills = sub.add_parser("skills", help="Inspect or update bundled Agent skills.")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True, parser_class=SmartSearchArgumentParser)
    for name in ("status", "update"):
        item = skills_sub.add_parser(name)
        item.add_argument("--targets", default=",".join(DEFAULT_SKILL_TARGET_IDS))
        item.add_argument("--project-root", default="")
        item.add_argument("--source-root", default="")
        _add_output_args(item)

    dev = sub.add_parser("dev", help="Developer commands.")
    dev_sub = dev.add_subparsers(dest="dev_command", required=True, parser_class=SmartSearchArgumentParser)
    regression = dev_sub.add_parser("regression")
    _add_output_args(regression)
    return parser


def _setup_values(args: argparse.Namespace) -> dict[str, str]:
    transport = args.grok_transport
    if not transport and not args.non_interactive:
        transport = input("Grok transport [openai-compatible/xai-responses]: ").strip() or "openai-compatible"
    if not transport:
        transport = service.config.grok_transport
    mapping = {
        "SMART_SEARCH_GROK_TRANSPORT": transport,
        "XAI_API_URL": args.xai_api_url,
        "XAI_API_KEY": args.xai_api_key,
        "XAI_MODEL": args.xai_model,
        "XAI_TOOLS": args.xai_tools,
        "OPENAI_COMPATIBLE_API_URL": args.openai_compatible_api_url,
        "OPENAI_COMPATIBLE_API_KEY": args.openai_compatible_api_key,
        "OPENAI_COMPATIBLE_MODEL": args.openai_compatible_model,
        "OPENAI_COMPATIBLE_STREAM": args.openai_compatible_stream,
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
    if not args.non_interactive:
        required = ["XAI_API_KEY"] if transport == "xai-responses" else ["OPENAI_COMPATIBLE_API_URL", "OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_MODEL"]
        required += ["EXA_API_KEY", "CONTEXT7_API_KEY", "ZHIPU_MCP_API_KEY", "FIRECRAWL_API_KEY"]
        for key in required:
            if not mapping.get(key):
                mapping[key] = input(f"{key}: ").strip()
    return {key: value for key, value in mapping.items() if value != ""}


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
                data = await service.fetch_extract(args.url, max_length=args.max_length, schema=schema, debug=args.debug)
    elif args.command == "map":
        data = await service.map_site_operation(args.url, search=args.search, sitemap=args.sitemap, include_subdomains=args.include_subdomains, ignore_query_parameters=args.ignore_query_parameters, ignore_cache=args.ignore_cache, limit=args.limit, timeout=args.timeout, location=args.location, debug=args.debug)
    elif args.command == "setup":
        values = _setup_values(args)
        errors = []
        for key, value in values.items():
            result = service.config_set(key, value)
            if not result.get("ok"):
                errors.append(result.get("error", key))
        data = {"ok": not errors, "config_file": str(service.config.config_file), "saved": sorted(values), "errors": errors}
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
    elif args.command == "skills":
        try:
            targets = parse_skill_targets(args.targets)
            kwargs = {"project_root": args.project_root or None, "source_root": args.source_root or None}
            data = status_skill_targets(targets, **kwargs) if args.skills_command == "status" else install_skill_targets(targets, **kwargs)
        except SkillInstallError as exc:
            data = {"ok": False, "error_type": "parameter_error", "error": str(exc)}
    else:
        data = await service.smoke("mock")
    return _print_result(data, args.format, args.output)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run_async(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
