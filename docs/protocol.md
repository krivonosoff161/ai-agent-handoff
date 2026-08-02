# The handoff protocol

## The problem
Multi-agent setups usually pass context by **copying chat** between agents. That is
lossy (summaries drop detail), expensive (re-sending history burns tokens), and
drift-prone (agents fall out of sync).

## The idea: files are the contract
Use the filesystem as shared memory. Three files do the work:

| File | Direction | Purpose |
|---|---|---|
| `TASK.md` | A → B | self-contained brief (ODAF). The *only* thing B needs to start. |
| `SESSION.md` | shared | live state + B's return block. Source of truth both read. |
| `AGENTS.md` | shared | rules + roles + the loop. Read once per session. |

## The loop
```
   A writes TASK.md  ──►  B reads TASK.md (no chat replay)
                                  │
                                  ▼
                            B works in a branch
                                  │
   A reads SESSION.md   ◄──  B appends "↪ Return" to SESSION.md + commits
   + git log / git diff
```

## Why it's cheap
B never re-reads the conversation — it reads one brief. A never re-reads B's work
turn-by-turn — it reads one return block + `git diff`. Token cost is **O(brief)**, not
**O(history)**. The files persist across a context reset and can be shared by more
than two agents, but reading them does not prove freshness or synchronization. The
protocol has no locking, ordering, or concurrent-writer guarantee; Git state and the
handoff revision must be verified explicitly.

## Safety
The `NEVER` list in `AGENTS.md` is backed mechanically by a PreToolUse guard
(`agent_guard`, wired as `python -m agent_guard`): edits to secrets/prod or dangerous
commands that match its patterns are blocked or require explicit human confirmation.
That covers the *known-shaped* dangerous surface, not everything — the guard is
pattern matching, not a sandbox (see [use-cases](use-cases.md) for the limits).
