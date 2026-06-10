# -*- coding: utf-8 -*-
"""Offline tests for the guard hook: pure decide() + load_config/CLI I/O paths."""
import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent_guard import DEFAULT_CONFIG, decide, load_config  # noqa: E402


def test_allow_normal_edit():
    assert decide({"file_path": "src/app.py", "new_string": "x = 1"})[0] == "allow"


def test_allow_command_normal():
    assert decide({"command": "pytest -q"})[0] == "allow"


def test_ask_on_env_file():
    d, reason = decide({"file_path": "/proj/.env", "new_string": "KEY=abc"})
    assert d == "ask" and ".env" in reason


def test_ask_on_secrets_dir():
    assert decide({"file_path": "app/secrets/keys.json"})[0] == "ask"


def test_deny_pem_key():
    assert decide({"file_path": "certs/server.pem"})[0] == "deny"


def test_deny_force_push():
    assert decide({"command": "git push origin main --force"})[0] == "deny"


def test_deny_rm_rf_root():
    assert decide({"command": "rm -rf /"})[0] == "deny"


def test_rm_rf_subdir_is_allowed():
    # only catastrophic root delete is denied; a scoped build dir is fine
    assert decide({"command": "rm -rf /tmp/build"})[0] == "allow"


def test_ask_sudo_in_command():
    assert decide({"command": "sudo systemctl restart svc"})[0] == "ask"


def test_ask_auto_deploy_flag_in_content():
    assert decide({"file_path": "ci.yaml", "new_string": "AUTO_DEPLOY=true"})[0] == "ask"


def test_custom_config_overrides_confirm_paths():
    cfg = {**DEFAULT_CONFIG, "confirm_paths": ["*.secret"]}
    assert decide({"file_path": "a.secret"}, cfg)[0] == "ask"
    assert decide({"file_path": "x.env"}, cfg)[0] == "allow"   # .env no longer in override


# ── load_config I/O ──────────────────────────────────────────────────────────
def test_load_config_missing_file_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_config() == DEFAULT_CONFIG


def test_load_config_merges_file_over_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "guard_config.json").write_text(
        json.dumps({"confirm_paths": ["*.secret"]}), encoding="utf-8")
    cfg = load_config()
    assert cfg["confirm_paths"] == ["*.secret"]                  # переопределено файлом
    assert cfg["deny_paths"] == DEFAULT_CONFIG["deny_paths"]     # остальное — дефолты


def test_load_config_malformed_json_falls_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "guard_config.json").write_text("{not json", encoding="utf-8")
    assert load_config() == DEFAULT_CONFIG                       # тихий fallback — guard не падает


def test_load_config_explicit_path(tmp_path):
    p = tmp_path / "custom.json"
    p.write_text(json.dumps({"deny_paths": ["*.key"]}), encoding="utf-8")
    assert load_config(str(p))["deny_paths"] == ["*.key"]


# ── CLI entry point: real subprocess, stdin → hook JSON on stdout ────────────
def _run_cli(payload: str, cwd) -> str:
    env = {**os.environ, "PYTHONPATH": str(_SRC)}
    r = subprocess.run([sys.executable, "-m", "agent_guard"], input=payload,
                       capture_output=True, text=True, env=env, cwd=str(cwd), timeout=60)
    assert r.returncode == 0                                     # guard всегда выходит 0
    return r.stdout


def test_cli_emits_ask_decision(tmp_path):
    out = _run_cli(json.dumps({"tool_input": {"file_path": "/proj/.env"}}), tmp_path)
    data = json.loads(out)
    assert data["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "guard:" in data["hookSpecificOutput"]["permissionDecisionReason"]


def test_cli_emits_deny_decision(tmp_path):
    out = _run_cli(json.dumps({"tool_input": {"command": "git push origin main --force"}}), tmp_path)
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_cli_allow_stays_silent(tmp_path):
    out = _run_cli(json.dumps({"tool_input": {"command": "pytest -q"}}), tmp_path)
    assert out == ""                                             # allow = никакого вывода


def test_cli_malformed_stdin_exits_zero_silently(tmp_path):
    out = _run_cli("{not json", tmp_path)
    assert out == ""                                             # не мешаем работе при мусоре


def test_cli_respects_local_guard_config(tmp_path):
    (tmp_path / "guard_config.json").write_text(
        json.dumps({"confirm_paths": ["*.weird"]}), encoding="utf-8")
    out = _run_cli(json.dumps({"tool_input": {"file_path": "a.weird"}}), tmp_path)
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"
