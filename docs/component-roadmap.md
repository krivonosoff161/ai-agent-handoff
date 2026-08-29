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

Ecosystem integration is currently **`extension_candidate`**. The standalone package is
unchanged; the separate `extensions/harness-v1/` source tree builds one operator-selected
Harness API 1 wheel. The candidate is not published, dependency-resolved, automatically
discovered, or part of a released Harness package.

The coordinated source candidates are `ai-agent-handoff==0.3.0` and
`ai-agent-handoff-harness-extension==1.0.0`. CI builds both exact artifact sets; public
index publication and the Harness optional-dependency row remain separate release gates.

## Ordered delivery gates

1. **Documentation convergence — active.** Keep this roadmap, `component.yaml`, README,
   and offline manifest tests synchronized with the central ecosystem contract.
2. **Extension contract — review candidate.** A canonical manifest targets Harness API 1
   and the future published `agentic-security-harness>=1.3,<2` package line.
3. **Installable extension — review candidate.** The nested dependency-free wheel contains
   exactly one explicit entry point and returns advisory `ExtensionFindingV1` results.
4. **Suite verification — implemented for review.** Exact source pins drive synthetic
   Distribution Discovery, approval, lifecycle binding, and run receipt tests on Linux and
   Windows. Publication remains a separate gate.
5. **Protocol deepening — separately reviewed.** Add only bounded protocol or sidecar
   capabilities that preserve the existing non-sandbox and non-authentication boundary.

No later gate is satisfied by documentation alone.

## Compatibility policy

- Standalone package metadata supports Python 3.9 and later.
- The initial ecosystem compatibility contour is Python 3.11 or later on Linux and
  Windows.
- Standalone package CI exercises Python 3.9-3.12 on both Linux and Windows, including
  source and wheel builds plus installed `agent-guard` and metadata-contract smoke.
- Harness API compatibility is `1` for the optional extension candidate. Its public
  package boundary is `agentic-security-harness>=1.3,<2`; current CI uses exact released
  Harness source SHA `c1dd69856212458ae952e43aeb2b0cc9290e8205` as compatibility evidence.

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

