# AGENTS — shared rules for the agent team

> Every agent reads this + `SESSION.md` before acting. Keep it short and authoritative.

## Roles
| Agent | Where | Responsibility |
|---|---|---|
| <Agent A> | <local / CLI> | architecture, decisions, executes |
| <Agent B> | <IDE / remote> | second opinion, review, drafts |

## Loop (how handoff works)
1. **A → B:** A writes a self-contained `TASK.md` (ODAF).
2. **B executes:** B reads `TASK.md` (no dialog replay), works in a branch.
3. **B → A:** B appends a `↪ Return` block to `SESSION.md` and commits.
4. **A syncs:** A reads `SESSION.md` + `git log` / `git diff` — in sync, no human relay.

## ALWAYS
- Read `TASK.md` + `SESSION.md` first.
- Update `SESSION.md` when a decision is made or a task finishes.
- Keep changes small; one logical change per commit.

## NEVER (require explicit human approval)
- Touch production / live systems.
- Edit secrets / `.env` / credentials.
- Enable "go live" / auto-deploy flags.

> The `NEVER` list is backed mechanically by a PreToolUse guard (pattern-based, not a sandbox) — see `agent_guard` (`python -m agent_guard`).
