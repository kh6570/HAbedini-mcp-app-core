# In the name of God, the Most Gracious, the Most Merciful
"""Path redaction for logs and traces."""

from __future__ import annotations

from pathlib import Path

from mcp_app_core.errors import SandboxViolationError
from mcp_app_core.redaction import redact_log_value, redact_paths, redact_paths_processor


def test_redacts_workspace_executable_and_schematic(tmp_path: Path) -> None:
    workspace = tmp_path / "circuits"
    workspace.mkdir()
    executable = tmp_path / "QSPICE64.exe"
    schematic = workspace / "amp.qsch"
    other = workspace / "notes.txt"
    text = f"{executable} {schematic} {other}"
    redacted = redact_paths(
        text,
        workspace_root=workspace,
        executable_path=executable,
        schematic_paths=(schematic,),
    )
    assert "<executable>" in redacted
    assert "<schematic>" in redacted
    assert "<workspace>" in redacted
    assert "notes.txt" in redacted
    assert "QSPICE64" not in redacted
    assert "amp.qsch" not in redacted
    assert str(workspace) not in redacted
    assert str(executable) not in redacted


def test_redacts_slash_case_and_escaped_forms(tmp_path: Path) -> None:
    workspace = tmp_path / "circuits"
    workspace.mkdir()
    schematic = workspace / "amp.qsch"
    other = workspace / "notes.txt"
    forward = str(other).replace("\\", "/")
    redacted = redact_paths(forward, workspace_root=workspace)
    assert "<workspace>" in redacted
    assert "notes.txt" in redacted
    assert str(workspace).replace("\\", "/") not in redacted

    swapped = redact_paths(str(schematic).swapcase(), schematic_paths=(schematic,))
    assert "<schematic>" in swapped
    assert "amp.qsch" not in swapped.casefold()

    escaped = str(schematic).replace("\\", "\\\\")
    escaped_redacted = redact_paths(f"path={escaped}", schematic_paths=(schematic,))
    assert "<schematic>" in escaped_redacted
    assert workspace.name not in escaped_redacted


def test_does_not_redact_a_longer_unrelated_path(tmp_path: Path) -> None:
    root = tmp_path / "work"
    sibling = tmp_path / "workspace"
    root.mkdir()
    sibling.mkdir()
    assert redact_paths(str(sibling), workspace_root=root) == str(sibling)

    executable = tmp_path / "QSPICE64.exe"
    text = f"notQSPICE64.exe and {executable.name}"
    redacted = redact_paths(text, executable_path=executable)
    assert "notQSPICE64.exe" in redacted
    assert "<executable>" in redacted

    schematic = root / "amp.qsch"
    assert "amp.qschematic" in redact_paths("amp.qschematic", schematic_paths=(schematic,))
    backup = redact_paths("see amp.qsch.bak", schematic_paths=(schematic,))
    assert backup == "see <schematic>.bak"


def test_several_schematics_keep_their_order(tmp_path: Path) -> None:
    workspace = tmp_path / "circuits"
    workspace.mkdir()
    first = workspace / "a.qsch"
    second = workspace / "b.asc"
    redacted = redact_paths(f"{second} then {first}", schematic_paths=(first, second))
    assert redacted.index("<schematic:2>") < redacted.index("<schematic:1>")
    assert "a.qsch" not in redacted
    assert "b.asc" not in redacted


def test_redacts_structured_log_values_without_mutating_the_event(tmp_path: Path) -> None:
    workspace = tmp_path / "circuits"
    workspace.mkdir()
    schematic = workspace / "amp.qsch"
    executable = tmp_path / "QSPICE64.exe"
    event = {
        "event": f"open {schematic}",
        "executable": executable,
        "count": 2,
        "nested": [str(workspace / "notes.txt")],
        "error": SandboxViolationError(f"Path is outside workspace root: {schematic}"),
    }
    original = {
        "event": event["event"],
        "executable": event["executable"],
        "count": event["count"],
        "nested": list(event["nested"]),
        "error": event["error"],
    }
    processor = redact_paths_processor(
        workspace_root=workspace,
        executable_path=executable,
        schematic_paths=(schematic,),
    )
    redacted = processor(None, "info", event)
    assert event["event"] == original["event"]
    assert event["executable"] == original["executable"]
    assert "<schematic>" in str(redacted["event"])
    assert redacted["executable"] == "<executable>"
    assert redacted["count"] == 2
    nested = redacted["nested"]
    assert isinstance(nested, list)
    assert "notes.txt" in str(nested[0])
    assert "<workspace>" in str(nested[0])
    assert "amp.qsch" not in str(redacted["error"])
    assert isinstance(redact_log_value(3, workspace_root=workspace), int)
