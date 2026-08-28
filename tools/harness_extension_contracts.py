"""Generate the source-owned Handoff Harness extension compatibility manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "extensions" / "harness-v1"
OUTPUT = ROOT / "contracts" / "harness-extension-v1.manifest.json"
HARNESS_HEAD = "c1dd69856212458ae952e43aeb2b0cc9290e8205"
HARNESS_TREE = "596c189e8b15ceaf7bf28337546655e23d47d3ef"
HARNESS_BINDINGS = {
    "src/agentic_security_harness/__init__.py": (
        "eb7aa2e995bcdc8381d6598a0c6900514ec09c46b1da19b450c7aeb0f75800f5"
    ),
    "src/agentic_security_harness/extension_distribution.py": (
        "e8bf5c2792e271c7363a7b51ce4f0450472649d1216099aea79a19915339a6e6"
    ),
    "src/agentic_security_harness/extension_lifecycle.py": (
        "22b0a23599ee3b48cb1d36f63f38ff1da0366cf79aa70403e02e7c487d7f9b59"
    ),
    "src/agentic_security_harness/extension_sdk.py": (
        "6135b948564bc5c563a7990160537151453c5b1b03e21f21fe5fea9699d3e7cb"
    ),
    "src/agentic_security_harness/portfolio_contract.py": (
        "d4af2870e5545abc6d8a5d7861cc5e0f083b7cd3d3ba21c9f0079a3f2d4da0c9"
    ),
}
LOCAL_BINDINGS = {
    "attributes": ".gitattributes",
    "backend": "extensions/harness-v1/handoff_extension_backend.py",
    "component": "component.yaml",
    "configuration": "extensions/harness-v1/ash-extension-config.json",
    "documentation": "docs/harness-extension.md",
    "extension_documentation": "extensions/harness-v1/README.md",
    "generator": "tools/harness_extension_contracts.py",
    "implementation": "extensions/harness-v1/src/ai_agent_handoff_harness_extension.py",
    "nested_project": "extensions/harness-v1/pyproject.toml",
    "package_smoke": "tools/package_smoke.py",
    "source_manifest": "MANIFEST.in",
    "tests": "tests/test_harness_extension_distribution.py",
    "test_bootstrap": "tests/conftest.py",
    "workflow": ".github/workflows/tests.yml",
}


def _sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8") + b"\n"


def generated_manifest() -> bytes:
    backend: dict[str, Any] = runpy.run_path(
        str(EXTENSION_ROOT / "handoff_extension_backend.py")
    )
    source = (EXTENSION_ROOT / "src" / "ai_agent_handoff_harness_extension.py").read_bytes()
    configuration = (EXTENSION_ROOT / "ash-extension-config.json").read_bytes()
    extension_manifest = backend["_manifest"](source, configuration)
    payload = {
        "artifact_boundary": {
            "entry_point_count": 1,
            "entry_point_group": "agentic_security_harness.extensions.v1",
            "entry_point_name": "ai-agent-handoff.validation",
            "requires_dist": [],
            "requires_python": ">=3.11,<3.14",
            "wheel_file_count": 6,
            "wheel_tag": "py3-none-any",
        },
        "authority": "none",
        "dependency_boundary": {
            "harness": "agentic-security-harness>=1.3,<2",
            "handoff": "ai-agent-handoff>=0.3,<1",
            "resolver_enforced": False,
            "semantics": "operator_preflight_only",
        },
        "extension_id": "ai-agent-handoff.validation",
        "extension_manifest_sha256": hashlib.sha256(extension_manifest).hexdigest(),
        "extension_version": "1.0.0",
        "handoff_source": {
            "base_head": "f4e51e0603497f63c62453fc4030319fdfc5ac04",
            "base_tree": "78311595f72469748469a1dfd4dc4a286244159f",
        },
        "harness_api": "1",
        "harness_reference": {
            "bindings": [
                {"path": path, "sha256": digest}
                for path, digest in sorted(HARNESS_BINDINGS.items())
            ],
            "head": HARNESS_HEAD,
            "published_package_candidate": False,
            "tree": HARNESS_TREE,
        },
        "local_bindings": [
            {
                "byte_semantics": "canonical_lf",
                "path": path,
                "role": role,
                "sha256": _sha256(ROOT / path),
            }
            for role, path in sorted(LOCAL_BINDINGS.items())
        ],
        "network": False,
        "operational_authority": "none",
        "raw_payloads": False,
        "schema_version": "ai-agent-handoff-harness-extension-contract-v1.0",
    }
    return _canonical_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    args = parser.parse_args()
    expected = generated_manifest()
    if args.mode == "generate":
        OUTPUT.write_bytes(expected)
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
        raise SystemExit("harness extension contract manifest is stale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
