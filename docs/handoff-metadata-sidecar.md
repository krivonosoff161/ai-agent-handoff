# Handoff metadata sidecar

`handoff-metadata-v1.0` is an optional machine-readable companion to one
`TASK.md` or `SESSION.md` artifact. It exists to support bounded integrity and
sequence checks without treating Markdown as executable instructions or trusted
authority.

## Contract

The canonical UTF-8 JSON sidecar is limited to 4096 bytes and ends in one LF. It
contains exactly:

- `schema_version`;
- `artifact_kind` (`task` or `session`);
- `artifact_sha256` over the exact caller-supplied artifact bytes;
- a non-negative monotonic `sequence`;
- a timezone-aware `created_at` normalized to UTC microseconds;
- a digest-shaped `producer_id_hash` claim;
- `parent_artifact_sha256`, null only for the initial record.

Unknown, missing, duplicate, non-canonical, oversized, non-finite, or wrong-typed
input is rejected. A non-initial record also requires the validated previous
metadata record. Replay, gaps, rollback, changed artifact kind, repeated artifact
digest, producer change, timestamp rollback, and wrong parent binding fail closed.
For a non-initial record the caller must also provide the previously validated
canonical observation; the child links that exact event rather than recomputing a
parent identifier under the child's possibly changed repository context.

## Portfolio projection

`project_handoff_metadata()` verifies the artifact SHA-256 before projecting the
sidecar. The output conforms to `portfolio-observation-v1.0` and contains only
digest-shaped evidence pointers. It never returns or serializes the Markdown body.

The owner contract is pinned in
`contracts/portfolio-observation.v1.owner-pin.json`; the vendored schema hash must
match that pin, as must the vendored owner manifest. Canonical output is independently strict-decoded before consumers
use it, and a domain-separated commitment binds its exact bytes. The observation
always has:

- `producer_attestation: unattested`;
- `authority_envelope_ref: null`;
- `operational_authority: none`.

The same owner pin binds the reviewed Harness revision that explicitly accepts
`handoff.metadata_sidecar` as an adapter-audit source model. It does not make the
producer attested or the audit authoritative.

The exhaustive adapter audit states which sidecar fields were mapped, dropped,
provided by explicit local context, or fixed as constants. Context includes the
project, repository, exact Git object, source surface, data-envelope digest and
telemetry state. Context is never inferred from the Markdown.

## Non-claims

The sidecar does not authenticate a producer, prove the Markdown true, authorize an
action, coordinate concurrent writers, persist state, open files, contact a provider,
or enforce a decision. The `event_id` is a digest-shaped producer claim bound to all
canonical sidecar fields. The separate commitment is the integrity binding for the
complete canonical observation bytes, including explicit projection context.
