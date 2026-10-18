# In the name of God, the Most Gracious, the Most Merciful
"""Sample contracts."""

from __future__ import annotations

MCP_CONTRACTS: dict[str, dict[str, object]] = {
    "make_widget": {
        "title": "Make Widget",
        "description": "Make a widget inside the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "output_path": {"type": "string"},
            },
            "required": ["label"],
        },
    }
}
