# Project map — for reviewers and maintainers

## What it does

Two independent pieces that work together:

1. **The handoff protocol** — three Markdown files (`TASK.md`, `SESSION.md`,
   `AGENTS.md`) that let coding agents (or an agent and a human) pass work to
   each other through the filesystem + git instead of copied chat. Pure
   convention: there is no code behind it, and that is the point.
2. **`agent_guard`** — an installable PreToolUse hook (one small module, zero
   dependencies) that answers `deny` / `ask` / `allow` for a proposed tool
   call, putting a gate between agent autonomy and secrets, prod files and
   dangerous commands.

Either piece is usable without the other.

## Mental model

```
protocol (no code):   A writes TASK.md ─► B executes ─► B appends "↪ Return"
                      to SESSION.md ─► A reads SESSION.md + git diff

guard (code):         tool-call JSON on stdin ─► decide(tool_input, config)
                      ─► deny/ask  -> hook JSON on stdout
                      ─► allow     -> no output, exit 0
```

## Key files

| Path | Role |
|---|---|
| `templates/TASK.md` · `SESSION.md` · `AGENTS.md` · `ODAF.md` | the protocol — copy into your project and fill in |
| `docs/protocol.md` | why files beat chat; the loop diagram |
| `examples/TASK.example.md` → `SESSION.example.md` | one filled-in handoff, end to end |
| `src/agent_guard/guard.py` | all guard logic: `DEFAULT_CONFIG`, `load_config()`, pure `decide()`, `main()` stdin/stdout entry |
| `guard_config.example.json` | starting point for per-project rules |
| `tests/test_guard.py` | offline tests: every decision branch, config validation/fallbacks, real-subprocess CLI behavior |
| `tests/test_protocol_files.py` | pins the protocol contract: templates and the example keep their documented sections |

## What exists today

- The four templates + a worked example of the loop.
- The guard: path globs (`deny_paths` / `confirm_paths`) and command regexes
  (`deny_command_patterns` / `confirm_command_patterns`), loaded from a local
  `guard_config.json` with per-key REPLACE over the built-in defaults.
- Config validation that fails safe and loud: malformed JSON → defaults,
  wrong-typed key → default for that key, invalid regex → dropped, unknown
  key (typo) → ignored; each case prints an `agent-guard:` warning to stderr.
  stdout is reserved for hook JSON.
- Claude Code PreToolUse output format; always exits 0; silent on `allow` and
  on malformed input (it never blocks the host tool by crashing).

## What is NOT included (by design)

- No daemon, no state, no network — the guard is one stdin→stdout process per call.
- No semantic understanding of commands: matching is globs + regex. A novel
  dangerous command that matches no pattern is allowed (see use-cases →
  limitations).
- No orchestration runtime for the protocol — git and the agents themselves
  are the runtime.

## How to inspect without reading every line

1. Read `docs/protocol.md` (32 lines) — the whole protocol.
2. Read `guard.py::decide()` (~20 lines) — the whole decision logic.
3. Run the shell demo from the README and watch the hook JSON.

## How to run checks

```bash
python -m pytest -q          # offline tests (incl. real subprocess CLI runs)
python -m ruff check .
echo '{"tool_input": {"file_path": ".env"}}' | python -m agent_guard   # -> "ask" JSON
```

CI runs pytest and ruff on Python 3.9 / 3.11 / 3.12.

## How to extend safely

- New protected surface: add patterns to `guard_config.json` in *your* project —
  no code change. Only extend `DEFAULT_CONFIG` for things that are dangerous in
  ~every project.
- New decision logic: keep `decide()` pure (no I/O) — that purity is what makes
  the branch tests trivial. I/O and config sanitizing stay in `load_config()` /
  `main()`; `decide()` assumes a sanitized config.
- Output formats for other hosts (non-Claude-Code): add a flag/env in `main()`
  only; do not leak host specifics into `decide()`.
- Template changes: keep `TASK.md` self-contained (ODAF + Done-when +
  Boundaries) — the protocol's value is that B needs nothing else.

## Reviewer checklist (for future changes, incl. agent-generated)

- [ ] `decide()` still pure and returns `(decision, reason)` with
      `decision ∈ {deny, ask, allow}`.
- [ ] Guard still exits 0 in every path (a crashing guard = a blocked agent).
- [ ] Malformed config still falls back to defaults *with a stderr warning*;
      malformed stdin still silently allows; stdout carries hook JSON only.
- [ ] Zero runtime dependencies preserved.
- [ ] New patterns covered by both a positive and a negative test
      (see `test_rm_rf_subdir_is_allowed` for the style).
- [ ] README shell demo output still matches actual CLI output.
