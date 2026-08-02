# -*- coding: utf-8 -*-
"""agent_guard — a PreToolUse safety guard for AI coding agents."""
from .guard import DEFAULT_CONFIG, decide, load_config, main
from .handoff_metadata import (
    AdapterAuditV1,
    AdapterFieldMappingV1,
    CanonicalObservationV1,
    HandoffAdapterContext,
    HandoffMetadataError,
    HandoffMetadataV1,
    HandoffProjectionResult,
    SafeEvidencePointerV1,
    build_handoff_metadata,
    commit_portfolio_observation_v1,
    decode_portfolio_observation_v1,
    encode_handoff_metadata,
    encode_portfolio_observation_v1,
    load_handoff_metadata,
    project_handoff_metadata,
)

__all__ = [
    "AdapterAuditV1",
    "AdapterFieldMappingV1",
    "CanonicalObservationV1",
    "DEFAULT_CONFIG",
    "HandoffAdapterContext",
    "HandoffMetadataError",
    "HandoffMetadataV1",
    "HandoffProjectionResult",
    "SafeEvidencePointerV1",
    "build_handoff_metadata",
    "commit_portfolio_observation_v1",
    "decode_portfolio_observation_v1",
    "decide",
    "encode_handoff_metadata",
    "encode_portfolio_observation_v1",
    "load_config",
    "load_handoff_metadata",
    "main",
    "project_handoff_metadata",
]
__version__ = "0.2.0"
