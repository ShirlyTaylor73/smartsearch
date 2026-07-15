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


def test_agent_skill_exposes_operation_contract_only():
    text = (PUBLIC_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for marker in (
        "search answer",
        "search sources",
        "search similar",
        "docs resolve",
        "docs search",
        "docs tree",
        "docs read",
        "fetch content",
        "fetch extract",
        "map site",
    ):
        assert marker in text
    for removed in ("anysearch-search", "anysearch-domains", "smart-search deep", "smart-search research"):
        assert removed not in text


def test_readmes_document_new_command_tree_and_removed_features():
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for marker in ("search answer", "search sources", "docs resolve", "docs tree", "fetch content", "fetch extract", "map site"):
            assert marker in text
        assert "AnySearch" not in text
        assert "smart-search research" not in text


def test_source_tree_has_no_anysearch_module():
    assert not (ROOT / "src" / "smart_search" / "providers" / "anysearch.py").exists()
