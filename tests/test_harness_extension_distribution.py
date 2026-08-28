from __future__ import annotations

import builtins
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
import subprocess
import sys
import types
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.9/3.10 CI rows
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "extensions" / "harness-v1"
MODULE_NAME = "ai_agent_handoff_harness_extension"
DIST_NAME = "ai-agent-handoff-harness-extension"
EXTENSION_ID = "ai-agent-handoff.validation"
HARNESS_ENV = "ASH_HANDOFF_EXTENSION_HARNESS_ROOT"


def _harness_root() -> Path:
    raw = os.environ.get(HARNESS_ENV)
    if raw is None:
        pytest.skip(f"{HARNESS_ENV} is required for exact cross-repository tests")
    root = Path(raw)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        pytest.fail(f"configured {HARNESS_ENV} is not a safe absolute directory")
    manifest = json.loads(
        (ROOT / "contracts" / "harness-extension-v1.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for binding in manifest["harness_reference"]["bindings"]:
        path = root / binding["path"]
        if not path.is_file() or path.is_symlink():
            pytest.fail("exact Harness reference file is missing or unsafe")
        if hashlib.sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
            pytest.fail("exact Harness reference digest drift")
    return root


def _build_wheel(tmp_path: Path) -> Path:
    output = tmp_path / "dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(output),
            str(EXTENSION_ROOT),
        ],
        check=True,
        cwd=ROOT,
        timeout=120,
    )
    wheels = tuple(output.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def _build_handoff_wheel(tmp_path: Path) -> Path:
    output = tmp_path / "handoff-dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(output),
            str(ROOT),
        ],
        check=True,
        cwd=ROOT,
        timeout=120,
    )
    wheels = tuple(output.glob("ai_agent_handoff-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def _safe_unpack(wheel: Path, destination: Path) -> None:
    destination.mkdir()
    with zipfile.ZipFile(wheel) as archive:
        members = archive.infolist()
        assert len(members) == 6
        for member in members:
            path = PurePosixPath(member.filename)
            assert not path.is_absolute()
            assert ".." not in path.parts
            assert not member.is_dir()
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))


def _pip_install_wheel(wheel: Path, destination: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--target",
            str(destination),
            str(wheel),
        ],
        check=True,
        cwd=ROOT,
        timeout=120,
    )
    assert not tuple(destination.rglob("__pycache__"))
    assert not tuple(destination.rglob("*.pyc"))


def _take_handoff_modules() -> dict[str, object]:
    saved = {
        name: module
        for name, module in tuple(sys.modules.items())
        if name == "agent_guard" or name.startswith("agent_guard.")
    }
    for name in saved:
        sys.modules.pop(name, None)
    return saved


def _restore_handoff_modules(saved: dict[str, object]) -> None:
    for name in tuple(sys.modules):
        if name == "agent_guard" or name.startswith("agent_guard."):
            sys.modules.pop(name, None)
    sys.modules.update(saved)


def _installed_distribution(root: Path) -> metadata.Distribution:
    matches = tuple(
        item
        for item in metadata.distributions(path=[str(root)])
        if item.metadata["Name"] == DIST_NAME
    )
    assert len(matches) == 1
    return matches[0]


def test_nested_project_declares_closed_noninstalling_dependency_boundary() -> None:
    project = tomllib.loads((EXTENSION_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["requires-python"] == ">=3.11,<3.14"
    assert project["project"]["dependencies"] == []
    assert project["project"]["entry-points"] == {
        "agentic_security_harness.extensions.v1": {
            EXTENSION_ID: f"{MODULE_NAME}:build_extension"
        }
    }
    boundary = project["tool"]["ai-agent-handoff"]["harness-extension"]
    assert boundary == {
        "required-harness": "agentic-security-harness>=1.3,<2",
        "required-handoff": "ai-agent-handoff>=0.3,<1",
        "dependency-resolution": "operator-preflight-only",
    }
    configuration = (EXTENSION_ROOT / "ash-extension-config.json").read_bytes()
    assert configuration.endswith(b"\n")
    assert json.dumps(
        json.loads(configuration), separators=(",", ":"), sort_keys=True
    ).encode() + b"\n" == configuration
    decoded = json.loads(configuration)
    assert decoded["handoff_runtime_version"] == "0.3.0"
    assert decoded["handoff_version_specifier"] == ">=0.3,<1"
    assert decoded["handoff_runtime_byte_semantics"] == "utf8_canonical_lf"
    assert decoded["handoff_runtime_bindings"] == {
        "agent_guard/__init__.py": (
            "fd69e20ed288685e4ef4b6e00e86af42d61d4b2d0075307677646223e05a39a1"
        ),
        "agent_guard/guard.py": (
            "80d4707b96319778ef8f8b18bf10cdac97c399c4ddb0157d57825ef0397b0932"
        ),
        "agent_guard/handoff_metadata.py": (
            "471bbed70ddb483d04be47cc7de8c8eb7024fc112fac39ab2248ddc94366cc25"
        ),
    }
    attributes = set((ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines())
    assert {
        "extensions/harness-v1/** text eol=lf",
        "contracts/harness-extension-v1.manifest.json text eol=lf",
        "docs/harness-extension.md text eol=lf",
        "tools/harness_extension_contracts.py text eol=lf",
        "tests/test_harness_extension_distribution.py text eol=lf",
        ".github/workflows/tests.yml text eol=lf",
        "component.yaml text eol=lf",
        "MANIFEST.in text eol=lf",
        "tools/package_smoke.py text eol=lf",
        "tests/conftest.py text eol=lf",
    } <= attributes


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Harness extension requires Python 3.11")
def test_exact_installed_wheel_inspection_approval_lifecycle_and_receipt(
    tmp_path: Path,
) -> None:
    harness_root = _harness_root()
    sys.path.insert(0, str(harness_root / "src"))
    try:
        from agentic_security_harness.extension_distribution import (
            approve_extension_distribution_v1,
            inspect_extension_distribution_v1,
        )
        from agentic_security_harness.extension_lifecycle import (
            bind_active_operator_extension_v1,
        )
        from agentic_security_harness.extension_sdk import (
            ExtensionContractError,
            build_extension_envelope_v1,
            encode_extension_manifest_v1,
            run_extension_v1,
        )
        from agentic_security_harness.portfolio_contract import (
            CanonicalObservationEventV1,
            SafeEvidencePointer,
        )

        wheel = _build_wheel(tmp_path)
        installed = tmp_path / "installed"
        _pip_install_wheel(wheel, installed)
        handoff_runtime = tmp_path / "handoff-runtime"
        _pip_install_wheel(_build_handoff_wheel(tmp_path), handoff_runtime)
        distribution = _installed_distribution(installed)
        entry_points = tuple(distribution.entry_points)
        assert len(entry_points) == 1
        entry_point = entry_points[0]
        assert entry_point.group == "agentic_security_harness.extensions.v1"
        assert entry_point.name == EXTENSION_ID
        assert entry_point.value == f"{MODULE_NAME}:build_extension"
        assert distribution.requires is None
        assert distribution.metadata["Requires-Python"] == ">=3.11,<3.14"

        configuration = (EXTENSION_ROOT / "ash-extension-config.json").read_bytes()
        assert MODULE_NAME not in sys.modules
        inspection = inspect_extension_distribution_v1(
            distribution_name=DIST_NAME,
            extension_id=EXTENSION_ID,
            search_paths=(installed,),
            configuration_bytes=configuration,
        )
        assert inspection.code_loaded is False
        approval = approve_extension_distribution_v1(
            approved_inspection=inspection,
            approved_inspection_id=inspection.inspection_id,
            search_paths=(installed,),
            configuration_bytes=configuration,
        )
        assert approval.code_loaded is False
        assert approval.operational_authority == "none"

        saved_handoff_modules = _take_handoff_modules()
        sys.path.insert(0, str(installed))
        sys.path.insert(0, str(handoff_runtime))
        try:
            factory = entry_point.load()
            assert "agent_guard" not in sys.modules
            extension = factory()
            assert "agent_guard.handoff_metadata" in sys.modules
            extension_module = sys.modules[MODULE_NAME]
            assert extension_module.canonical_configuration_bytes() == configuration
            manifest_path = next(installed.glob("*.dist-info")) / "ash-extension-manifest.json"
            assert encode_extension_manifest_v1(extension.manifest) == manifest_path.read_bytes()
            bound = bind_active_operator_extension_v1(approval, extension)

            event = CanonicalObservationEventV1.model_validate(
                {
                    "schema_version": "portfolio-observation-v1.0",
                    "event_id": "a" * 64,
                    "project_id": "ai-agent-handoff",
                    "repository_id": "example/synthetic-handoff",
                    "repository_sha": "b" * 40,
                    "occurred_at": datetime(2026, 8, 24, tzinfo=timezone.utc),
                    "producer_id_hash": "c" * 64,
                    "producer_attestation": "unattested",
                    "source_surface": "agent",
                    "activity": "handoff.task",
                    "entity_refs": (
                        SafeEvidencePointer(
                            kind="artifact", digest="d" * 64, locator_id="e" * 64
                        ),
                    ),
                    "parent_event_ids": (),
                    "data_envelope_ref": "f" * 64,
                    "authority_envelope_ref": None,
                    "telemetry_state": "complete",
                    "operational_authority": "none",
                }
            )
            envelope = build_extension_envelope_v1(
                source_component_id="ai-agent-handoff",
                source_commitment_sha256="1" * 64,
                events=(event,),
            )
            receipt = run_extension_v1(bound, envelope)
            finding = receipt.result.findings[0]
            assert finding.outcome == "pass"
            assert finding.reason_code == "handoff.observation_valid"
            assert receipt.operational_authority == "none"
            encoded = json.dumps(receipt.model_dump(mode="json"), sort_keys=True)
            assert "synthetic-handoff-body" not in encoded
            assert str(installed) not in encoded
            with pytest.raises(ExtensionContractError, match="already appears"):
                run_extension_v1(bound, receipt.output_envelope)

            drifted_event = event.model_copy(update={"authority_envelope_ref": "9" * 64})
            drifted_envelope = build_extension_envelope_v1(
                source_component_id="ai-agent-handoff",
                source_commitment_sha256="2" * 64,
                events=(drifted_event,),
            )
            drifted = run_extension_v1(bound, drifted_envelope)
            assert drifted.result.findings[0].outcome == "finding"
            assert (
                drifted.result.findings[0].reason_code
                == "handoff.observation_contract_drift"
            )

            missing_artifact = event.model_copy(update={"entity_refs": ()})
            missing_envelope = build_extension_envelope_v1(
                source_component_id="ai-agent-handoff",
                source_commitment_sha256="3" * 64,
                events=(missing_artifact,),
            )
            missing = run_extension_v1(bound, missing_envelope)
            assert missing.result.findings[0].outcome == "finding"
            assert missing.result.findings[0].reason_code == "handoff.artifact_binding_missing"

            incomplete_event = event.model_copy(update={"telemetry_state": "incomplete"})
            incomplete_envelope = build_extension_envelope_v1(
                source_component_id="ai-agent-handoff",
                source_commitment_sha256="4" * 64,
                events=(incomplete_event,),
            )
            incomplete = run_extension_v1(bound, incomplete_envelope)
            assert incomplete.result.findings[0].outcome == "inconclusive"
            assert incomplete.result.findings[0].reason_code == "handoff.telemetry_incomplete"

            unrelated_event = event.model_copy(update={"activity": "agent.observed"})
            unrelated_envelope = build_extension_envelope_v1(
                source_component_id="ai-agent-handoff",
                source_commitment_sha256="5" * 64,
                events=(unrelated_event,),
            )
            unrelated = run_extension_v1(bound, unrelated_envelope)
            assert unrelated.result.findings[0].outcome == "inconclusive"
            assert unrelated.result.findings[0].evidence_event_ids == ()

            mixed_events = (
                event.model_copy(update={"event_id": "1" * 64}),
                missing_artifact.model_copy(update={"event_id": "2" * 64}),
                incomplete_event.model_copy(update={"event_id": "3" * 64}),
                drifted_event.model_copy(update={"event_id": "4" * 64}),
            )
            mixed_envelope = build_extension_envelope_v1(
                source_component_id="ai-agent-handoff",
                source_commitment_sha256="6" * 64,
                events=mixed_events,
            )
            mixed = run_extension_v1(bound, mixed_envelope)
            attribution = {
                finding.reason_code: finding.evidence_event_ids
                for finding in mixed.result.findings
            }
            assert attribution == {
                "handoff.observation_contract_drift": ("4" * 64,),
                "handoff.artifact_binding_missing": ("2" * 64,),
                "handoff.telemetry_incomplete": ("3" * 64,),
                "handoff.observation_valid": ("1" * 64,),
            }
        finally:
            sys.path.remove(str(handoff_runtime))
            sys.path.remove(str(installed))
            sys.modules.pop(MODULE_NAME, None)
            _restore_handoff_modules(saved_handoff_modules)
    finally:
        sys.path.remove(str(harness_root / "src"))


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Harness extension requires Python 3.11")
def test_exact_approval_reinspection_rejects_installed_source_drift(tmp_path: Path) -> None:
    harness_root = _harness_root()
    sys.path.insert(0, str(harness_root / "src"))
    try:
        from agentic_security_harness.extension_distribution import (
            ExtensionDistributionError,
            approve_extension_distribution_v1,
            inspect_extension_distribution_v1,
        )

        installed = tmp_path / "installed"
        _safe_unpack(_build_wheel(tmp_path), installed)
        configuration = (EXTENSION_ROOT / "ash-extension-config.json").read_bytes()
        inspection = inspect_extension_distribution_v1(
            distribution_name=DIST_NAME,
            extension_id=EXTENSION_ID,
            search_paths=(installed,),
            configuration_bytes=configuration,
        )
        module = installed / f"{MODULE_NAME}.py"
        module.write_bytes(module.read_bytes() + b"# post-inspection drift\n")
        with pytest.raises(ExtensionDistributionError):
            approve_extension_distribution_v1(
                approved_inspection=inspection,
                approved_inspection_id=inspection.inspection_id,
                search_paths=(installed,),
                configuration_bytes=configuration,
            )
        assert MODULE_NAME not in sys.modules
    finally:
        sys.path.remove(str(harness_root / "src"))


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Harness extension requires Python 3.11")
def test_factory_rejects_preloaded_handoff_runtime_namespace(tmp_path: Path) -> None:
    harness_root = _harness_root()
    sys.path.insert(0, str(harness_root / "src"))
    saved_handoff_modules = _take_handoff_modules()
    installed = tmp_path / "installed"
    try:
        _pip_install_wheel(_build_wheel(tmp_path), installed)
        sys.path.insert(0, str(installed))
        try:
            entry_point = tuple(_installed_distribution(installed).entry_points)[0]
            factory = entry_point.load()
            sys.modules["agent_guard.handoff_metadata"] = types.ModuleType(
                "agent_guard.handoff_metadata"
            )
            extension_module = sys.modules[MODULE_NAME]
            with pytest.raises(
                extension_module.HandoffHarnessExtensionError,
                match="loaded before extension preflight",
            ):
                factory()
            assert "agent_guard" not in sys.modules
        finally:
            sys.path.remove(str(installed))
            sys.modules.pop(MODULE_NAME, None)
    finally:
        _restore_handoff_modules(saved_handoff_modules)
        sys.path.remove(str(harness_root / "src"))


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Harness extension requires Python 3.11")
def test_factory_rejects_handoff_runtime_digest_drift_before_import(tmp_path: Path) -> None:
    harness_root = _harness_root()
    installed = tmp_path / "installed"
    handoff_runtime = tmp_path / "handoff-runtime"
    saved_handoff_modules = _take_handoff_modules()
    sys.path.insert(0, str(harness_root / "src"))
    try:
        _pip_install_wheel(_build_wheel(tmp_path), installed)
        _pip_install_wheel(_build_handoff_wheel(tmp_path), handoff_runtime)
        metadata_source = handoff_runtime / "agent_guard" / "handoff_metadata.py"
        metadata_source.write_bytes(metadata_source.read_bytes() + b"# hostile drift\n")
        sys.path.insert(0, str(installed))
        sys.path.insert(0, str(handoff_runtime))
        try:
            factory = tuple(_installed_distribution(installed).entry_points)[0].load()
            extension_module = sys.modules[MODULE_NAME]
            with pytest.raises(
                extension_module.HandoffHarnessExtensionError,
                match="binding digest drift",
            ):
                factory()
            assert "agent_guard" not in sys.modules
            assert "agent_guard.handoff_metadata" not in sys.modules
        finally:
            sys.path.remove(str(handoff_runtime))
            sys.path.remove(str(installed))
            sys.modules.pop(MODULE_NAME, None)
    finally:
        _restore_handoff_modules(saved_handoff_modules)
        sys.path.remove(str(harness_root / "src"))


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Harness extension requires Python 3.11")
def test_bound_readers_reject_oversize_growth_and_equal_size_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness_root = _harness_root()
    sys.path.insert(0, str(harness_root / "src"))
    sys.path.insert(0, str(EXTENSION_ROOT / "src"))
    try:
        extension_module = importlib.import_module(MODULE_NAME)

        oversized = tmp_path / "oversized.py"
        oversized.write_bytes(b"x" * (extension_module.MAX_BOUND_FILE_BYTES + 1))
        original_file = extension_module.__file__
        try:
            extension_module.__file__ = str(oversized)
            with pytest.raises(
                extension_module.HandoffHarnessExtensionError,
                match="exceeds the bounded byte limit",
            ):
                extension_module._implementation_sha256()
        finally:
            extension_module.__file__ = original_file

        growing = tmp_path / "growing.py"
        growing.write_bytes(b"a" * 64)
        real_open = builtins.open

        class GrowingStream:
            def __init__(self, path: Path) -> None:
                self._stream = real_open(path, "r+b", buffering=0)

            def __enter__(self) -> GrowingStream:
                return self

            def __exit__(self, *_args: object) -> None:
                self._stream.close()

            def fileno(self) -> int:
                return self._stream.fileno()

            def read(self, size: int) -> bytes:
                position = self._stream.tell()
                self._stream.seek(0, 2)
                self._stream.write(b"z")
                self._stream.seek(position)
                return self._stream.read(size)

        def growing_open(
            path: Path, mode: str, *, buffering: int = -1
        ) -> GrowingStream | object:
            if Path(path) == growing and mode == "rb" and buffering == 0:
                return GrowingStream(Path(path))
            return real_open(path, mode, buffering=buffering)

        with monkeypatch.context() as context:
            context.setattr(extension_module, "open", growing_open, raising=False)
            with pytest.raises(
                extension_module.HandoffHarnessExtensionError,
                match="changed while it was read",
            ):
                extension_module._bounded_file_snapshot(growing, label="synthetic binding")

        equal_size = tmp_path / "equal-size.py"
        equal_size.write_bytes(b"a" * 64)
        real_snapshot = extension_module._bounded_file_snapshot
        call_count = 0

        def replacing_snapshot(path: Path, *, label: str) -> tuple[bytes, object]:
            nonlocal call_count
            snapshot = real_snapshot(path, label=label)
            call_count += 1
            if call_count == 1:
                path.write_bytes(b"b" * 64)
            return snapshot

        with monkeypatch.context() as context:
            context.setattr(extension_module, "_bounded_file_snapshot", replacing_snapshot)
            with pytest.raises(
                extension_module.HandoffHarnessExtensionError,
                match="changed between bounded reads",
            ):
                extension_module._stable_bound_bytes(
                    equal_size, expected_sha256=None, label="synthetic binding"
                )

        lf = tmp_path / "lf.py"
        crlf = tmp_path / "crlf.py"
        bare_cr = tmp_path / "bare-cr.py"
        lf.write_bytes(b"alpha\nbeta\n")
        crlf.write_bytes(b"alpha\r\nbeta\r\n")
        bare_cr.write_bytes(b"alpha\rbeta\n")
        canonical_digest = hashlib.sha256(lf.read_bytes()).hexdigest()
        assert extension_module._stable_bound_bytes(
            lf,
            canonical_digest,
            label="synthetic binding",
            canonical_lf=True,
        ) == lf.read_bytes()
        assert extension_module._stable_bound_bytes(
            crlf,
            canonical_digest,
            label="synthetic binding",
            canonical_lf=True,
        ) == crlf.read_bytes()
        with pytest.raises(
            extension_module.HandoffHarnessExtensionError,
            match="non-canonical CR byte",
        ):
            extension_module._stable_bound_bytes(
                bare_cr,
                canonical_digest,
                label="synthetic binding",
                canonical_lf=True,
            )
    finally:
        sys.path.remove(str(EXTENSION_ROOT / "src"))
        sys.path.remove(str(harness_root / "src"))
        sys.modules.pop(MODULE_NAME, None)


def test_extension_source_has_no_raw_input_path_network_or_dynamic_execution() -> None:
    source = (
        EXTENSION_ROOT / "src" / "ai_agent_handoff_harness_extension.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "import socket",
        "import subprocess",
        "import requests",
        "import httpx",
        "urlopen(",
        "entry_points(",
        "eval(",
        "exec(",
        "artifact_bytes",
        "raw_payload",
    )
    assert all(token not in source for token in forbidden)
