from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "component.yaml"

TOP_LEVEL_KEYS = {
    "schema_version",
    "component_id",
    "display_name",
    "repository",
    "visibility",
    "kind",
    "summary",
    "package",
    "owns",
    "consumes",
    "contracts",
    "docs",
    "compatibility",
    "integration_status",
    "evidence_refs",
    "claims",
    "non_claims",
    "authority",
}
DOC_ROLES = {
    "canonical",
    "component-owned",
    "component-front-door",
    "generated",
    "generated-current-snapshot",
    "generated-ecosystem-view",
    "current-snapshot",
    "research",
    "historical",
    "superseded",
}


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_component_manifest_matches_central_v1_shape_and_local_boundary() -> None:
    manifest = _manifest()

    assert set(manifest) == TOP_LEVEL_KEYS
    assert manifest["schema_version"] == "AgenticSecurityEcosystemComponent.v1"
    assert manifest["component_id"] == "ai-agent-handoff"
    assert manifest["visibility"] == "public"
    assert manifest["kind"] == "check_extension"
    assert manifest["integration_status"] == "extension_candidate"
    assert manifest["authority"] == "none"
    assert manifest["package"] == {
        "name": "ai-agent-handoff",
        "version": "0.3.0",
        "install": "pip install .",
        "entry_points": ["agent-guard"],
    }
    assert manifest["compatibility"] == {
        "harness_api": "1",
        "python": ">=3.11",
        "platforms": {
            "supported": ["linux", "windows"],
            "tested": ["linux", "windows"],
        },
    }
    assert manifest["owns"]["modules"] == ["M13-handoff-edge"]
    assert (
        "published or automatically installed Agentic Security Harness extension"
        in manifest["non_claims"]
    )


def test_component_manifest_document_refs_exist_and_classify_legacy_projection() -> None:
    manifest = _manifest()
    docs = manifest["docs"]
    roles = {item["path"]: item["role"] for item in docs}

    assert all(item["role"] in DOC_ROLES for item in docs)
    assert roles["README.md"] == "component-front-door"
    assert roles["docs/component-roadmap.md"] == "component-owned"
    assert roles["docs/package-ci.md"] == "component-owned"
    assert roles["docs/harness-extension.md"] == "component-owned"
    for path in (
        "docs/security-portfolio-roadmap.md",
        "docs/security-portfolio-roadmap-public.yaml",
        "docs/security-portfolio-roadmap-contract.json",
    ):
        assert roles[path] == "historical"

    for path in roles:
        candidate = (ROOT / path).resolve()
        assert ROOT.resolve() in candidate.parents
        assert candidate.is_file()
        assert not candidate.is_symlink()


def test_component_docs_link_the_current_ecosystem_without_promoting_integration() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "component-roadmap.md").read_text(encoding="utf-8")
    legacy = (ROOT / "docs" / "security-portfolio-roadmap.md").read_text(encoding="utf-8")

    for text in (readme, roadmap, legacy):
        assert "agentic-security-harness/blob/main/docs/ecosystem-roadmap.md" in text
    assert "extension candidate" in readme
    assert "not published, automatically" in readme
    assert "`extension_candidate`" in roadmap
    assert "Historical R4 projection" in legacy


def test_install_docs_distinguish_source_extra_from_public_packages() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    extension = (ROOT / "docs" / "harness-extension.md").read_text(encoding="utf-8")

    for text in (readme, extension):
        normalized = " ".join(text.split())
        assert "Harness `main`" in normalized
        assert "published Harness `v1.3.0` metadata does not contain" in normalized
    assert "Public\n`pip install agentic-security-harness[handoff]` support" in readme
    assert "public extra command is unavailable" in extension
    assert "released or automatically installed" in " ".join(extension.split())
