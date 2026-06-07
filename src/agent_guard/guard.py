# -*- coding: utf-8 -*-
"""
agent_guard.guard — a generalized PreToolUse safety hook for AI coding agents.

Reads the tool-call payload (JSON on stdin). If the call touches a protected path
or matches a forbidden/sensitive pattern, it returns a decision:
  - "deny"  -> block it
  - "ask"   -> require explicit human confirmation
  - (allow) -> stay out of the way (no output, exit 0)

Wire it as a Claude Code PreToolUse hook (matcher: Edit|Write|Bash) via either
`agent-guard` (console script) or `python -m agent_guard`. The original use case
was gating `.env` edits and a "go live" flag in a money-handling app; here it is
generalized to protect any secret/prod surface via `guard_config.json`.

`decide()` is a pure function (no I/O), so it is trivially testable.
"""
from __future__ import annotations

import fnmatch
import io
import json
import re
import sys
from pathlib import Path

# Sensible defaults — override/extend via guard_config.json (see guard_config.example.json).
DEFAULT_CONFIG = {
    "deny_paths": ["*id_rsa", "*.pem", "*/.ssh/*"],
    "deny_command_patterns": [
        r"rm\s+-rf\s+/(?!\w)",            # rm -rf / (root)
        r"git\s+push\b.*--force\b",       # force push
        r"curl\b[^|]*\|\s*(sh|bash)\b",   # curl ... | sh
    ],
    "confirm_paths": ["*.env", "*/.env", "*/secrets/*", "*credential*", "*/config/prod*"],
    "confirm_command_patterns": [
        r"AUTO[_-]?DEPLOY\s*[:=]\s*true",
        r"\bDROP\s+TABLE\b",
        r"\bsudo\b",
    ],
}


def load_config(path: str | None = None) -> dict:
    """Load guard_config.json from `path` or the current working directory; else defaults."""
    p = Path(path) if path else Path.cwd() / "guard_config.json"
    if p.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(p.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return DEFAULT_CONFIG


def _path_match(fp: str, pattern: str) -> bool:
    pat = pattern.lower()
    return bool(fp) and (fnmatch.fnmatch(fp, pat) or pat.strip("*/") in fp)


def decide(tool_input: dict, config: dict | None = None) -> tuple[str, str]:
    """Return (decision, reason). decision in {"deny", "ask", "allow"}. Pure / no I/O."""
    cfg = config or DEFAULT_CONFIG
    fp = str(tool_input.get("file_path") or tool_input.get("path") or "").replace("\\", "/").lower()
    cmd = str(tool_input.get("command") or "")
    blob = " ".join(str(tool_input.get(k, "")) for k in ("content", "new_string", "command"))

    for pat in cfg.get("deny_paths", []):
        if _path_match(fp, pat):
            return "deny", f"edit to protected path matches '{pat}'"
    for rx in cfg.get("deny_command_patterns", []):
        if re.search(rx, cmd, re.IGNORECASE):
            return "deny", f"command matches forbidden pattern '{rx}'"
    for pat in cfg.get("confirm_paths", []):
        if _path_match(fp, pat):
            return "ask", f"edit to sensitive path matches '{pat}'"
    for rx in cfg.get("confirm_command_patterns", []):
        if re.search(rx, blob, re.IGNORECASE):
            return "ask", f"action matches sensitive pattern '{rx}'"
    return "allow", ""


def main() -> None:
    """Entry point for the PreToolUse hook (reads stdin JSON, prints a decision)."""
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass   # stdout already text / no raw buffer (e.g. captured) — fine
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)   # malformed payload -> stay out of the way
    decision, reason = decide(data.get("tool_input", {}) or {}, load_config())
    if decision != "allow":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"guard: {reason}",
        }}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
