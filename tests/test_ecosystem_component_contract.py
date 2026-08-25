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
    assert manifest["integration_status"] == "contract_only"
    assert manifest["authority"] == "none"
    assert manifest["package"] == {
        "name": "ai-agent-handoff",
        "version": "0.2.0",
        "install": "pip install .",
        "entry_points": ["agent-guard"],
    }
    assert manifest["compatibility"] == {
        "harness_api": "not-yet-declared",
        "python": ">=3.11",
        "platforms": {
            "supported": ["linux", "windows"],
            "tested": ["linux"],
        },
    }
    assert manifest["owns"]["modules"] == ["M13-handoff-edge"]
    assert "installable Agentic Security Harness extension today" in manifest["non_claims"]


def test_component_manifest_document_refs_exist_and_classify_legacy_projection() -> None:
    manifest = _manifest()
    docs = manifest["docs"]
    roles = {item["path"]: item["role"] for item in docs}

    assert all(item["role"] in DOC_ROLES for item in docs)
    assert roles["README.md"] == "component-front-door"
    assert roles["docs/component-roadmap.md"] == "component-owned"
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
    assert "contract-only" in readme
    assert "not yet an installable `ash` extension" in readme
    assert "`contract_only`" in roadmap
    assert "Historical R4 projection" in legacy
