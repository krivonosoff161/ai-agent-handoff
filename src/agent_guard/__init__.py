# -*- coding: utf-8 -*-
"""agent_guard — a PreToolUse safety guard for AI coding agents."""
from .guard import DEFAULT_CONFIG, decide, load_config, main

__all__ = ["decide", "load_config", "main", "DEFAULT_CONFIG"]
__version__ = "0.1.0"
