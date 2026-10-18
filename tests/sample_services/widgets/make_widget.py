# In the name of God, the Most Gracious, the Most Merciful
"""Sample tool."""

from __future__ import annotations

from pathlib import Path

from mcp_app_core.catalog import ServiceSpec

SERVICE_SPEC = ServiceSpec(
    name="make_widget",
    title="Make Widget",
    summary="Make a widget.",
    phase="implemented",
    read_only=False,
)


def make_widget(*, workspace_root: Path, label: str, output_path: str = "") -> dict[str, object]:
    """Return the label and workspace."""

    return {"label": label, "root": str(workspace_root), "output_path": output_path}
