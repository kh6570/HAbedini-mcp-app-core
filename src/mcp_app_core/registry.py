# In the name of God, the Most Gracious, the Most Merciful
"""Tool definitions derived from service specs."""

from __future__ import annotations

from dataclasses import dataclass

from mcp_app_core.catalog import ServiceSpec

_WORKSPACE_PROPERTY: dict[str, object] = {
    "type": "string",
    "description": "Optional per-call workspace root override.",
}


@dataclass(frozen=True, slots=True)
class ToolAnnotations:
    """Behavior hints for MCP clients."""

    read_only_hint: bool = False
    destructive_hint: bool = False
    idempotent_hint: bool = False
    open_world_hint: bool = False


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Metadata for one MCP tool."""

    name: str
    title: str
    description: str
    input_schema: dict[str, object]
    annotations: ToolAnnotations
    service: ServiceSpec

    def summary(self) -> dict[str, object]:
        """Return a JSON-serializable summary."""

        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "read_only": self.annotations.read_only_hint,
            "long_running": self.service.long_running,
        }


def resolve_tool_annotations(
    spec: ServiceSpec, *, open_world_names: frozenset[str] = frozenset()
) -> ToolAnnotations:
    """Derive annotation hints from a service spec."""

    return ToolAnnotations(
        read_only_hint=spec.read_only,
        destructive_hint=spec.destructive,
        idempotent_hint=spec.idempotent if spec.idempotent is not None else spec.read_only,
        open_world_hint=spec.long_running or spec.name in open_world_names,
    )


def normalize_input_schema(input_schema: dict[str, object]) -> dict[str, object]:
    """Ensure ``required`` exists and advertise ``workspace_root`` on path-taking tools."""

    schema = dict(input_schema)
    existing = schema.get("properties", {})
    properties: dict[str, object] = dict(existing) if isinstance(existing, dict) else {}
    path_like = any(
        name.endswith(("_path", "_dir", "_file", "_root")) or name in {"path", "dir", "file"}
        for name in properties
    )
    if path_like and "workspace_root" not in properties:
        properties["workspace_root"] = dict(_WORKSPACE_PROPERTY)
    schema["properties"] = properties
    schema.setdefault("required", [])
    return schema


def build_tool_registry(
    specs: tuple[ServiceSpec, ...],
    *,
    open_world_names: frozenset[str] = frozenset(),
) -> tuple[ToolDefinition, ...]:
    """Build tool definitions. Specs without a schema are rejected."""

    tools: list[ToolDefinition] = []
    for spec in specs:
        if spec.input_schema is None:
            raise KeyError(f"Missing MCP input_schema for service {spec.name!r}.")
        tools.append(
            ToolDefinition(
                name=spec.name,
                title=spec.title,
                description=spec.description or spec.summary,
                input_schema=normalize_input_schema(dict(spec.input_schema)),
                annotations=resolve_tool_annotations(spec, open_world_names=open_world_names),
                service=spec,
            )
        )
    return tuple(tools)


def implemented_tools(tools: tuple[ToolDefinition, ...]) -> tuple[ToolDefinition, ...]:
    """Return tools whose service phase is implemented."""

    return tuple(tool for tool in tools if tool.service.phase == "implemented")
