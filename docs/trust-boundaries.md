# Trust Boundaries

Portfolio-level documentation authority and public/private storage rules live in
the [Documentation Contract](https://github.com/krivonosoff161/krivonosoff161/blob/main/docs/documentation-contract.md).
This page defines only the local trust boundary of handoff files, the git
trail, and the guard.

This project makes agent handoffs easier to review. It does not make every
handoff trustworthy by itself.

The handoff files create durable claims. Git makes those claims inspectable.
`agent_guard` blocks or asks on known-shaped risky tool calls. Stronger
verification starts when a system checks provenance, authority, freshness,
integrity, and approval instead of trusting the text of the handoff.

## Source Baseline

This trust model uses public references as vocabulary, not as a certification:

- OpenAI Agents SDK handoffs and guardrails:
  <https://openai.github.io/openai-agents-python/handoffs/>
  and <https://openai.github.io/openai-agents-python/guardrails/>
- OpenAI agent safety guidance:
  <https://developers.openai.com/api/docs/guides/agent-builder-safety>
- Model Context Protocol security best practices:
  <https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices>
- OWASP Top 10 for LLM Applications 2025:
  <https://owasp.org/www-project-top-10-for-large-language-model-applications/>
- NIST AI RMF Generative AI Profile, NIST AI 600-1:
  <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>
- W3C PROV overview and data model:
  <https://www.w3.org/TR/prov-overview/>
  and <https://www.w3.org/TR/prov-dm/>
- in-toto attestation framework and SLSA provenance:
  <https://github.com/in-toto/attestation>
  and <https://slsa.dev/spec/v0.1/provenance>

## Artifact Claims

| Artifact | What it can show | What it cannot prove |
|---|---|---|
| `TASK.md` | The requested outcome, data boundary, expected action, output format, done-when, and stop conditions. | That the brief came from an authorized person, that it is fresh, or that the agent followed it. |
| `SESSION.md` | The current state and return block from the previous worker. | That the return block is complete, honest, non-stale, or written by the claimed actor. |
| `AGENTS.md` | Local rules, role boundaries, and operating constraints. | That every agent read it or obeyed it. |
| Git branch and diff | Which files changed and how the public history moved. | That the change is safe, correct, reviewed, or free of hidden side effects. |
| Commit message | The claimed intent of a change. | That the implementation matches the intent. |
| `agent_guard` decision | Whether one observed tool call matched configured deny/ask/allow patterns. | That a sequence of allowed calls is safe, or that an obfuscated or novel risky call will be caught. |
| Handoff metadata sidecar | Exact artifact-byte digest, bounded metadata shape, monotonic sequence and parent linkage after local verification. | Producer identity or authority, semantic truth of the Markdown, authorization, concurrency safety, or absence of omitted context. |

## Trust Checks

Before accepting a handoff, check these fields explicitly:

- **Source:** who or what produced the handoff?
- **Authority:** was that source allowed to request this action?
- **Scope:** which repo, files, accounts, tools, providers, and data classes are in bounds?
- **Freshness:** when was the claim produced, and is it still valid?
- **Evidence:** what command output, test result, diff, trace, or review supports it?
- **Integrity:** can the artifact be tied to the exact files or commits it describes?
- **Approval:** which actions needed human approval, and where is that approval recorded?
- **Residual risk:** what was not checked?

If one of these cannot be answered, the handoff should be treated as a proposal,
not as trusted state.

## Failure Modes

Common failures in file-based handoffs:

- A stale `SESSION.md` return is treated as current state.
- A copied task brief smuggles higher authority than the original requester had.
- A tool output or issue comment is pasted into `TASK.md` as if it were a user
  instruction.
- An agent reports "tests passed" without the exact command and output.
- A branch diff proves what changed, but not why the change is safe.
- A guard allows several harmless-looking calls that become risky as a sequence.
- A human merges based on the summary instead of checking the diff and evidence.

## Escalation Path

Use this repository for lightweight coordination. Escalate when the work can
write files, change permissions, install dependencies, send messages, call
providers, touch secrets, affect money, or support a public safety claim.

Escalation options:

- Use playbook wording from
  [llm-safety-playbooks](https://github.com/krivonosoff161/llm-safety-playbooks)
  before writing the handoff.
- Validate provenance and authority with
  [agentic-transfer-verifier](https://github.com/krivonosoff161/agentic-transfer-verifier).
- Measure boundary failures with
  [agentic-security-harness](https://github.com/krivonosoff161/agentic-security-harness).
- Require CI, review, and protected-branch gates before merge.
- Keep private prompts, raw model responses, credentials, and live target details
  out of public repositories.

## Design Rule

The protocol should stay small enough that an agent can actually follow it
during normal work. If a claim needs cryptographic binding, provenance graphs,
formal scoring, replay, or adversarial testing, it belongs in a verifier or
harness layer, not in these handoff templates.

The optional metadata adapter follows that rule: it exports digest-only,
unattested, authority-free observations. Its `event_id` is a producer identifier;
the separate portfolio commitment binds the exact canonical observation bytes.
