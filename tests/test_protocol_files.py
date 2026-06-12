# -*- coding: utf-8 -*-
"""The protocol has no code — but its files are the public contract, so pin them.

These tests keep templates and the worked example structurally honest: every
documented section exists, and the example actually follows the template it
claims to demonstrate.
"""
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ODAF_SECTIONS = ("## Outcome", "## Data", "## Action", "## Format")


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_task_template_has_full_odaf_contract():
    text = _read("templates/TASK.md")
    for section in ODAF_SECTIONS + ("## Done when", "## Boundaries"):
        assert section in text, f"templates/TASK.md lost section {section!r}"


def test_session_template_has_return_block():
    text = _read("templates/SESSION.md")
    assert "## Current focus" in text
    assert "↪ Return" in text
    for field in ("**What:**", "**Files:**", "**Verified:**"):
        assert field in text


def test_agents_template_has_roles_and_never_list():
    text = _read("templates/AGENTS.md")
    assert "## Roles" in text and "## NEVER" in text and "## ALWAYS" in text


def test_task_example_follows_the_template():
    text = _read("examples/TASK.example.md")
    for section in ODAF_SECTIONS + ("## Done when", "## Boundaries"):
        assert section in text, f"examples/TASK.example.md lost section {section!r}"


def test_session_example_has_filled_return_block():
    text = _read("examples/SESSION.example.md")
    assert "↪ Return" in text and "**Verified:**" in text


def test_example_guard_config_is_valid_and_loadable():
    import json
    import sys
    src = _ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from agent_guard import load_config
    cfg_path = _ROOT / "guard_config.example.json"
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    # the shipped example must load cleanly (no warnings-worthy content)
    cfg = load_config(str(cfg_path))
    for key in ("deny_paths", "confirm_paths",
                "deny_command_patterns", "confirm_command_patterns"):
        assert cfg[key] == raw[key]
