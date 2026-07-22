import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOLVER = ROOT / "npm" / "scripts" / "resolve-prerelease-version.js"
WORKFLOW = ROOT / ".github" / "workflows" / "publish-npm.yml"
PACKAGE_NAME = "@shirlytaylor73/smart-search"


def read_reference_tree(skill_dir: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((skill_dir / "references").rglob("*"))
        if path.is_file() and path.suffix == ".md"
    )


def run_resolver(base_version: str, versions: list[str]) -> str:
    result = subprocess.run(
        [
            "node",
            str(RESOLVER),
            "--package",
            PACKAGE_NAME,
            "--base",
            base_version,
            "--id",
            "beta",
            "--versions-json",
            json.dumps(versions),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def test_resolver_counts_legacy_dev_slots_per_base_version():
    versions = [
        "0.1.9-dev.30",
        "0.1.9",
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10",
    ]

    assert run_resolver("0.1.9", versions) == "0.1.9-beta.2"
    assert run_resolver("0.1.10", versions) == "0.1.10-beta.3"


def test_resolver_prefers_existing_beta_numbers_when_higher_than_legacy_count():
    versions = [
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10-beta.5",
        "0.1.10",
    ]

    assert run_resolver("0.1.10", versions) == "0.1.10-beta.6"


def test_resolver_starts_at_beta_one_without_prior_versions():
    assert run_resolver("0.3.0", []) == "0.3.0-beta.1"


def test_package_metadata_belongs_to_fork_and_uses_breaking_release_version():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))

    assert package["name"] == PACKAGE_NAME
    assert package["version"] == "0.3.0-beta.1"
    assert package["homepage"] == "https://github.com/ShirlyTaylor73/smartsearch#readme"
    assert package["repository"]["url"] == "git+https://github.com/ShirlyTaylor73/smartsearch.git"
    assert package["bugs"]["url"] == "https://github.com/ShirlyTaylor73/smartsearch/issues"
    assert package_lock["name"] == PACKAGE_NAME
    assert package_lock["version"] == "0.3.0-beta.1"
    assert package_lock["packages"][""]["name"] == PACKAGE_NAME


def test_publish_workflow_uses_manual_beta_tag_stable_and_token_auth():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "branches:" not in workflow
    assert 'tags:\n      - "v*"' in workflow
    assert "github.event.inputs.target_ref" in workflow
    assert "github.event.inputs.version" in workflow
    assert "github.event.inputs.npm_tag" in workflow
    assert 'tag="next"' in workflow
    assert 'tag="latest"' in workflow
    assert "Refusing to publish prerelease version" in workflow
    assert "NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}" in workflow
    assert "npm publish --access public --provenance" in workflow
    assert 'expected_package="@shirlytaylor73/smart-search"' in workflow
    assert 'notes_file=".github/releases/v${version}.md"' in workflow
    assert 'notes_footer="$(printf' in workflow
    assert "gh release create" in workflow
    assert "--prerelease" in workflow


def test_release_docs_explain_new_package_and_migration():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    public_contract = read_reference_tree(ROOT / "skills" / "smart-search-cli")
    packaged_contract = read_reference_tree(
        ROOT / "src" / "smart_search" / "assets" / "skills" / "smart-search-cli"
    )

    required_markers = ["@shirlytaylor73/smart-search@next", "Python", "0.3.0-beta", "Exa", "Firecrawl"]
    for marker in required_markers:
        assert marker in readme

    zh_required_markers = ["@shirlytaylor73/smart-search@next", "Python", "0.3.0-beta", "Exa", "Firecrawl"]
    for marker in zh_required_markers:
        assert marker in readme_zh

    contract_markers = ["0.3.0-beta.N", "@shirlytaylor73/smart-search", "npm versions are immutable"]
    for marker in contract_markers:
        assert marker in public_contract
        assert marker in packaged_contract


def test_current_stable_release_notes_describe_user_visible_changes():
    notes = (ROOT / ".github" / "releases" / "v0.2.0.md").read_text(encoding="utf-8")

    required_markers = [
        "@shirlytaylor73/smart-search",
        "0.2.0",
        "search answer",
        "docs search",
        "fetch content",
        "map site",
        "AnySearch",
        "Deep Research",
    ]
    for marker in required_markers:
        assert marker in notes
