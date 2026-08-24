"""Minimal deterministic PEP 517 backend for the closed six-file extension wheel."""

from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path
from typing import Any

NAME = "ai-agent-handoff-harness-extension"
NORMALIZED_NAME = "ai_agent_handoff_harness_extension"
VERSION = "1.0.0"
MODULE = "ai_agent_handoff_harness_extension"
EXTENSION_ID = "ai-agent-handoff.validation"
ENTRY_POINT_GROUP = "agentic_security_harness.extensions.v1"
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "src" / f"{MODULE}.py"
CONFIGURATION = ROOT / "ash-extension-config.json"
DIST_INFO = f"{NORMALIZED_NAME}-{VERSION}.dist-info"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8") + b"\n"


def _configuration_bytes() -> bytes:
    payload = CONFIGURATION.read_bytes()
    decoded = json.loads(payload.decode("utf-8"))
    expected = {
        "dependency_resolution": "operator_preflight_only",
        "handoff_distribution": "ai-agent-handoff",
        "handoff_runtime_bindings": {
            "agent_guard/__init__.py": (
                "b8830cf85e6f2b34e15e5b8dd6243a4ac5b677cc54a11ceac39aaec64dc03962"
            ),
            "agent_guard/guard.py": (
                "d9dd728c876879e6f32862695b519f948c92bfcb9d790bf9c30edbac67db372c"
            ),
            "agent_guard/handoff_metadata.py": (
                "471bbed70ddb483d04be47cc7de8c8eb7024fc112fac39ab2248ddc94366cc25"
            ),
        },
        "handoff_runtime_version": "0.2.0",
        "handoff_version_specifier": ">=0.2,<1",
        "harness_distribution": "agentic-security-harness",
        "harness_version_specifier": ">=1.3,<2",
        "network_mode": "off",
        "operational_authority": "none",
        "schema_version": "ai-agent-handoff-harness-extension-config-v1.0",
    }
    if decoded != expected or payload != _canonical_bytes(expected):
        raise ValueError("extension configuration is not canonical V1")
    return payload


def _manifest(source: bytes, configuration: bytes) -> bytes:
    return _canonical_bytes(
        {
            "capabilities": ["observation.read", "finding.emit"],
            "component_id": "ai-agent-handoff",
            "configuration_sha256": hashlib.sha256(configuration).hexdigest(),
            "consumes": [
                {"contract_id": "portfolio-observation", "required": True, "version": "1.0"}
            ],
            "deterministic": True,
            "evidence_provenance": "deterministic_rule",
            "execution_model": "in_process_operator_approved_not_sandboxed",
            "extension_id": EXTENSION_ID,
            "extension_version": VERSION,
            "harness_api": "1",
            "implementation_sha256": hashlib.sha256(source).hexdigest(),
            "kind": "check_extension",
            "network_mode": "off",
            "operational_authority": "none",
            "produces": [
                {"contract_id": "extension-finding", "required": True, "version": "1.0"}
            ],
            "raw_data_policy": "digests_only",
            "schema_version": "harness-extension-manifest-v1.0",
        }
    )


def _metadata() -> bytes:
    return (
        "Metadata-Version: 2.4\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: Optional advisory-only AI Agent Handoff extension for Agentic Security Harness.\n"
        "Requires-Python: >=3.11,<3.14\n\n"
    ).encode("utf-8")


def _wheel_metadata() -> bytes:
    return (
        b"Wheel-Version: 1.0\n"
        b"Generator: ai-agent-handoff-harness-extension-backend\n"
        b"Root-Is-Purelib: true\n"
        b"Tag: py3-none-any\n"
    )


def _entry_points() -> bytes:
    return (
        f"[{ENTRY_POINT_GROUP}]\n{EXTENSION_ID} = {MODULE}:build_extension\n"
    ).encode("utf-8")


def _record_digest(payload: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode("ascii")
    return f"sha256={encoded.rstrip('=')}"


def _wheel_files() -> dict[str, bytes]:
    source = SOURCE.read_bytes()
    configuration = _configuration_bytes()
    return {
        f"{MODULE}.py": source,
        f"{DIST_INFO}/METADATA": _metadata(),
        f"{DIST_INFO}/WHEEL": _wheel_metadata(),
        f"{DIST_INFO}/ash-extension-manifest.json": _manifest(source, configuration),
        f"{DIST_INFO}/entry_points.txt": _entry_points(),
    }


def _record(files: dict[str, bytes]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for path in sorted(files):
        payload = files[path]
        writer.writerow((path, _record_digest(payload), len(payload)))
    writer.writerow((f"{DIST_INFO}/RECORD", "", ""))
    return output.getvalue().encode("utf-8")


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def get_requires_for_build_wheel(config_settings: dict[str, Any] | None = None) -> list[str]:
    return []


def get_requires_for_build_sdist(config_settings: dict[str, Any] | None = None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: dict[str, Any] | None = None
) -> str:
    root = Path(metadata_directory) / DIST_INFO
    root.mkdir(parents=True, exist_ok=False)
    source = SOURCE.read_bytes()
    configuration = _configuration_bytes()
    (root / "METADATA").write_bytes(_metadata())
    (root / "WHEEL").write_bytes(_wheel_metadata())
    (root / "entry_points.txt").write_bytes(_entry_points())
    (root / "ash-extension-manifest.json").write_bytes(_manifest(source, configuration))
    return DIST_INFO


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    files = _wheel_files()
    files[f"{DIST_INFO}/RECORD"] = _record(files)
    filename = f"{NORMALIZED_NAME}-{VERSION}-py3-none-any.whl"
    destination = Path(wheel_directory) / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(files):
            archive.writestr(_zip_info(path), files[path])
    return filename


def build_sdist(
    sdist_directory: str, config_settings: dict[str, Any] | None = None
) -> str:
    source_paths = (
        Path("README.md"),
        Path("ash-extension-config.json"),
        Path("handoff_extension_backend.py"),
        Path("pyproject.toml"),
        Path("src") / f"{MODULE}.py",
    )
    root_name = f"{NORMALIZED_NAME}-{VERSION}"
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w") as archive:
        for relative in source_paths:
            payload = (ROOT / relative).read_bytes()
            info = tarfile.TarInfo(f"{root_name}/{relative.as_posix()}")
            info.size = len(payload)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    filename = f"{root_name}.tar.gz"
    destination = Path(sdist_directory) / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            compressed.write(raw_tar.getvalue())
    return filename
