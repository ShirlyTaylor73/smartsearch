from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SKILL_DIR = ROOT / "skills" / "smart-search-cli"
PACKAGED_SKILL_DIR = ROOT / "src" / "smart_search" / "assets" / "skills" / "smart-search-cli"


def test_public_and_packaged_skill_files_match():
    public = {path.relative_to(PUBLIC_SKILL_DIR) for path in PUBLIC_SKILL_DIR.rglob("*") if path.is_file()}
    packaged = {path.relative_to(PACKAGED_SKILL_DIR) for path in PACKAGED_SKILL_DIR.rglob("*") if path.is_file()}
    assert public == packaged
    for relative in public:
        assert (PUBLIC_SKILL_DIR / relative).read_bytes() == (PACKAGED_SKILL_DIR / relative).read_bytes()


def test_agent_skill_is_a_compact_navigation_entrypoint():
    skill = PUBLIC_SKILL_DIR / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 60
    for marker in (
        "search answer",
        "search sources",
        "docs resolve",
        "docs search",
        "docs tree",
        "docs read",
        "fetch content",
        "fetch extract",
        "map site",
        "references/common.md",
        "references/search.md",
        "references/docs.md",
        "references/fetch.md",
        "references/map.md",
    ):
        assert marker in text


def test_agent_skill_references_document_the_current_cli_parameters():
    expected_files = {
        Path("SKILL.md"),
        Path("agents/openai.yaml"),
        Path("references/common.md"),
        Path("references/search.md"),
        Path("references/docs.md"),
        Path("references/fetch.md"),
        Path("references/map.md"),
    }
    actual_files = {
        path.relative_to(PUBLIC_SKILL_DIR)
        for path in PUBLIC_SKILL_DIR.rglob("*")
        if path.is_file()
    }
    assert actual_files == expected_files

    references = {
        name: (PUBLIC_SKILL_DIR / "references" / name).read_text(encoding="utf-8")
        for name in ("common.md", "search.md", "docs.md", "fetch.md", "map.md")
    }
    for marker in ("--format", "--output", "--debug", "--help", "--version", "error_type", "error"):
        assert marker in references["common.md"]
    for marker in (
        "--timeout",
        "--limit",
        "--start-published-date",
        "--include-domains",
        "--exclude-domains",
        "--category",
        "--include-text",
        "--include-highlights",
    ):
        assert marker in references["search.md"]
    for marker in ("NAME", "QUERY", "--source", "REPO", "--path", "PATH"):
        assert marker in references["docs.md"]
    for marker in ("URL", "--schema", "--max-length", "raw_evidence", "data"):
        assert marker in references["fetch.md"]
    for marker in (
        "--search",
        "--sitemap",
        "--include-subdomains",
        "--no-include-subdomains",
        "--ignore-query-parameters",
        "--no-ignore-query-parameters",
        "--ignore-cache",
        "--limit",
        "--timeout",
        "--location",
    ):
        assert marker in references["map.md"]


def test_agent_skill_contains_only_current_agent_usage_guidance():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PUBLIC_SKILL_DIR.rglob("*")
        if path.is_file()
    ).lower()
    for excluded in (
        "provider",
        "fallback",
        "deprecated",
        "removed",
        "migration",
        "search similar",
        "tavily",
        "anysearch",
        "deep research",
        "npm",
        "release",
        "0.3.0",
    ):
        assert excluded not in text


def test_readmes_document_new_command_tree_and_removed_features():
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for marker in ("search answer", "search sources", "docs resolve", "docs tree", "fetch content", "fetch extract", "map site"):
            assert marker in text
        assert "AnySearch" not in text
        assert "smart-search research" not in text


def test_source_tree_has_no_anysearch_module():
    assert not (ROOT / "src" / "smart_search" / "providers" / "anysearch.py").exists()
