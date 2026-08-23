# AI Agent Handoff component roadmap

This is the source-owned roadmap for `ai-agent-handoff`. The public ecosystem sequence and
cross-repository dependencies are owned by the
[Agentic Security Harness ecosystem roadmap](https://github.com/krivonosoff161/agentic-security-harness/blob/main/docs/ecosystem-roadmap.md).
The machine-readable component boundary is [`component.yaml`](../component.yaml).

## Current component boundary

The repository currently ships two independently usable surfaces:

- a file-and-git handoff protocol built around `TASK.md`, `SESSION.md`, and `AGENTS.md`;
- the dependency-free `agent-guard` pattern guard plus an optional bounded metadata
  sidecar with digest, sequence, parent-link, and authority-free portfolio projection.

Ecosystem integration is currently **`contract_only`**. The package does not yet implement
the future Harness Extension SDK, does not register checks with `ash`, and must not be
described as an installable Harness extension today.

## Ordered delivery gates

1. **Documentation convergence — active.** Keep this roadmap, `component.yaml`, README,
   and offline manifest tests synchronized with the central ecosystem contract.
2. **Extension contract — planned.** After Harness publishes a stable Extension SDK,
   expose versioned descriptors for metadata integrity and pattern-guard checks while
   keeping the file protocol independently usable.
3. **Installable extension — planned.** Register explicit extension entry points and return
   the common evidence/result contract without converting advisory output into authority.
4. **Suite verification — planned.** Add pinned cross-repository compatibility tests on
   Linux and Windows and publish evidence for the compatibility row.
5. **Protocol deepening — separately reviewed.** Add only bounded protocol or sidecar
   capabilities that preserve the existing non-sandbox and non-authentication boundary.

No later gate is satisfied by documentation alone.

## Compatibility policy

- Standalone package metadata supports Python 3.9 and later.
- The initial ecosystem compatibility contour is Python 3.11 or later on Linux and
  Windows.
- Harness API compatibility is `not-yet-declared` until an executable Extension SDK
  contract and cross-repository test exist.

## Document authority

- `component.yaml` and this page own this repository's ecosystem identity and local
  delivery sequence.
- `docs/project-map.md` remains the component architecture and reviewer map.
- The three `docs/security-portfolio-roadmap*` artifacts are preserved historical,
  digest-bound R4 projections. They remain evidence of the earlier portfolio contract and
  do not override the current public ecosystem roadmap.

## Claims and non-claims

The component may claim its file protocol, deterministic declared-pattern guard, and
bounded metadata-sidecar checks. It is not a sandbox, semantic verifier, cryptographic
producer authenticator, concurrency coordinator, production enforcement service, or
source of operational authority.

