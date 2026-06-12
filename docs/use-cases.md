# Use cases

## Who this is for

Developers who run **more than one AI coding agent** (e.g. Claude Code +
Codex, or several Claude sessions over days) on the same repository — and
anyone who gives a coding agent enough autonomy that a wrong `Edit`/`Bash`
call could touch secrets or production.

## The problem it solves

**Handoff:** passing context between agents by copying chat is lossy,
token-expensive, and dies with the context window. Files + git survive resets,
cost one brief instead of a whole history, and keep any number of readers in
sync.

**Guard:** instructions like "never touch `.env`" live in prompts, and prompts
get ignored under long contexts. A PreToolUse hook enforces the same rule
mechanically, outside the model.

## Practical workflows

**1. Two-agent relay (the original use).**
Agent A (architect) writes `TASK.md` (ODAF brief). The human says to agent B:
*"do TASK.md"*. B works in a branch, appends an `↪ Return` block to
`SESSION.md`, commits. A reads `SESSION.md` + `git diff` and is synchronized —
zero copy-paste between chats.

**2. Surviving your own context resets.**
Single-agent, long project: keep `SESSION.md` as the live thread. After a
compaction or a new session, the agent reads one file instead of
reconstructing days of chat.

**3. Guarding an autonomous session.**
Wire `python -m agent_guard` as a Claude Code PreToolUse hook. The agent works
freely in `src/` and `tests/`, but an edit to `.env`/`secrets/` becomes an
explicit *ask*, and `git push --force` / `rm -rf /` / `curl | sh` are denied
outright — regardless of what the prompt says.

**4. Per-project risk profiles.**
Copy `guard_config.example.json` → `guard_config.json` and encode *this*
project's red lines (`*/config/prod*`, a go-live flag, a deploy command). The
defaults stay as the baseline underneath.

## What this is not

- **Not a security sandbox.** The guard filters *known-shaped* dangerous calls
  at one hook point. It is a seatbelt, not a container — pair real isolation
  (VMs, containers, least-privilege keys) with it for untrusted work.
- **Not a guarantee against all unsafe tool use.** Glob + regex matching means
  a novel or obfuscated command that matches no pattern passes through.
- **Not an orchestration framework.** The protocol is a convention; git is the
  sync mechanism; there is no runtime to operate.

## Limitations and residual risk

- Pattern matching is syntactic: `.env` is caught, `cat .en?` may not be.
  Treat the config as a living list, not a complete one.
- Config mistakes are surfaced, not fatal: a malformed `guard_config.json`,
  a wrong-typed key, an invalid regex or a typo'd key name each produce an
  `agent-guard:` warning on stderr while the guard keeps running on the
  remaining/default rules. Watch stderr after editing the config.
- The guard sees one tool call at a time — it cannot reason about a *sequence*
  of individually-harmless calls.
- `ask` relies on the host (e.g. Claude Code) actually presenting the
  confirmation; output format is currently Claude-Code-specific.
- The protocol assumes disciplined agents: an agent that doesn't read
  `AGENTS.md`/`TASK.md` gets nothing from the convention (the guard exists
  precisely because conventions alone aren't enforcement).
