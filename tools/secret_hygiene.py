"""Bounded supplemental public-tree hygiene gate.

The gate reports only path, line, and rule identifiers. It is not a substitute for
GitHub secret scanning or an independent review.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

MAX_TRACKED_FILES = 2_000
MAX_FILE_BYTES = 1_048_576
MAX_TOTAL_BYTES = 16_777_216
MAX_LINE_CHARS = 20_000

BLOCKED_SUFFIXES = {".db", ".key", ".p12", ".pem", ".pfx", ".sqlite", ".sqlite3"}
BLOCKED_PARTS = {".internal", "reports"}
RULES = (
    ("private-key-block", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    (
        "credential-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|password|secret|token)\b\s*[:=]\s*"
            r"[\"'][^\"'\r\n]{16,}[\"']"
        ),
    ),
    (
        "bearer-assignment",
        re.compile(r"(?i)\bauthorization\b\s*[:=]\s*[\"']bearer\s+[^\"'\s]{16,}[\"']"),
    ),
)


def _tracked_paths(root: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        check=True,
        capture_output=True,
    )
    names = result.stdout.split(b"\0")
    if names and names[-1] == b"":
        names.pop()
    if len(names) > MAX_TRACKED_FILES:
        raise ValueError("tracked-file-count")
    paths: list[Path] = []
    for raw in names:
        name = raw.decode("utf-8", errors="strict")
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError("tracked-path-shape")
        paths.append(root.joinpath(*pure.parts))
    return tuple(paths)


def findings(root: Path) -> tuple[str, ...]:
    found: list[str] = []
    total = 0
    for path in _tracked_paths(root):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            found.append(f"{relative}:0:non-regular-tracked-path")
            continue
        parts = PurePosixPath(relative).parts
        lower_name = path.name.lower()
        if (
            lower_name == ".env"
            or lower_name.startswith(".env.")
            or path.suffix.lower() in BLOCKED_SUFFIXES
            or any(part.lower() in BLOCKED_PARTS for part in parts)
        ):
            found.append(f"{relative}:0:blocked-public-path")
            continue
        data = path.read_bytes()
        total += len(data)
        if len(data) > MAX_FILE_BYTES:
            found.append(f"{relative}:0:file-scan-bound")
            continue
        if total > MAX_TOTAL_BYTES:
            raise ValueError("tracked-byte-budget")
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            found.append(f"{relative}:0:non-utf8-text")
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if len(line) > MAX_LINE_CHARS:
                found.append(f"{relative}:{line_number}:line-scan-bound")
                continue
            for rule_id, pattern in RULES:
                if pattern.search(line):
                    found.append(f"{relative}:{line_number}:{rule_id}")
    return tuple(found)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        problems = findings(root)
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as exc:
        print(f"public-tree-hygiene:error:{type(exc).__name__}")
        return 2
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
