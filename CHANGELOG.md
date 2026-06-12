# Changelog

## 0.2.0 — unreleased

### Fixed
- An invalid regex in `guard_config.json` no longer crashes the guard on
  every tool call (it used to raise `re.error` and exit non-zero, breaking
  the "always exits 0" contract). Invalid regexes are now dropped at load
  time with a stderr warning.
- The guard no longer fails open on Windows consoles: stdin was decoded with
  the console locale (e.g. cp1251), so a UTF-8 payload with a BOM — exactly
  what a PowerShell pipe produces — was rejected as malformed JSON and
  everything was silently allowed. The payload is now read as bytes and
  decoded as UTF-8 (`utf-8-sig`, BOM stripped) regardless of locale.

### Changed
- `load_config()` now validates the config and reports every problem on
  **stderr** (prefix `agent-guard:`) instead of failing silently:
  malformed JSON → built-in defaults; a key with the wrong type → default
  kept for that key; an unknown key (e.g. the typo `deny_path`) → ignored
  with a warning. Previously a malformed config silently dropped all your
  custom rules. stdout remains reserved for hook JSON; exit code stays 0.
- `load_config()` returns a copy — mutating the result no longer mutates
  `DEFAULT_CONFIG`.
- `python -m agent_guard` entry module now uses the standard
  `if __name__ == "__main__"` idiom.

### Migration
- No action needed for valid configs: known keys with list-of-string values
  behave exactly as before (per-key replace over defaults).
- If your config had a typo'd/unknown key, it was silently ignored before
  and is warned about now — fix the key name to activate the rule.

### Docs
- Documented the deliberate substring fallback in path matching, the
  deny-vs-ask scope asymmetry, per-key replace merge semantics, and the
  config warning behavior; softened safety wording ("gates in front of",
  not "keeps autonomy off") to match what pattern matching can promise.

## 0.1.0

- Initial release: handoff protocol templates + worked example, `agent_guard`
  PreToolUse hook (deny/ask/allow), offline test suite, CI.
