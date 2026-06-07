# -*- coding: utf-8 -*-
"""Offline tests for the guard hook (pure decide(), no stdin/process)."""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent_guard import DEFAULT_CONFIG, decide  # noqa: E402


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
