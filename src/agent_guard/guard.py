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


_LIST_KEYS = ("deny_paths", "deny_command_patterns",
              "confirm_paths", "confirm_command_patterns")


def _warn(msg: str) -> None:
    """Config problems go to stderr — never stdout (stdout is the hook channel)."""
    print(f"agent-guard: {msg}", file=sys.stderr)


def load_config(path: str | None = None) -> dict:
    """Load guard_config.json from `path` or the current working directory.

    Merge semantics: per-key REPLACE — a key present in the file replaces the
    default list entirely (start from guard_config.example.json to keep the
    defaults). Anything wrong is reported on stderr and never crashes the
    guard: malformed JSON falls back to the built-in defaults; a key with the
    wrong type keeps its default; an invalid regex is dropped; an unknown key
    is ignored (this catches typos like "deny_path" that would otherwise
    silently disable protection).
    """
    p = Path(path) if path else Path.cwd() / "guard_config.json"
    if not p.exists():
        return dict(DEFAULT_CONFIG)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        _warn(f"could not parse {p.name} ({exc}); using built-in defaults")
        return dict(DEFAULT_CONFIG)
    if not isinstance(raw, dict):
        _warn(f"{p.name} must contain a JSON object; using built-in defaults")
        return dict(DEFAULT_CONFIG)
    cfg = dict(DEFAULT_CONFIG)
    for key, value in raw.items():
        if key not in _LIST_KEYS:
            _warn(f"unknown key '{key}' in {p.name} ignored "
                  f"(known keys: {', '.join(_LIST_KEYS)})")
            continue
        if not (isinstance(value, list)
                and all(isinstance(v, str) for v in value)):
            _warn(f"'{key}' in {p.name} must be a list of strings; "
                  "keeping the default for this key")
            continue
        if key.endswith("_command_patterns"):
            kept = []
            for rx in value:
                try:
                    re.compile(rx)
                    kept.append(rx)
                except re.error as exc:
                    _warn(f"invalid regex {rx!r} in '{key}' dropped ({exc})")
            value = kept
        cfg[key] = value
    return cfg


def _path_match(fp: str, pattern: str) -> bool:
    """Glob match with a deliberate substring fallback.

    `fnmatch` alone misses relative-path cases (e.g. pattern '*/.ssh/*' vs
    path '.ssh/id_rsa'), so the pattern's core — the glob stripped of leading/
    trailing '*' and '/' — is also checked as a plain substring. This errs on
    the side of FALSE POSITIVES ('.env' also flags 'x.environment.py'), which
    for a safety guard is the right direction: an over-eager 'ask' costs one
    confirmation; a miss costs a secret.
    """
    pat = pattern.lower()
    return bool(fp) and (fnmatch.fnmatch(fp, pat) or pat.strip("*/") in fp)


def decide(tool_input: dict, config: dict | None = None) -> tuple[str, str]:
    """Return (decision, reason). decision in {"deny", "ask", "allow"}. Pure / no I/O.

    Scope asymmetry (intentional): deny_command_patterns run against the
    `command` field only, while confirm_command_patterns run against command
    AND written content (`content` / `new_string`) — writing text that merely
    mentions a dangerous command should at most ask, never hard-block.
    Patterns must be valid regexes — `decide` does not sanitize its `config`
    argument; pass configs through `load_config` (which does).
    """
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
        # read BYTES and decode as UTF-8 ourselves: a non-UTF-8 console locale
        # (cp1251 etc.) would mangle the payload, and PowerShell pipes prepend
        # a BOM — either way json.loads would fail and the guard would
        # silently fail open. utf-8-sig strips the BOM for free.
        raw = sys.stdin.buffer.read().decode("utf-8-sig", "replace")
    except AttributeError:   # stdin already text (e.g. captured/redirected)
        raw = sys.stdin.read().lstrip(chr(0xFEFF))
    try:
        data = json.loads(raw)
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
