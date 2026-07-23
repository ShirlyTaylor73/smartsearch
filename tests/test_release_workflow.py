import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOLVER = ROOT / "npm" / "scripts" / "resolve-prerelease-version.js"
WORKFLOW = ROOT / ".github" / "workflows" / "publish-npm.yml"
PACKAGE_NAME = "@shirlytaylor73/smart-search"


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
    assert package["version"] == "0.3.0-beta.2"
    assert package["homepage"] == "https://github.com/ShirlyTaylor73/smartsearch#readme"
    assert package["repository"]["url"] == "git+https://github.com/ShirlyTaylor73/smartsearch.git"
    assert package["bugs"]["url"] == "https://github.com/ShirlyTaylor73/smartsearch/issues"
    assert package_lock["name"] == PACKAGE_NAME
    assert package_lock["version"] == "0.3.0-beta.2"
    assert package_lock["packages"][""]["name"] == PACKAGE_NAME


def test_publish_workflow_uses_manual_beta_tag_stable_and_trusted_publishing():
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
    assert "id-token: write" in workflow
    assert "package-manager-cache: false" in workflow
    assert "NODE_AUTH_TOKEN" not in workflow
    assert "npm whoami" not in workflow
    assert "npm publish --access public --tag" in workflow
    assert 'expected_package="@shirlytaylor73/smart-search"' in workflow
    assert 'notes_file=".github/releases/v${version}.md"' in workflow
    assert 'notes_footer="$(printf' in workflow
    assert "gh release create" in workflow
    assert "--prerelease" in workflow


def test_release_docs_explain_new_package_and_migration():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    required_markers = ["@shirlytaylor73/smart-search@next", "Python", "0.3.0-beta", "Exa", "Firecrawl"]
    for marker in required_markers:
        assert marker in readme

    zh_required_markers = ["@shirlytaylor73/smart-search@next", "Python", "0.3.0-beta", "Exa", "Firecrawl"]
    for marker in zh_required_markers:
        assert marker in readme_zh

    npx_markers = [
        "npx --yes --package=@shirlytaylor73/smart-search@next",
        "smart-search skills install --project --agent codex --yes",
    ]
    for marker in npx_markers:
        assert marker in readme
        assert marker in readme_zh


def test_npx_skill_installation_is_part_of_package_validation():
    package_test = (ROOT / "npm" / "scripts" / "test.js").read_text(encoding="utf-8")
    npx_test = (ROOT / "npm" / "scripts" / "test-npx-skill-install.js").read_text(encoding="utf-8")

    assert "test-npx-skill-install.js" in package_test
    assert '"--yes"' in npx_test
    assert "--package=" in npx_test
    assert '"skills"' in npx_test
    assert '"install"' in npx_test
    assert '"--project"' in npx_test
    assert '"--agent"' in npx_test
    assert '"codex"' in npx_test


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
