# ai-agent-handoff

This package is the handoff/protocol component of the
[Agentic Security Harness ecosystem](https://github.com/krivonosoff161/agentic-security-harness/blob/main/docs/ecosystem-roadmap.md).
Its source-owned identity and ordered integration gates are recorded in
[`component.yaml`](component.yaml) and the
[component roadmap](docs/component-roadmap.md).

Current ecosystem status is **contract-only**: the package is independently usable, but
it is not yet an installable `ash` extension. The former
[Security Portfolio module contract](docs/security-portfolio-roadmap.md) is preserved as
historical, digest-bound R4 evidence.

[![Tests](https://github.com/krivonosoff161/ai-agent-handoff/actions/workflows/tests.yml/badge.svg)](https://github.com/krivonosoff161/ai-agent-handoff/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

**A file-based protocol for handing off work between AI coding agents — plus a PreToolUse safety guard that puts deny/ask gates in front of the secret/prod surface.**

Multi-agent setups usually pass context by **copying chat** between agents: lossy, token-expensive, drift-prone. This is the opposite — agents coordinate through three small files and a `git`-based sync, so a handoff costs **one brief, not the whole history**.

> Distilled from a real Claude + Codex workflow on a long-running project. Templates + an installable, dependency-free guard hook + a worked example. No framework, no lock-in.

---

## Where it fits

This repository is the handoff/protocol layer in the public Agentic AI Security
toolchain:

```
llm-safety-playbooks -> ai-agent-handoff -> agentic-transfer-verifier -> agentic-security-harness
```

- [`llm-safety-playbooks`](https://github.com/krivonosoff161/llm-safety-playbooks)
  makes the human/agent task boundary explicit.
- `ai-agent-handoff` turns that boundary into durable files and a reviewable git
  trail.
- [`agentic-transfer-verifier`](https://github.com/krivonosoff161/agentic-transfer-verifier)
  checks provenance, trust, and authority claims across handoffs.
- [`agentic-security-harness`](https://github.com/krivonosoff161/agentic-security-harness)
  measures boundary failures with traces, scorecards, and reports.

The guard is a local seatbelt for known-shaped risky paths and commands. It is
not a sandbox and does not claim to make an agent safe by itself.

Portfolio-level documentation authority and public/private storage rules live in
the [Documentation Contract](https://github.com/krivonosoff161/krivonosoff161/blob/main/docs/documentation-contract.md).
This repository owns the handoff protocol and guard; it does not redefine the
whole portfolio.

---

## The loop

```
   Agent A writes TASK.md  ──►  Agent B reads TASK.md (no chat replay)
                                       │
                                       ▼
                                 B works in a branch
                                       │
   A reads SESSION.md   ◄──  B appends "↪ Return" to SESSION.md + commits
   + git log / git diff
```

1. **A → B:** A writes a self-contained `TASK.md` (ODAF: Outcome · Data · Action · Format).
2. **B executes:** reads the brief — no dialog replay — works in a branch.
3. **B → A:** appends a `↪ Return` block to `SESSION.md` and commits.
4. **A reviews:** reads `SESSION.md` + `git diff` and verifies freshness and scope.

Token cost is **O(brief)**, not **O(history)**. The files survive a context reset,
but freshness, sequencing, concurrent writers, and repository state still require
explicit verification. See [docs/protocol.md](docs/protocol.md).

---

## What's inside

- **[templates/](templates/)** — `TASK.md` (ODAF brief) · `SESSION.md` (live state + return channel) · `AGENTS.md` (rules + roles) · `ODAF.md` (task framing).
- **[src/agent_guard/](src/agent_guard/)** — an installable PreToolUse safety guard (deny / ask / allow) for secrets, prod, and dangerous commands. Zero dependencies, tested.
- **[Handoff metadata sidecar](docs/handoff-metadata-sidecar.md)** — a strict,
  bounded digest-and-sequence record that projects to the portfolio observation
  contract without publishing the Markdown body or granting authority.
- **[examples/](examples/)** — a filled-in `TASK.md` → `SESSION.md` return for a real task.
- **[docs/protocol.md](docs/protocol.md)** — the loop, the diagram, and why it's cheap.

---

## Quickstart (the protocol)

```bash
git clone https://github.com/krivonosoff161/ai-agent-handoff
cd ai-agent-handoff
cp templates/AGENTS.md AGENTS.md       # your rules + roles (read once per session)
cp templates/SESSION.md SESSION.md     # your live state
# for each handoff: write a TASK.md from templates/TASK.md
```

Tell agent A: *"write the next task into `TASK.md`"*; tell agent B: *"do `TASK.md`"*. No copy-paste between them.

---

## The safety guard

```bash
pip install -e .          # provides the `agent-guard` command + the agent_guard package
python -m pytest -q       # offline test suite, no network
```

```python
from agent_guard import decide

decide({"file_path": "/proj/.env"})                   # -> ("ask",  "edit to sensitive path ...")
decide({"command": "git push origin main --force"})   # -> ("deny", "forbidden pattern ...")
decide({"file_path": "src/app.py"})                   # -> ("allow", "")
```

Try it from the shell before wiring the hook — the guard answers in Claude Code hook format:

```bash
echo '{"tool_input": {"file_path": ".env"}}' | python -m agent_guard
# {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", ...}}

echo '{"tool_input": {"command": "pytest -q"}}' | python -m agent_guard
# (no output — allow means the guard stays out of the way)
```

Works the same from bash and PowerShell: the guard reads stdin as UTF-8 and strips a
BOM, regardless of console locale.

Wire it as a [Claude Code PreToolUse hook](https://docs.claude.com/en/docs/claude-code/hooks) in `.claude/settings.json`:

```json
{ "hooks": { "PreToolUse": [
  { "matcher": "Edit|Write|Bash",
    "hooks": [ { "type": "command", "command": "python -m agent_guard" } ] } ] } }
```

`allow` = no output (the guard stays out of the way); exit code is always 0. Configure by copying
`guard_config.example.json` → `guard_config.json` in your project root
(`deny_paths` / `confirm_paths` / `deny_command_patterns` / `confirm_command_patterns`).
Defaults protect SSH keys, `.pem`, `.env`, `secrets/`, force-push, `rm -rf /`, `curl | sh`, `sudo`.

Config rules worth knowing:

- **Per-key replace, not append** — a key in your `guard_config.json` replaces that default
  list entirely; start from the example file to keep the defaults underneath.
- **Mistakes are loud but never fatal** — malformed JSON falls back to defaults, a key with
  the wrong type keeps its default, an invalid regex is dropped, an unknown key (a typo like
  `deny_path`) is ignored; every case prints an `agent-guard:` warning to **stderr** while
  stdout stays a clean hook channel and the exit code stays 0.
- **Matching is deliberately over-eager** — path patterns also match as substrings
  (`.env` flags `x.environment.py` too). For a guard that's the right direction:
  a false *ask* costs one confirmation; a miss costs a secret.

---

## Docs

- [Component roadmap](docs/component-roadmap.md) — source-owned status and ordered ecosystem integration gates.
- [Project map](docs/project-map.md) — what's where, guard internals, reviewer checklist.
- [Use cases](docs/use-cases.md) — workflows, what this is *not* (incl. "not a sandbox"), residual risk.
- [Protocol](docs/protocol.md) — why files beat chat, the loop.
- [Trust boundaries](docs/trust-boundaries.md) — what the handoff files, git trail, and guard can prove, and where stronger verification starts.
- [Metadata sidecar](docs/handoff-metadata-sidecar.md) — integrity, sequence,
  replay and authority limits for machine-readable handoff observations.

---

## What this is not

- **Not a security sandbox.** The guard pattern-matches *known-shaped* dangerous calls at one
  hook point — a seatbelt, not a container. A novel or obfuscated command that matches no
  pattern passes through. Pair it with real isolation for untrusted work.
- **Not an orchestration framework.** The protocol is files + git + discipline; there is no
  runtime to install or operate.
- **Not a guarantee.** Details and residual risk: [docs/use-cases.md](docs/use-cases.md).

---

## Why files beat chat

- **Cheap:** B reads one brief, not the whole conversation; A reads one return + `git diff`.
- **Durable:** files remain available after a context reset; they do not prove that
  the resumed agent loaded the latest revision.
- **Shareable:** multiple agents can read the same files, but the protocol does not
  provide locking, ordering, merge, or concurrency guarantees.
- **Auditable:** everything is `git`-versioned; the guard hook is the safety net.

---

## License

MIT — see [LICENSE](LICENSE).
