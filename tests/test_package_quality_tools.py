from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_tool(name: str) -> ModuleType:
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_member_paths_reject_parent_absolute_and_windows_drive() -> None:
    smoke = _load_tool("package_smoke")
    assert smoke._safe_member("package/module.py")
    assert not smoke._safe_member("../outside")
    assert not smoke._safe_member("/absolute")
    assert not smoke._safe_member("C:/absolute")
    assert not smoke._safe_member("C:\\absolute")
    assert not smoke._safe_member("package/C:/nested-drive")


def test_wheel_and_sdist_reject_link_or_special_members(tmp_path: Path) -> None:
    smoke = _load_tool("package_smoke")
    wheel = tmp_path / "synthetic.whl"
    with zipfile.ZipFile(wheel, mode="w") as archive:
        link = zipfile.ZipInfo("agent_guard/link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        archive.writestr(link, "target")
    with pytest.raises(ValueError, match="link"):
        smoke._validate_wheel(wheel)

    sdist = tmp_path / "synthetic.tar.gz"
    with tarfile.open(sdist, mode="w:gz") as archive:
        fifo = tarfile.TarInfo("package/fifo")
        fifo.type = tarfile.FIFOTYPE
        archive.addfile(fifo, io.BytesIO())
    with pytest.raises(ValueError, match="non-file"):
        smoke._validate_sdist(sdist)


def test_sdist_rejects_shape_valid_archive_without_protocol_surface(tmp_path: Path) -> None:
    smoke = _load_tool("package_smoke")
    sdist = tmp_path / "synthetic.tar.gz"
    with tarfile.open(sdist, mode="w:gz") as archive:
        payload = b"synthetic"
        member = tarfile.TarInfo("package/README.md")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    with pytest.raises(ValueError, match="review or protocol"):
        smoke._validate_sdist(sdist)


def test_snapshot_bounds_post_lstat_growth_and_same_size_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    smoke = _load_tool("package_smoke")
    source = tmp_path / "artifact.whl"
    destination = tmp_path / "snapshot.whl"
    source.write_bytes(b"old!")
    monkeypatch.setattr(smoke, "MAX_ARTIFACT_BYTES", 4)
    real_open = Path.open
    reads: list[int] = []
    payloads = iter((b"grow!", b"grow!"))

    class RecordingStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            reads.append(size)
            return super().read(size)

    def replacement_open(path: Path, mode: str = "r", *args: object, **kwargs: object):
        if path == source and mode == "rb":
            return RecordingStream(next(payloads))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", replacement_open)
    with pytest.raises(ValueError, match="changed during snapshot"):
        smoke._snapshot_artifact(source, destination)
    assert reads == [5, 5]
    assert not destination.exists()

    reads.clear()
    payloads = iter((b"same", b"diff"))
    with pytest.raises(ValueError, match="changed during snapshot"):
        smoke._snapshot_artifact(source, destination)
    assert reads == [5, 5]
    assert not destination.exists()


def test_secret_gate_reports_only_location_and_rule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hygiene = _load_tool("secret_hygiene")
    candidate = tmp_path / "config.py"
    hidden_value = "synthetic-value-that-must-not-be-printed"
    candidate.write_text(f'token = "{hidden_value}"\n', encoding="utf-8")
    monkeypatch.setattr(hygiene, "_tracked_paths", lambda _root: (candidate,))

    result = hygiene.findings(tmp_path)

    assert result == ("config.py:1:credential-assignment",)
    assert hidden_value not in "".join(result)
