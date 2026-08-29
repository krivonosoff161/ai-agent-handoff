"""Source-owned, advisory-only Harness extension for canonical handoff observations."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Literal

from agentic_security_harness.extension_sdk import (
    ExtensionContractRefV1,
    ExtensionFindingV1,
    ExtensionManifestV1,
    ExtensionObservationEnvelopeV1,
)
from agentic_security_harness.portfolio_contract import (
    encode_portfolio_observation_v1 as encode_harness_observation_v1,
)

EXTENSION_ID = "ai-agent-handoff.validation"
EXTENSION_VERSION = "1.0.0"
CANONICAL_CONFIGURATION_BYTES = (
    b'{"dependency_resolution":"operator_preflight_only",'
    b'"handoff_distribution":"ai-agent-handoff",'
    b'"handoff_runtime_bindings":{'
    b'"agent_guard/__init__.py":"fd69e20ed288685e4ef4b6e00e86af42d61d4b2d0075307677646223e05a39a1",'
    b'"agent_guard/guard.py":"80d4707b96319778ef8f8b18bf10cdac97c399c4ddb0157d57825ef0397b0932",'
    b'"agent_guard/handoff_metadata.py":"471bbed70ddb483d04be47cc7de8c8eb7024fc112fac39ab2248ddc94366cc25"},'
    b'"handoff_runtime_byte_semantics":"utf8_canonical_lf",'
    b'"handoff_runtime_version":"0.3.0",'
    b'"handoff_version_specifier":">=0.3,<1",'
    b'"harness_distribution":"agentic-security-harness",'
    b'"harness_version_specifier":">=1.3,<2",'
    b'"network_mode":"off","operational_authority":"none",'
    b'"schema_version":"ai-agent-handoff-harness-extension-config-v1.0"}\n'
)
HANDOFF_RUNTIME_VERSION = "0.3.0"
HANDOFF_RUNTIME_BINDINGS = (
    (
        "agent_guard/__init__.py",
        "fd69e20ed288685e4ef4b6e00e86af42d61d4b2d0075307677646223e05a39a1",
    ),
    (
        "agent_guard/guard.py",
        "80d4707b96319778ef8f8b18bf10cdac97c399c4ddb0157d57825ef0397b0932",
    ),
    (
        "agent_guard/handoff_metadata.py",
        "471bbed70ddb483d04be47cc7de8c8eb7024fc112fac39ab2248ddc94366cc25",
    ),
)
MAX_BOUND_FILE_BYTES = 1_048_576


class HandoffHarnessExtensionError(ValueError):
    """Raised when the installed implementation cannot bind its own exact bytes."""


def canonical_configuration_bytes() -> bytes:
    """Return the public canonical preflight contract; it contains no secret material."""

    return CANONICAL_CONFIGURATION_BYTES


def _implementation_sha256() -> str:
    """Bind the runtime manifest to the exact single-file implementation bytes."""

    payload = _stable_bound_bytes(
        Path(__file__), expected_sha256=None, label="extension implementation"
    )
    return hashlib.sha256(payload).hexdigest()


def _bounded_file_snapshot(
    path: Path, *, label: str
) -> tuple[bytes, tuple[int, int, int, int]]:
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise HandoffHarnessExtensionError(
                f"{label} must be a regular single-link file"
            )
        with open(path, "rb", buffering=0) as stream:  # noqa: PTH123 - descriptor identity
            opened = os.fstat(stream.fileno())
            payload = stream.read(MAX_BOUND_FILE_BYTES + 1)
            after_read = os.fstat(stream.fileno())
        final = os.lstat(path)
    except OSError as exc:
        raise HandoffHarnessExtensionError(f"{label} is unavailable") from exc
    snapshots = (before, opened, after_read, final)
    if any(not stat.S_ISREG(item.st_mode) or item.st_nlink != 1 for item in snapshots):
        raise HandoffHarnessExtensionError(f"{label} is not a stable regular file")
    if os.name == "nt":
        reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if reparse and any(
            int(getattr(item, "st_file_attributes", 0)) & reparse for item in snapshots
        ):
            raise HandoffHarnessExtensionError(f"{label} must not be a reparse point")
    identities = tuple(
        (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns) for item in snapshots
    )
    if len(payload) > MAX_BOUND_FILE_BYTES:
        raise HandoffHarnessExtensionError(f"{label} exceeds the bounded byte limit")
    if len(set(identities)) != 1 or len(payload) != before.st_size:
        raise HandoffHarnessExtensionError(f"{label} changed while it was read")
    return payload, identities[0]


def _stable_bound_bytes(
    path: Path,
    expected_sha256: str | None,
    *,
    label: str,
    canonical_lf: bool = False,
) -> bytes:
    first, first_identity = _bounded_file_snapshot(path, label=label)
    second, second_identity = _bounded_file_snapshot(path, label=label)
    if first_identity != second_identity or first != second:
        raise HandoffHarnessExtensionError(f"{label} changed between bounded reads")
    digest_bytes = first
    if canonical_lf:
        digest_bytes = digest_bytes.replace(b"\r\n", b"\n")
        if b"\r" in digest_bytes:
            raise HandoffHarnessExtensionError(f"{label} contains a non-canonical CR byte")
    if (
        expected_sha256 is not None
        and hashlib.sha256(digest_bytes).hexdigest() != expected_sha256
    ):
        raise HandoffHarnessExtensionError(f"{label} digest drift")
    return first


def _handoff_namespace_loaded() -> bool:
    return any(
        name == "agent_guard" or name.startswith("agent_guard.") for name in sys.modules
    )


def _purge_handoff_namespace() -> None:
    for name in tuple(sys.modules):
        if name == "agent_guard" or name.startswith("agent_guard."):
            sys.modules.pop(name, None)


def _verified_handoff_codec() -> tuple[
    Callable[[bytes], Any], Callable[[Any], bytes], type[Exception]
]:
    """Verify the exact source-owned runtime before and after its first import."""

    if _handoff_namespace_loaded():
        raise HandoffHarnessExtensionError(
            "Handoff runtime namespace was loaded before extension preflight"
        )
    try:
        distribution = importlib.metadata.distribution("ai-agent-handoff")
    except importlib.metadata.PackageNotFoundError as exc:
        raise HandoffHarnessExtensionError(
            "required Handoff runtime distribution is unavailable"
        ) from exc
    if distribution.version != HANDOFF_RUNTIME_VERSION:
        raise HandoffHarnessExtensionError("Handoff runtime version is not exactly bound")

    package_spec = importlib.util.find_spec("agent_guard")
    if (
        package_spec is None
        or package_spec.origin is None
        or package_spec.submodule_search_locations is None
        or len(tuple(package_spec.submodule_search_locations)) != 1
    ):
        raise HandoffHarnessExtensionError("Handoff runtime package origin is ambiguous")
    package_init = Path(package_spec.origin)
    package_root = package_init.parent
    try:
        package_root_stat = package_root.lstat()
    except OSError as exc:
        raise HandoffHarnessExtensionError(
            "Handoff runtime package directory is unavailable"
        ) from exc
    if package_root.is_symlink() or not stat.S_ISDIR(package_root_stat.st_mode):
        raise HandoffHarnessExtensionError(
            "Handoff runtime package directory is not canonical"
        )
    if os.name == "nt":
        reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if reparse and int(getattr(package_root_stat, "st_file_attributes", 0)) & reparse:
            raise HandoffHarnessExtensionError(
                "Handoff runtime package directory must not be a reparse point"
            )
    expected_paths = {
        relative: package_root / Path(relative).name
        for relative, _digest in HANDOFF_RUNTIME_BINDINGS
    }
    if expected_paths["agent_guard/__init__.py"] != package_init:
        raise HandoffHarnessExtensionError("Handoff runtime package origin is not canonical")

    for relative, digest in HANDOFF_RUNTIME_BINDINGS:
        _stable_bound_bytes(
            expected_paths[relative],
            digest,
            label="Handoff runtime binding",
            canonical_lf=True,
        )

    try:
        module = importlib.import_module("agent_guard.handoff_metadata")
        package = sys.modules.get("agent_guard")
        guard = sys.modules.get("agent_guard.guard")
        if not isinstance(package, ModuleType) or not isinstance(guard, ModuleType):
            raise HandoffHarnessExtensionError("Handoff runtime import closure is incomplete")
        actual_origins = {
            "agent_guard/__init__.py": getattr(package, "__file__", None),
            "agent_guard/guard.py": getattr(guard, "__file__", None),
            "agent_guard/handoff_metadata.py": getattr(module, "__file__", None),
        }
        for relative, digest in HANDOFF_RUNTIME_BINDINGS:
            actual = actual_origins[relative]
            if actual is None or Path(actual).resolve(strict=True) != expected_paths[
                relative
            ].resolve(strict=True):
                raise HandoffHarnessExtensionError(
                    "Handoff runtime import origin differs from verified bytes"
                )
            _stable_bound_bytes(
                expected_paths[relative],
                digest,
                label="Handoff runtime binding",
                canonical_lf=True,
            )
        decoder = getattr(module, "decode_portfolio_observation_v1", None)
        encoder = getattr(module, "encode_portfolio_observation_v1", None)
        error_type = getattr(module, "HandoffMetadataError", None)
        if (
            not callable(decoder)
            or not callable(encoder)
            or not isinstance(error_type, type)
            or not issubclass(error_type, Exception)
            or getattr(decoder, "__module__", None) != module.__name__
            or getattr(encoder, "__module__", None) != module.__name__
        ):
            raise HandoffHarnessExtensionError("Handoff runtime codec surface is invalid")
        return decoder, encoder, error_type
    except Exception:
        _purge_handoff_namespace()
        raise


def _manifest() -> ExtensionManifestV1:
    return ExtensionManifestV1(
        schema_version="harness-extension-manifest-v1.0",
        extension_id=EXTENSION_ID,
        extension_version=EXTENSION_VERSION,
        component_id="ai-agent-handoff",
        implementation_sha256=_implementation_sha256(),
        configuration_sha256=hashlib.sha256(CANONICAL_CONFIGURATION_BYTES).hexdigest(),
        harness_api="1",
        kind="check_extension",
        capabilities=("observation.read", "finding.emit"),
        consumes=(
            ExtensionContractRefV1(
                contract_id="portfolio-observation", version="1.0", required=True
            ),
        ),
        produces=(
            ExtensionContractRefV1(
                contract_id="extension-finding", version="1.0", required=True
            ),
        ),
        deterministic=True,
        evidence_provenance="deterministic_rule",
        network_mode="off",
        raw_data_policy="digests_only",
        execution_model="in_process_operator_approved_not_sandboxed",
        operational_authority="none",
    )


class HandoffValidationExtensionV1:
    """Revalidate content-free handoff observations with exact attribution."""

    def __init__(
        self,
        decoder: Callable[[bytes], Any],
        encoder: Callable[[Any], bytes],
        error_type: type[Exception],
    ) -> None:
        self.manifest = _manifest()
        self._decoder = decoder
        self._encoder = encoder
        self._error_type = error_type

    def evaluate(
        self, envelope: ExtensionObservationEnvelopeV1
    ) -> tuple[ExtensionFindingV1, ...]:
        try:
            if type(envelope) is not ExtensionObservationEnvelopeV1:
                raise TypeError("envelope is not exact ExtensionObservationEnvelopeV1")
            checked = ExtensionObservationEnvelopeV1.model_validate(
                envelope.model_dump(mode="python")
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise HandoffHarnessExtensionError(
                "extension observation envelope violates canonical V1"
            ) from exc
        matched = tuple(
            event
            for event in checked.events
            if event.activity in {"handoff.task", "handoff.session"}
        )
        if not matched:
            return (
                ExtensionFindingV1(
                    check_id="ai-agent-handoff.validation",
                    outcome="inconclusive",
                    severity="none",
                    reason_code="handoff.no_matching_observation",
                    evidence_event_ids=(),
                ),
            )

        grouped: dict[str, list[str]] = {
            "handoff.observation_contract_drift": [],
            "handoff.artifact_binding_missing": [],
            "handoff.telemetry_incomplete": [],
            "handoff.observation_valid": [],
        }
        for event in matched:
            try:
                canonical = encode_harness_observation_v1(event)
                handoff_observation = self._decoder(canonical)
                if self._encoder(handoff_observation) != canonical:
                    raise HandoffHarnessExtensionError("canonical observation codec drift")
            except (self._error_type, HandoffHarnessExtensionError, ValueError):
                grouped["handoff.observation_contract_drift"].append(event.event_id)
                continue
            if (
                len(handoff_observation.entity_refs) != 1
                or handoff_observation.entity_refs[0].kind != "artifact"
            ):
                grouped["handoff.artifact_binding_missing"].append(event.event_id)
            elif handoff_observation.telemetry_state != "complete":
                grouped["handoff.telemetry_incomplete"].append(event.event_id)
            else:
                grouped["handoff.observation_valid"].append(event.event_id)

        states: dict[
            str,
            tuple[
                str,
                Literal["pass", "finding", "inconclusive", "error"],
                Literal["none", "low", "medium", "high", "critical"],
            ],
        ] = {
            "handoff.observation_contract_drift": ("contract", "finding", "high"),
            "handoff.artifact_binding_missing": ("artifact", "finding", "high"),
            "handoff.telemetry_incomplete": ("telemetry", "inconclusive", "medium"),
            "handoff.observation_valid": ("valid", "pass", "none"),
        }
        return tuple(
            ExtensionFindingV1(
                check_id=f"ai-agent-handoff.validation.{suffix}",
                outcome=outcome,
                severity=severity,
                reason_code=reason_code,
                evidence_event_ids=tuple(grouped[reason_code]),
            )
            for reason_code, (suffix, outcome, severity) in states.items()
            if grouped[reason_code]
        )


def build_extension() -> HandoffValidationExtensionV1:
    """Construct the exact source-owned V1 object after explicit operator loading."""

    return HandoffValidationExtensionV1(*_verified_handoff_codec())
