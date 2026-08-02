from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import pytest

from agent_guard.handoff_metadata import (
    MAX_HANDOFF_METADATA_BYTES,
    HandoffAdapterContext,
    HandoffMetadataError,
    build_handoff_metadata,
    commit_portfolio_observation_v1,
    decode_portfolio_observation_v1,
    encode_handoff_metadata,
    encode_portfolio_observation_v1,
    load_handoff_metadata,
    project_handoff_metadata,
)

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
PRODUCER = "a" * 64
DATA_ENVELOPE = "b" * 64
REPOSITORY_SHA = "c" * 40


def _metadata(
    body: bytes = b"# Synthetic task\n",
    *,
    kind: str = "task",
    sequence: int = 0,
    created_at: datetime = datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
    parent: Optional[str] = None,
):
    return build_handoff_metadata(
        artifact_kind=kind,  # type: ignore[arg-type]
        artifact_bytes=body,
        sequence=sequence,
        created_at=created_at,
        producer_id_hash=PRODUCER,
        parent_artifact_sha256=parent,
    )


def _context(**updates: object) -> HandoffAdapterContext:
    values: Dict[str, object] = {
        "project_id": "security-project",
        "repository_id": "owner/security-project",
        "repository_sha": REPOSITORY_SHA,
        "source_surface": "agent",
        "data_envelope_ref": DATA_ENVELOPE,
        "telemetry_state": "complete",
    }
    values.update(updates)
    return HandoffAdapterContext(**values)  # type: ignore[arg-type]


def test_metadata_round_trip_is_strict_canonical_and_bounded() -> None:
    metadata = _metadata()
    encoded = encode_handoff_metadata(metadata)

    assert len(encoded) <= MAX_HANDOFF_METADATA_BYTES
    assert load_handoff_metadata(encoded) == metadata
    assert encoded.endswith(b"\n")
    with pytest.raises(HandoffMetadataError, match="canonical"):
        load_handoff_metadata(json.dumps(metadata.to_dict(), indent=2).encode())


def test_loader_rejects_unknown_missing_duplicate_wrong_type_and_oversize() -> None:
    encoded = encode_handoff_metadata(_metadata())
    data = json.loads(encoded)
    data["operational_authority"] = "allow"
    with pytest.raises(HandoffMetadataError, match="fields"):
        load_handoff_metadata(json.dumps(data).encode())
    data = json.loads(encoded)
    del data["artifact_sha256"]
    with pytest.raises(HandoffMetadataError, match="fields"):
        load_handoff_metadata(json.dumps(data).encode())
    duplicate = encoded.replace(
        b'"schema_version":"handoff-metadata-v1.0"',
        b'"schema_version":"handoff-metadata-v1.0",'
        b'"schema_version":"handoff-metadata-v1.0"',
    )
    with pytest.raises(HandoffMetadataError, match="duplicate"):
        load_handoff_metadata(duplicate)
    data = json.loads(encoded)
    data["sequence"] = True
    with pytest.raises(HandoffMetadataError, match="wrong JSON type"):
        load_handoff_metadata(json.dumps(data).encode())
    with pytest.raises(HandoffMetadataError, match="byte limit"):
        load_handoff_metadata(b"x" * (MAX_HANDOFF_METADATA_BYTES + 1))
    deeply_nested = b"[" * 1_100 + b"0" + b"]" * 1_100
    with pytest.raises(HandoffMetadataError, match="nesting|JSON object"):
        load_handoff_metadata(deeply_nested)


def test_loader_rejects_naive_invalid_and_out_of_range_time() -> None:
    data = _metadata().to_dict()
    for value in (
        "",
        "2026-08-02T10:00:00",
        "not-a-time",
        "1969-12-31T23:59:59Z",
        "2101-01-01T00:00:00Z",
    ):
        changed = dict(data, created_at=value)
        payload = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        with pytest.raises(HandoffMetadataError):
            load_handoff_metadata(payload)


def test_sidecar_rejects_intrinsic_sequence_parent_mismatch() -> None:
    initial = _metadata().to_dict()
    invalid_values = (
        dict(initial, parent_artifact_sha256="d" * 64),
        dict(initial, sequence=1),
    )
    for value in invalid_values:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        with pytest.raises(HandoffMetadataError, match="initial sequence|only the initial"):
            load_handoff_metadata(payload)


def test_projection_verifies_artifact_sha_and_never_emits_markdown() -> None:
    body = b"# Synthetic task\nsecret-shaped-example-is-still-not-output\n"
    metadata = _metadata(body)
    result = project_handoff_metadata(metadata, body, _context())
    encoded = encode_portfolio_observation_v1(result.observation)

    assert body not in encoded
    assert b"secret-shaped-example" not in encoded
    assert result.observation.entity_refs[0].digest == hashlib.sha256(body).hexdigest()
    assert result.observation.producer_attestation == "unattested"
    assert result.observation.authority_envelope_ref is None
    assert result.observation.operational_authority == "none"
    with pytest.raises(HandoffMetadataError, match="does not match"):
        project_handoff_metadata(metadata, b"changed", _context())


def test_initial_sequence_rejects_parent_or_previous() -> None:
    body = b"initial"
    initial = _metadata(body)
    with pytest.raises(HandoffMetadataError, match="initial"):
        project_handoff_metadata(
            replace(initial, parent_artifact_sha256="d" * 64), body, _context()
        )
    with pytest.raises(HandoffMetadataError, match="initial"):
        project_handoff_metadata(initial, body, _context(), previous=initial)


def test_valid_sequence_binds_parent_and_canonical_parent_event() -> None:
    first_body = b"first"
    second_body = b"second"
    first = _metadata(first_body)
    second = _metadata(
        second_body,
        sequence=1,
        created_at=first.created_at + timedelta(seconds=1),
        parent=first.artifact_sha256,
    )
    first_result = project_handoff_metadata(first, first_body, _context())
    second_result = project_handoff_metadata(
        second,
        second_body,
        _context(),
        previous=first,
        previous_observation=first_result.observation,
    )
    assert second_result.observation.parent_event_ids == (
        first_result.observation.event_id,
    )


@pytest.mark.parametrize(
    ("sequence", "parent", "seconds", "message"),
    [
        (0, None, 1, "initial"),
        (2, "valid", 1, "gap"),
        (1, "wrong", 1, "parent"),
        (1, "valid", 0, "timestamp rollback"),
    ],
)
def test_sequence_replay_gap_rollback_and_parent_fail_closed(
    sequence: int, parent: Optional[str], seconds: int, message: str
) -> None:
    first = _metadata(b"first")
    parent_digest = first.artifact_sha256 if parent == "valid" else parent
    if parent_digest == "wrong":
        parent_digest = "d" * 64
    current = _metadata(
        b"second",
        sequence=sequence,
        created_at=first.created_at + timedelta(seconds=seconds),
        parent=parent_digest,
    )
    with pytest.raises(HandoffMetadataError, match=message):
        project_handoff_metadata(current, b"second", _context(), previous=first)


def test_repeated_artifact_digest_is_rejected() -> None:
    body = b"same"
    first = _metadata(body)
    second = _metadata(
        body,
        sequence=1,
        created_at=first.created_at + timedelta(seconds=1),
        parent=first.artifact_sha256,
    )
    with pytest.raises(HandoffMetadataError, match="repeated"):
        project_handoff_metadata(second, body, _context(), previous=first)


def test_sequence_rejects_producer_identity_change() -> None:
    first = _metadata(b"first")
    second = replace(
        _metadata(
            b"second",
            sequence=1,
            created_at=first.created_at + timedelta(seconds=1),
            parent=first.artifact_sha256,
        ),
        producer_id_hash="e" * 64,
    )
    with pytest.raises(HandoffMetadataError, match="producer identity"):
        project_handoff_metadata(second, b"second", _context(), previous=first)


def test_same_or_lower_sequence_is_rejected_as_replay_or_rollback() -> None:
    previous = _metadata(b"previous", sequence=1, parent="d" * 64)
    for sequence in (0, 1):
        current = _metadata(
            b"current",
            sequence=sequence,
            created_at=previous.created_at + timedelta(seconds=1),
            parent=previous.artifact_sha256 if sequence else None,
        )
        with pytest.raises(HandoffMetadataError, match="initial|replay|rollback"):
            project_handoff_metadata(current, b"current", _context(), previous=previous)


def test_loss_audit_covers_exact_source_and_owner_target_universes() -> None:
    result = project_handoff_metadata(_metadata(), b"# Synthetic task\n", _context())
    audit = result.audit
    source = [value for item in audit.mappings for value in item.source_fields]
    target = [value for item in audit.mappings for value in item.target_fields]

    assert set(source) | set(audit.dropped_source_fields) == set(audit.source_fields)
    assert len(source) + len(audit.dropped_source_fields) == len(audit.source_fields)
    assert audit.dropped_source_fields == ()
    assert set(target) | set(audit.context_target_fields) | set(
        audit.constant_target_fields
    ) == set(audit.target_fields)
    assert set(asdict(result.observation)) == set(audit.target_fields)
    assert audit.authority_downgrade is True
    assert audit.operational_authority == "none"


def test_context_rejects_noncanonical_repository_sha_and_data_binding() -> None:
    with pytest.raises(HandoffMetadataError, match="repository_id"):
        _context(repository_id="not-a-repository")
    with pytest.raises(HandoffMetadataError, match="Git object"):
        _context(repository_sha="main")
    with pytest.raises(HandoffMetadataError, match="data_envelope_ref"):
        _context(data_envelope_ref="trusted")
    with pytest.raises(HandoffMetadataError, match="source_surface"):
        _context(source_surface="provider")


def test_owner_schema_pin_field_universe_and_commitment_relation() -> None:
    schema_path = ROOT / "contracts" / "portfolio-observation.v1.schema.json"
    pin = json.loads(
        (ROOT / "contracts" / "portfolio-observation.v1.owner-pin.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    manifest_path = ROOT / "contracts" / "portfolio-observation.v1.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = project_handoff_metadata(_metadata(), b"# Synthetic task\n", _context())
    commitment = commit_portfolio_observation_v1(result.observation)

    assert hashlib.sha256(schema_path.read_bytes()).hexdigest() == pin["schema_sha256"]
    assert pin["schema_sha256"] == (
        "19371f188b080accfdac489e985b9642f547c3300c0b56b44527eb97f550c26f"
    )
    assert pin["owner_manifest_sha256"] == (
        "fecbe08da3e48250aaeff2ea19bf50efdbd2c3aa532af9cae8be50b4c8321554"
    )
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == pin[
        "owner_manifest_sha256"
    ]
    assert manifest["event_id_semantics"] == "producer_claim_shape_only"
    assert manifest["commitment_domain"] == commitment["domain"]
    assert pin["owner_repository"] == "krivonosoff161/agentic-security-harness"
    assert pin["owner_main_sha"] == "372ce4161b1e9232215835b8dc4f3014d4726f34"
    assert pin["adapter_audit_source_model"] == result.audit.source_model
    assert set(schema["required"]) == set(result.audit.target_fields)
    assert schema["properties"]["entity_refs"]["maxItems"] == 64
    assert schema["properties"]["parent_event_ids"]["maxItems"] == 64
    assert commitment["domain"] == "agentic-security-portfolio/observation/v1.0"
    assert commitment["operational_authority"] == "none"

    metadata_schema = json.loads(
        (ROOT / "contracts" / "handoff-metadata.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(metadata_schema["required"]) == set(_metadata().to_dict())
    assert metadata_schema["additionalProperties"] is False
    assert metadata_schema["oneOf"] == [
        {
            "properties": {
                "parent_artifact_sha256": {"type": "null"},
                "sequence": {"const": 0},
            },
            "required": ["sequence", "parent_artifact_sha256"],
        },
        {
            "properties": {
                "parent_artifact_sha256": {
                    "pattern": "^[0-9a-f]{64}$",
                    "type": "string",
                },
                "sequence": {"minimum": 1},
            },
            "required": ["sequence", "parent_artifact_sha256"],
        },
    ]


def test_strict_consumer_round_trip_and_separate_context_commitment() -> None:
    body = b"# Synthetic task\n"
    first = project_handoff_metadata(_metadata(body), body, _context()).observation
    encoded = encode_portfolio_observation_v1(first)

    assert decode_portfolio_observation_v1(encoded) == first
    changed_sha = project_handoff_metadata(
        _metadata(body),
        body,
        _context(repository_sha="d" * 40),
    ).observation
    changed_project = project_handoff_metadata(
        _metadata(body),
        body,
        _context(project_id="other-project"),
    ).observation
    assert changed_sha.event_id == first.event_id
    assert changed_project.event_id == first.event_id
    assert commit_portfolio_observation_v1(changed_sha) != (
        commit_portfolio_observation_v1(first)
    )
    assert commit_portfolio_observation_v1(changed_project) != (
        commit_portfolio_observation_v1(first)
    )


def test_parent_uses_verified_previous_event_id_across_context_change() -> None:
    first_body = b"first"
    second_body = b"second"
    first = _metadata(first_body)
    first_observation = project_handoff_metadata(
        first, first_body, _context()
    ).observation
    second = _metadata(
        second_body,
        sequence=1,
        created_at=first.created_at + timedelta(seconds=1),
        parent=first.artifact_sha256,
    )
    second_observation = project_handoff_metadata(
        second,
        second_body,
        _context(repository_sha="d" * 40, data_envelope_ref="e" * 64),
        previous=first,
        previous_observation=first_observation,
    ).observation

    assert second_observation.parent_event_ids == (first_observation.event_id,)
    with pytest.raises(HandoffMetadataError, match="previous observation"):
        project_handoff_metadata(second, second_body, _context(), previous=first)
    with pytest.raises(HandoffMetadataError, match="does not bind"):
        project_handoff_metadata(
            second,
            second_body,
            _context(),
            previous=first,
            previous_observation=replace(first_observation, event_id="f" * 64),
        )


def test_runtime_guard_consumer_golden_is_exact_and_pinned() -> None:
    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "portfolio-observation-v1"
        / "handoff-metadata.json"
    )
    pin = json.loads(
        (ROOT / "contracts" / "portfolio-observation.v1.consumer-pin.json").read_text(
            encoding="utf-8"
        )
    )
    body = b"# Synthetic task\n"
    encoded = encode_portfolio_observation_v1(
        project_handoff_metadata(_metadata(body), body, _context()).observation
    )

    assert encoded == fixture.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == pin["fixture_sha256"]
    assert pin["consumer_repository"] == "krivonosoff161/agentic-runtime-guard"
    assert pin["consumer_sha"] == "f9dcc67e3b9baf2ed753f582e701be2d32bb9020"
    assert pin["consumer_module_sha256"] == (
        "2a68937ce1a69a9627bc31f349a710308805103d4ce836c7fdd6bc538b1afc23"
    )
    assert pin["fixture_path"] == (
        "tests/fixtures/portfolio-observation-v1/handoff-metadata.json"
    )
    assert pin["operational_authority"] == "none"


def test_mapping_runtime_enums_fail_closed() -> None:
    from agent_guard.handoff_metadata import AdapterFieldMappingV1

    with pytest.raises(HandoffMetadataError, match="transformation"):
        AdapterFieldMappingV1(
            ("artifact_kind",),
            ("activity",),
            "invented",  # type: ignore[arg-type]
            "none",
        )
    with pytest.raises(HandoffMetadataError, match="authority effect"):
        AdapterFieldMappingV1(
            ("artifact_kind",),
            ("activity",),
            "derived",
            "promote",  # type: ignore[arg-type]
        )


def test_observation_is_deterministic_and_offset_normalized() -> None:
    body = b"task"
    utc = _metadata(body)
    offset = timezone(timedelta(hours=3))
    same = _metadata(
        body,
        created_at=datetime(2026, 8, 2, 13, 0, tzinfo=offset),
    )
    first = project_handoff_metadata(utc, body, _context()).observation
    second = project_handoff_metadata(same, body, _context()).observation
    assert encode_portfolio_observation_v1(first) == encode_portfolio_observation_v1(second)
