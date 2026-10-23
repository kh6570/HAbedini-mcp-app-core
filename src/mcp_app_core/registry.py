# In the name of God, the Most Gracious, the Most Merciful
"""Tool definitions derived from service specs."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from mcp_app_core.catalog import SERVICE_PROFILES, ServiceSpec

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
    output_schema: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.output_schema is not None:
            object.__setattr__(self, "output_schema", dict(self.output_schema))

    def summary(self) -> dict[str, object]:
        """Return a JSON-serializable summary."""

        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "read_only": self.annotations.read_only_hint,
            "long_running": self.service.long_running,
            "profile": self.service.profile,
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


def _active_profiles(active_profiles: Collection[str] | None) -> frozenset[str] | None:
    if active_profiles is None:
        return None
    if isinstance(active_profiles, str):
        raise TypeError("active_profiles must be a collection of profile names.")
    allowed = frozenset(active_profiles)
    unknown = sorted(allowed.difference(SERVICE_PROFILES))
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(f"Unknown service profile(s): {names}.")
    return allowed


def build_tool_registry(
    specs: tuple[ServiceSpec, ...],
    *,
    open_world_names: frozenset[str] = frozenset(),
    active_profiles: Collection[str] | None = None,
) -> tuple[ToolDefinition, ...]:
    """Build tool definitions. Specs without a schema are rejected.

    Omit ``active_profiles`` to include every spec. Pass a collection of
    ``default`` and ``extended`` to load that subset. A spec outside the
    active set is skipped before its input schema is required.
    """

    allowed = _active_profiles(active_profiles)
    tools: list[ToolDefinition] = []
    for spec in specs:
        if allowed is not None and spec.profile not in allowed:
            continue
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
                output_schema=spec.output_schema,
            )
        )
    return tuple(tools)


def implemented_tools(tools: tuple[ToolDefinition, ...]) -> tuple[ToolDefinition, ...]:
    """Return tools whose service phase is implemented."""

    return tuple(tool for tool in tools if tool.service.phase == "implemented")
