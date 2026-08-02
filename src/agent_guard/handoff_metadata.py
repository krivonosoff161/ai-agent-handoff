# -*- coding: utf-8 -*-
"""Strict, authority-free handoff metadata projection.

This module accepts bytes supplied by the caller.  It does not open handoff files,
interpret Markdown, authenticate identities, or grant permission.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

HANDOFF_METADATA_V1 = "handoff-metadata-v1.0"
PORTFOLIO_OBSERVATION_V1 = "portfolio-observation-v1.0"
PORTFOLIO_ADAPTER_AUDIT_V1 = "portfolio-adapter-audit-v1.0"
PORTFOLIO_COMMITMENT_DOMAIN = "agentic-security-portfolio/observation/v1.0"
MAX_HANDOFF_METADATA_BYTES = 4_096
MAX_PORTFOLIO_OBSERVATION_BYTES = 4_096
MAX_ADAPTER_FIELDS = 128
MAX_ADAPTER_MAPPINGS = 128
MAX_ADAPTER_REASON_CODES = 64

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_OBJECT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_REPOSITORY_ID = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TOKEN = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_MAX_SUPPORTED_TIME = datetime(2100, 1, 1, tzinfo=timezone.utc)

_SOURCE_FIELDS = (
    "schema_version",
    "artifact_kind",
    "artifact_sha256",
    "sequence",
    "created_at",
    "producer_id_hash",
    "parent_artifact_sha256",
)
_TARGET_FIELDS = (
    "schema_version",
    "event_id",
    "project_id",
    "repository_id",
    "repository_sha",
    "occurred_at",
    "producer_id_hash",
    "producer_attestation",
    "source_surface",
    "activity",
    "entity_refs",
    "parent_event_ids",
    "data_envelope_ref",
    "authority_envelope_ref",
    "telemetry_state",
    "operational_authority",
)

SourceSurface = Literal["user", "agent"]
TelemetryState = Literal["complete", "incomplete", "malformed", "unattested", "conflicting"]


class HandoffMetadataError(ValueError):
    """Raised when metadata, sequence, context, or projection fails closed."""


@dataclass(frozen=True)
class HandoffMetadataV1:
    schema_version: Literal["handoff-metadata-v1.0"]
    artifact_kind: Literal["task", "session"]
    artifact_sha256: str
    sequence: int
    created_at: datetime
    producer_id_hash: str
    parent_artifact_sha256: Optional[str]

    def __post_init__(self) -> None:
        if self.schema_version != HANDOFF_METADATA_V1:
            raise HandoffMetadataError("unsupported handoff metadata version")
        if self.artifact_kind not in {"task", "session"}:
            raise HandoffMetadataError("artifact_kind is not supported")
        if not _SHA256.fullmatch(self.artifact_sha256):
            raise HandoffMetadataError("artifact_sha256 must be lowercase SHA-256")
        if type(self.sequence) is not int or not 0 <= self.sequence <= 1_000_000_000:
            raise HandoffMetadataError("sequence is outside the supported range")
        _validate_time(self.created_at, field="created_at")
        if not _SHA256.fullmatch(self.producer_id_hash):
            raise HandoffMetadataError("producer_id_hash must be lowercase SHA-256")
        if self.parent_artifact_sha256 is not None and not _SHA256.fullmatch(
            self.parent_artifact_sha256
        ):
            raise HandoffMetadataError("parent_artifact_sha256 must be null or SHA-256")
        if (self.sequence == 0) != (self.parent_artifact_sha256 is None):
            raise HandoffMetadataError(
                "only the initial sequence may omit parent_artifact_sha256"
            )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = _format_time(self.created_at)
        return data


@dataclass(frozen=True)
class HandoffAdapterContext:
    project_id: str
    repository_id: str
    repository_sha: str
    source_surface: SourceSurface
    data_envelope_ref: str
    telemetry_state: TelemetryState = "complete"

    def __post_init__(self) -> None:
        if not _PROJECT_ID.fullmatch(self.project_id):
            raise HandoffMetadataError("project_id is not canonical")
        if not _REPOSITORY_ID.fullmatch(self.repository_id):
            raise HandoffMetadataError("repository_id is not canonical")
        if not _GIT_OBJECT.fullmatch(self.repository_sha):
            raise HandoffMetadataError("repository_sha is not an exact Git object id")
        if self.source_surface not in {"user", "agent"}:
            raise HandoffMetadataError("handoff source_surface must be user or agent")
        if not _SHA256.fullmatch(self.data_envelope_ref):
            raise HandoffMetadataError("data_envelope_ref must be lowercase SHA-256")
        if self.telemetry_state not in {
            "complete", "incomplete", "malformed", "unattested", "conflicting"
        }:
            raise HandoffMetadataError("telemetry_state is not supported")


@dataclass(frozen=True)
class SafeEvidencePointerV1:
    kind: Literal["artifact"]
    digest: str
    locator_id: str

    def __post_init__(self) -> None:
        if self.kind != "artifact":
            raise HandoffMetadataError("handoff pointer must reference an artifact")
        if not _SHA256.fullmatch(self.digest) or not _SHA256.fullmatch(self.locator_id):
            raise HandoffMetadataError("evidence pointer values must be SHA-256")


@dataclass(frozen=True)
class CanonicalObservationV1:
    schema_version: Literal["portfolio-observation-v1.0"]
    event_id: str
    project_id: str
    repository_id: str
    repository_sha: str
    occurred_at: datetime
    producer_id_hash: str
    producer_attestation: Literal["unattested"]
    source_surface: SourceSurface
    activity: str
    entity_refs: Tuple[SafeEvidencePointerV1, ...]
    parent_event_ids: Tuple[str, ...]
    data_envelope_ref: str
    authority_envelope_ref: None
    telemetry_state: TelemetryState
    operational_authority: Literal["none"]

    def __post_init__(self) -> None:
        if self.schema_version != PORTFOLIO_OBSERVATION_V1:
            raise HandoffMetadataError("unsupported observation version")
        if not _SHA256.fullmatch(self.event_id):
            raise HandoffMetadataError("event_id must be lowercase SHA-256")
        if not _PROJECT_ID.fullmatch(self.project_id):
            raise HandoffMetadataError("project_id is not canonical")
        if not _REPOSITORY_ID.fullmatch(self.repository_id):
            raise HandoffMetadataError("repository_id is not canonical")
        if not _GIT_OBJECT.fullmatch(self.repository_sha):
            raise HandoffMetadataError("repository_sha is not an exact Git object id")
        _validate_time(self.occurred_at, field="occurred_at")
        if not _SHA256.fullmatch(self.producer_id_hash):
            raise HandoffMetadataError("producer_id_hash must be lowercase SHA-256")
        if self.producer_attestation != "unattested":
            raise HandoffMetadataError("handoff metadata cannot authenticate its producer")
        if self.source_surface not in {"user", "agent"}:
            raise HandoffMetadataError("source_surface is not supported")
        if not _TOKEN.fullmatch(self.activity):
            raise HandoffMetadataError("activity is not a canonical token")
        if len(self.entity_refs) > 64:
            raise HandoffMetadataError("entity_refs exceeds the V1 cardinality")
        if any(type(value) is not SafeEvidencePointerV1 for value in self.entity_refs):
            raise HandoffMetadataError("entity_refs must contain safe pointers")
        if len(self.parent_event_ids) > 64:
            raise HandoffMetadataError("parent_event_ids exceeds the V1 cardinality")
        if len(self.parent_event_ids) != len(set(self.parent_event_ids)):
            raise HandoffMetadataError("parent_event_ids must be unique")
        if any(not _SHA256.fullmatch(value) for value in self.parent_event_ids):
            raise HandoffMetadataError("parent_event_ids must be SHA-256")
        if self.event_id in self.parent_event_ids:
            raise HandoffMetadataError("event cannot be its own parent")
        if not _SHA256.fullmatch(self.data_envelope_ref):
            raise HandoffMetadataError("data_envelope_ref must be SHA-256")
        if self.authority_envelope_ref is not None:
            raise HandoffMetadataError("handoff projection cannot carry authority")
        if self.telemetry_state not in {
            "complete", "incomplete", "malformed", "unattested", "conflicting"
        }:
            raise HandoffMetadataError("telemetry_state is not supported")
        if self.operational_authority != "none":
            raise HandoffMetadataError("handoff projection has no operational authority")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["occurred_at"] = _format_time(self.occurred_at)
        return data


@dataclass(frozen=True)
class AdapterFieldMappingV1:
    source_fields: Tuple[str, ...]
    target_fields: Tuple[str, ...]
    transformation: Literal["identity", "derived"]
    authority_effect: Literal["none", "downgrade"]

    def __post_init__(self) -> None:
        if not self.source_fields or not self.target_fields:
            raise HandoffMetadataError("mapping fields must not be empty")
        if len(self.source_fields) > MAX_ADAPTER_FIELDS or len(
            self.target_fields
        ) > MAX_ADAPTER_FIELDS:
            raise HandoffMetadataError("mapping field cardinality exceeded")
        if len(self.source_fields) != len(set(self.source_fields)) or len(
            self.target_fields
        ) != len(set(self.target_fields)):
            raise HandoffMetadataError("mapping fields must be unique")
        if any(
            not _TOKEN.fullmatch(value)
            for value in self.source_fields + self.target_fields
        ):
            raise HandoffMetadataError("mapping fields must be canonical tokens")
        if self.transformation not in {"identity", "derived"}:
            raise HandoffMetadataError("mapping transformation is not supported")
        if self.authority_effect not in {"none", "downgrade"}:
            raise HandoffMetadataError("mapping authority effect is not supported")
        if self.transformation == "identity" and (
            len(self.source_fields) != 1 or self.source_fields != self.target_fields
        ):
            raise HandoffMetadataError("identity mapping requires one identical field")


@dataclass(frozen=True)
class AdapterAuditV1:
    schema_version: Literal["portfolio-adapter-audit-v1.0"]
    source_model: Literal["handoff.metadata_sidecar"]
    target_model: Literal["portfolio-observation-v1.0"]
    completeness: Literal["partial"]
    source_fields: Tuple[str, ...]
    target_fields: Tuple[str, ...]
    mappings: Tuple[AdapterFieldMappingV1, ...]
    dropped_source_fields: Tuple[str, ...]
    context_target_fields: Tuple[str, ...]
    constant_target_fields: Tuple[str, ...]
    authority_downgrade: Literal[True]
    reason_codes: Tuple[str, ...]
    operational_authority: Literal["none"]

    def __post_init__(self) -> None:
        if self.schema_version != PORTFOLIO_ADAPTER_AUDIT_V1:
            raise HandoffMetadataError("unsupported audit version")
        if self.source_model != "handoff.metadata_sidecar":
            raise HandoffMetadataError("unsupported source model")
        if self.target_model != PORTFOLIO_OBSERVATION_V1:
            raise HandoffMetadataError("unsupported target model")
        if self.completeness != "partial":
            raise HandoffMetadataError("unattested handoff projection must remain partial")
        groups = (
            self.source_fields,
            self.target_fields,
            self.dropped_source_fields,
            self.context_target_fields,
            self.constant_target_fields,
            self.reason_codes,
        )
        if any(len(group) != len(set(group)) for group in groups):
            raise HandoffMetadataError("audit lists must contain unique values")
        if any(not _TOKEN.fullmatch(value) for group in groups for value in group):
            raise HandoffMetadataError("audit values must be canonical tokens")
        if len(self.source_fields) > MAX_ADAPTER_FIELDS or len(
            self.target_fields
        ) > MAX_ADAPTER_FIELDS:
            raise HandoffMetadataError("audit field cardinality exceeded")
        if len(self.mappings) > MAX_ADAPTER_MAPPINGS:
            raise HandoffMetadataError("audit mapping cardinality exceeded")
        if len(self.reason_codes) > MAX_ADAPTER_REASON_CODES:
            raise HandoffMetadataError("audit reason cardinality exceeded")
        if any(
            len(group) > MAX_ADAPTER_FIELDS
            for group in (
                self.dropped_source_fields,
                self.context_target_fields,
                self.constant_target_fields,
            )
        ):
            raise HandoffMetadataError("audit classification cardinality exceeded")
        if set(self.source_fields) != set(_SOURCE_FIELDS):
            raise HandoffMetadataError("source_fields must equal the V1 field universe")
        if set(self.target_fields) != set(_TARGET_FIELDS):
            raise HandoffMetadataError("target_fields must equal the V1 field universe")
        mapped_sources = [value for item in self.mappings for value in item.source_fields]
        mapped_targets = [value for item in self.mappings for value in item.target_fields]
        source_accounting = mapped_sources + list(self.dropped_source_fields)
        target_accounting = (
            mapped_targets
            + list(self.context_target_fields)
            + list(self.constant_target_fields)
        )
        if len(source_accounting) != len(set(source_accounting)):
            raise HandoffMetadataError("source field classifications overlap")
        if len(target_accounting) != len(set(target_accounting)):
            raise HandoffMetadataError("target field classifications overlap")
        if set(source_accounting) != set(self.source_fields):
            raise HandoffMetadataError("source field accounting is not exhaustive")
        if set(target_accounting) != set(self.target_fields):
            raise HandoffMetadataError("target field accounting is not exhaustive")
        if not self.authority_downgrade or self.operational_authority != "none":
            raise HandoffMetadataError("handoff projection must downgrade authority")
        if "authority_envelope_ref" not in self.constant_target_fields:
            raise HandoffMetadataError("authority_envelope_ref must be constant")
        if "operational_authority" not in self.constant_target_fields:
            raise HandoffMetadataError("operational_authority must be constant")
        if not self.reason_codes:
            raise HandoffMetadataError("partial projection requires reason codes")


@dataclass(frozen=True)
class HandoffProjectionResult:
    observation: CanonicalObservationV1
    audit: AdapterAuditV1


def encode_handoff_metadata(metadata: HandoffMetadataV1) -> bytes:
    """Return canonical, bounded metadata bytes with one LF terminator."""
    encoded = _canonical_bytes(metadata.to_dict()) + b"\n"
    if len(encoded) > MAX_HANDOFF_METADATA_BYTES:
        raise HandoffMetadataError("handoff metadata exceeds the byte limit")
    return encoded


def load_handoff_metadata(payload: bytes) -> HandoffMetadataV1:
    """Decode exact canonical sidecar bytes; ambiguous input fails closed."""
    if not isinstance(payload, bytes):
        raise HandoffMetadataError("handoff metadata payload must be bytes")
    if len(payload) > MAX_HANDOFF_METADATA_BYTES:
        raise HandoffMetadataError("handoff metadata exceeds the byte limit")
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except RecursionError as exc:
        raise HandoffMetadataError("handoff metadata nesting exceeds the limit") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffMetadataError("handoff metadata is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise HandoffMetadataError("handoff metadata must be a JSON object")
    if set(decoded) != set(_SOURCE_FIELDS):
        raise HandoffMetadataError("handoff metadata fields do not match V1")
    for field in ("schema_version", "artifact_kind", "artifact_sha256", "created_at", "producer_id_hash"):
        if type(decoded[field]) is not str:
            raise HandoffMetadataError("%s has the wrong JSON type" % field)
    if type(decoded["sequence"]) is not int:
        raise HandoffMetadataError("sequence has the wrong JSON type")
    parent = decoded["parent_artifact_sha256"]
    if parent is not None and type(parent) is not str:
        raise HandoffMetadataError("parent_artifact_sha256 has the wrong JSON type")
    metadata = HandoffMetadataV1(
        schema_version=cast(Any, decoded["schema_version"]),
        artifact_kind=cast(Any, decoded["artifact_kind"]),
        artifact_sha256=cast(str, decoded["artifact_sha256"]),
        sequence=cast(int, decoded["sequence"]),
        created_at=_parse_time(cast(str, decoded["created_at"]), field="created_at"),
        producer_id_hash=cast(str, decoded["producer_id_hash"]),
        parent_artifact_sha256=cast(Optional[str], parent),
    )
    if encode_handoff_metadata(metadata) != payload:
        raise HandoffMetadataError("handoff metadata is not canonical V1")
    return metadata


def build_handoff_metadata(
    *,
    artifact_kind: Literal["task", "session"],
    artifact_bytes: bytes,
    sequence: int,
    created_at: datetime,
    producer_id_hash: str,
    parent_artifact_sha256: Optional[str] = None,
) -> HandoffMetadataV1:
    """Build metadata without retaining or returning the artifact body."""
    if not isinstance(artifact_bytes, bytes):
        raise HandoffMetadataError("artifact_bytes must be bytes")
    return HandoffMetadataV1(
        schema_version="handoff-metadata-v1.0",
        artifact_kind=artifact_kind,
        artifact_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
        sequence=sequence,
        created_at=created_at,
        producer_id_hash=producer_id_hash,
        parent_artifact_sha256=parent_artifact_sha256,
    )


def project_handoff_metadata(
    metadata: HandoffMetadataV1,
    artifact_bytes: bytes,
    context: HandoffAdapterContext,
    *,
    previous: Optional[HandoffMetadataV1] = None,
    previous_observation: Optional[CanonicalObservationV1] = None,
) -> HandoffProjectionResult:
    """Verify artifact and sequence, then emit an authority-free observation."""
    if not isinstance(artifact_bytes, bytes):
        raise HandoffMetadataError("artifact_bytes must be bytes")
    if hashlib.sha256(artifact_bytes).hexdigest() != metadata.artifact_sha256:
        raise HandoffMetadataError("artifact SHA-256 does not match the sidecar")
    _validate_sequence(metadata, previous)
    if previous is None:
        if previous_observation is not None:
            raise HandoffMetadataError("initial sequence cannot declare a previous observation")
        parent_event_ids: Tuple[str, ...] = ()
    else:
        if previous_observation is None:
            raise HandoffMetadataError("previous observation is required for parent binding")
        _validate_previous_observation(previous, previous_observation)
        parent_event_ids = (previous_observation.event_id,)
    event_id = _event_id(metadata)
    locator_id = _domain_digest(
        "artifact-locator",
        "%s:%d:%s:%s"
        % (
            metadata.artifact_kind,
            metadata.sequence,
            metadata.artifact_sha256,
            metadata.producer_id_hash,
        ),
    )
    observation = CanonicalObservationV1(
        schema_version="portfolio-observation-v1.0",
        event_id=event_id,
        project_id=context.project_id,
        repository_id=context.repository_id,
        repository_sha=context.repository_sha,
        occurred_at=metadata.created_at,
        producer_id_hash=metadata.producer_id_hash,
        producer_attestation="unattested",
        source_surface=context.source_surface,
        activity="handoff.%s" % metadata.artifact_kind,
        entity_refs=(
            SafeEvidencePointerV1(
                kind="artifact",
                digest=metadata.artifact_sha256,
                locator_id=locator_id,
            ),
        ),
        parent_event_ids=parent_event_ids,
        data_envelope_ref=context.data_envelope_ref,
        authority_envelope_ref=None,
        telemetry_state=context.telemetry_state,
        operational_authority="none",
    )
    mappings = (
        AdapterFieldMappingV1(
            _SOURCE_FIELDS,
            (
                "event_id",
                "occurred_at",
                "producer_id_hash",
                "activity",
                "entity_refs",
            ),
            "derived",
            "downgrade",
        ),
    )
    audit = AdapterAuditV1(
        schema_version="portfolio-adapter-audit-v1.0",
        source_model="handoff.metadata_sidecar",
        target_model="portfolio-observation-v1.0",
        completeness="partial",
        source_fields=_SOURCE_FIELDS,
        target_fields=_TARGET_FIELDS,
        mappings=mappings,
        dropped_source_fields=(),
        context_target_fields=(
            "project_id",
            "repository_id",
            "repository_sha",
            "source_surface",
            "data_envelope_ref",
            "telemetry_state",
            "parent_event_ids",
        ),
        constant_target_fields=(
            "schema_version",
            "producer_attestation",
            "authority_envelope_ref",
            "operational_authority",
        ),
        authority_downgrade=True,
        reason_codes=(
            "adapter.artifact_digest_only",
            "adapter.handoff_text_untrusted",
            "adapter.producer_unattested",
        ),
        operational_authority="none",
    )
    return HandoffProjectionResult(observation=observation, audit=audit)


def encode_portfolio_observation_v1(event: CanonicalObservationV1) -> bytes:
    encoded = _canonical_bytes(event.to_dict()) + b"\n"
    if len(encoded) > MAX_PORTFOLIO_OBSERVATION_BYTES:
        raise HandoffMetadataError("portfolio observation exceeds the V1 byte limit")
    return encoded


def decode_portfolio_observation_v1(payload: bytes) -> CanonicalObservationV1:
    """Decode exact V1 bytes using the same fail-closed rules as consumers."""
    if not isinstance(payload, bytes):
        raise HandoffMetadataError("portfolio observation payload must be bytes")
    if len(payload) > MAX_PORTFOLIO_OBSERVATION_BYTES:
        raise HandoffMetadataError("portfolio observation exceeds the V1 byte limit")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except RecursionError as exc:
        raise HandoffMetadataError("portfolio observation nesting exceeds the limit") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffMetadataError("portfolio observation is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise HandoffMetadataError("portfolio observation must be a JSON object")
    if set(value) != set(_TARGET_FIELDS):
        raise HandoffMetadataError("portfolio observation fields do not match V1")
    refs = value["entity_refs"]
    parents = value["parent_event_ids"]
    if not isinstance(refs, list):
        raise HandoffMetadataError("entity_refs must be an array")
    if not isinstance(parents, list) or any(type(item) is not str for item in parents):
        raise HandoffMetadataError("parent_event_ids must be an array of strings")
    try:
        pointers = tuple(_decode_pointer(item) for item in refs)
        observation = CanonicalObservationV1(
            schema_version=cast(Any, value["schema_version"]),
            event_id=_required_string(value, "event_id"),
            project_id=_required_string(value, "project_id"),
            repository_id=_required_string(value, "repository_id"),
            repository_sha=_required_string(value, "repository_sha"),
            occurred_at=_parse_time(_required_string(value, "occurred_at"), field="occurred_at"),
            producer_id_hash=_required_string(value, "producer_id_hash"),
            producer_attestation=cast(Any, value["producer_attestation"]),
            source_surface=cast(Any, value["source_surface"]),
            activity=_required_string(value, "activity"),
            entity_refs=pointers,
            parent_event_ids=tuple(cast(List[str], parents)),
            data_envelope_ref=_required_string(value, "data_envelope_ref"),
            authority_envelope_ref=cast(Any, value["authority_envelope_ref"]),
            telemetry_state=cast(Any, value["telemetry_state"]),
            operational_authority=cast(Any, value["operational_authority"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HandoffMetadataError("portfolio observation values violate V1") from exc
    if encode_portfolio_observation_v1(observation) != payload:
        raise HandoffMetadataError("portfolio observation is not canonical V1")
    return observation


def commit_portfolio_observation_v1(event: CanonicalObservationV1) -> Dict[str, str]:
    content_sha256 = hashlib.sha256(encode_portfolio_observation_v1(event)).hexdigest()
    value = "\0".join(
        (PORTFOLIO_COMMITMENT_DOMAIN, PORTFOLIO_OBSERVATION_V1, content_sha256)
    ).encode("ascii")
    return {
        "schema_version": "portfolio-observation-commitment-v1.0",
        "observation_schema_version": PORTFOLIO_OBSERVATION_V1,
        "domain": PORTFOLIO_COMMITMENT_DOMAIN,
        "content_sha256": content_sha256,
        "commitment_sha256": hashlib.sha256(value).hexdigest(),
        "operational_authority": "none",
    }


def _validate_sequence(
    current: HandoffMetadataV1, previous: Optional[HandoffMetadataV1]
) -> None:
    if current.sequence == 0:
        if previous is not None or current.parent_artifact_sha256 is not None:
            raise HandoffMetadataError("initial sequence cannot declare a parent")
        return
    if previous is None:
        raise HandoffMetadataError("non-initial sequence requires validated previous metadata")
    if current.artifact_kind != previous.artifact_kind:
        raise HandoffMetadataError("handoff artifact kind changed within a sequence")
    if current.producer_id_hash != previous.producer_id_hash:
        raise HandoffMetadataError("producer identity changed within a sequence")
    if current.sequence <= previous.sequence:
        raise HandoffMetadataError("sequence replay or rollback detected")
    if current.sequence != previous.sequence + 1:
        raise HandoffMetadataError("sequence gap detected")
    if current.parent_artifact_sha256 != previous.artifact_sha256:
        raise HandoffMetadataError("parent artifact binding does not match previous metadata")
    if current.artifact_sha256 == previous.artifact_sha256:
        raise HandoffMetadataError("repeated artifact digest detected")
    if current.created_at <= previous.created_at:
        raise HandoffMetadataError("handoff timestamp rollback detected")


def _event_id(metadata: HandoffMetadataV1) -> str:
    """Return a producer identifier bound to every canonical metadata field.

    The portfolio contract treats ``event_id`` as a producer claim.  Exact wire
    integrity is provided separately by ``commit_portfolio_observation_v1``.
    """
    body = {
        "metadata": metadata.to_dict(),
        "projection_schema": PORTFOLIO_OBSERVATION_V1,
    }
    return hashlib.sha256(
        b"ai-agent-handoff/event-id/v1\0" + _canonical_bytes(body)
    ).hexdigest()


def _validate_previous_observation(
    metadata: HandoffMetadataV1,
    observation: CanonicalObservationV1,
) -> None:
    if observation.event_id != _event_id(metadata):
        raise HandoffMetadataError("previous observation does not bind previous metadata")
    expected_locator = _domain_digest(
        "artifact-locator",
        "%s:%d:%s:%s"
        % (
            metadata.artifact_kind,
            metadata.sequence,
            metadata.artifact_sha256,
            metadata.producer_id_hash,
        ),
    )
    if observation.entity_refs != (
        SafeEvidencePointerV1(
            kind="artifact",
            digest=metadata.artifact_sha256,
            locator_id=expected_locator,
        ),
    ):
        raise HandoffMetadataError("previous observation evidence does not bind metadata")
    if (
        observation.occurred_at != metadata.created_at
        or observation.producer_id_hash != metadata.producer_id_hash
        or observation.activity != "handoff.%s" % metadata.artifact_kind
        or observation.producer_attestation != "unattested"
        or observation.authority_envelope_ref is not None
        or observation.operational_authority != "none"
    ):
        raise HandoffMetadataError("previous observation claims do not bind metadata")


def _domain_digest(domain: str, value: str) -> str:
    return hashlib.sha256(("ai-agent-handoff/%s\0%s" % (domain, value)).encode()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HandoffMetadataError("value is not canonical JSON data") from exc


def _parse_time(value: str, *, field: str) -> datetime:
    if not value:
        raise HandoffMetadataError("%s is required" % field)
    if not value.endswith("Z") and not re.search(r"[+-]\d{2}:\d{2}$", value):
        raise HandoffMetadataError("%s must be timezone-aware RFC 3339" % field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HandoffMetadataError("%s is not a valid timestamp" % field) from exc
    _validate_time(parsed, field=field)
    return parsed.astimezone(timezone.utc)


def _validate_time(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HandoffMetadataError("%s must be timezone-aware" % field)
    normalized = value.astimezone(timezone.utc)
    if normalized.year < 1970 or normalized > _MAX_SUPPORTED_TIME:
        raise HandoffMetadataError("%s is outside the supported range" % field)


def _format_time(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _strict_object(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HandoffMetadataError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise HandoffMetadataError("non-finite JSON value is forbidden: %s" % value)


def _required_string(value: Dict[str, object], key: str) -> str:
    result = value[key]
    if type(result) is not str:
        raise HandoffMetadataError("%s must be a string" % key)
    return cast(str, result)


def _decode_pointer(value: object) -> SafeEvidencePointerV1:
    if not isinstance(value, dict) or set(value) != {"kind", "digest", "locator_id"}:
        raise HandoffMetadataError("evidence pointer fields do not match V1")
    typed = cast(Dict[str, object], value)
    return SafeEvidencePointerV1(
        kind=cast(Any, _required_string(typed, "kind")),
        digest=_required_string(typed, "digest"),
        locator_id=_required_string(typed, "locator_id"),
    )
