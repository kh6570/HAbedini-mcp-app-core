# In the name of God, the Most Gracious, the Most Merciful
"""FastMCP registration helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.types import ErrorData
from mcp.types import ToolAnnotations as MCPToolAnnotations

from mcp_app_core.errors import AppError
from mcp_app_core.handlers import error_payload
from mcp_app_core.registry import ToolAnnotations, ToolDefinition

ToolHandler = Callable[..., dict[str, object]]


@dataclass(frozen=True, slots=True)
class StaticResource:
    """One static MCP resource."""

    uri: str
    name: str
    description: str
    body: str
    mime_type: str = "text/plain"


@dataclass(frozen=True, slots=True)
class StaticPrompt:
    """One static MCP prompt."""

    name: str
    description: str
    body: str


def to_error_data(error: AppError) -> ErrorData:
    """Convert a domain error into MCP error data."""

    return ErrorData(code=0, message=str(error), data=error_payload(error))


def _annotations(annotations: ToolAnnotations) -> MCPToolAnnotations:
    return MCPToolAnnotations(
        readOnlyHint=annotations.read_only_hint,
        destructiveHint=annotations.destructive_hint,
        idempotentHint=annotations.idempotent_hint,
        openWorldHint=annotations.open_world_hint,
    )


def register_tools(
    app: FastMCP,
    tools: tuple[ToolDefinition, ...],
    handler_for: Callable[[str], ToolHandler],
) -> None:
    """Register implemented tools and stamp their JSON schemas."""

    for tool in tools:
        app.tool(
            name=tool.name,
            title=tool.title,
            description=tool.description,
            annotations=_annotations(tool.annotations),
            structured_output=False,
        )(handler_for(tool.name))
        registered = app._tool_manager.get_tool(tool.name)
        if registered is not None:
            registered.parameters = dict(tool.input_schema)


def register_resources(app: FastMCP, resources: tuple[StaticResource, ...]) -> None:
    """Register static text resources."""

    def make_resource(body: str) -> Callable[[], str]:
        def resource() -> str:
            return body

        return resource

    for resource in resources:
        app.resource(
            resource.uri,
            name=resource.name,
            title=resource.name,
            description=resource.description,
            mime_type=resource.mime_type,
        )(make_resource(resource.body))


def register_prompts(app: FastMCP, prompts: tuple[StaticPrompt, ...]) -> None:
    """Register static prompts."""

    def make_prompt(body: str) -> Callable[[], str]:
        def prompt() -> str:
            return body

        return prompt

    for prompt in prompts:
        app.prompt(prompt.name, description=prompt.description)(make_prompt(prompt.body))
