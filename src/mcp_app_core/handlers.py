# In the name of God, the Most Gracious, the Most Merciful
"""Generic handler binding and JSON schema signatures."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from mcp_app_core.errors import AppError
from mcp_app_core.registry import ToolDefinition

ToolHandler = Callable[..., dict[str, object]]


class HasWorkspace(Protocol):
    """Settings object that carries a workspace root and an optional executable."""

    workspace_root: Path
    exe: Path | None

    def model_copy(self, *, update: dict[str, object]) -> HasWorkspace:
        """Return a copy with updated fields."""

    def normalized(self) -> HasWorkspace:
        """Return a path-normalized copy."""


def expose_tool_schema(handler: ToolHandler, tool: ToolDefinition) -> ToolHandler:
    """Give a handler the keyword signature advertised by its JSON schema."""

    schema = tool.input_schema
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    required = schema.get("required", [])
    required_names = {str(item) for item in required} if isinstance(required, list) else set()
    parameters = [
        inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty if name in required_names else None,
            annotation=object,
        )
        for name in properties
    ]
    signature = inspect.Signature(parameters, return_annotation=dict[str, object])

    def schema_handler(**kwargs: object) -> dict[str, object]:
        provided = {name: value for name, value in kwargs.items() if value is not None}
        return handler(**provided)

    schema_handler.__name__ = tool.name
    schema_handler.__doc__ = tool.description
    schema_handler.__signature__ = signature  # type: ignore[attr-defined]
    schema_handler.__annotations__ = {parameter.name: object for parameter in parameters}
    schema_handler.__annotations__["return"] = dict[str, object]
    return schema_handler


def _jsonify(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(item) for item in value]
    if isinstance(value, float | int | str | bool) or value is None:
        return value
    return str(value)


def to_json_object(value: object) -> dict[str, object]:
    """Require a mapping and coerce nested values into JSON types."""

    if not isinstance(value, dict):
        raise TypeError("Tool handlers must return a dictionary.")
    return {str(key): _jsonify(item) for key, item in value.items()}


def call_kwargs(
    service_fn: Callable[..., object],
    tool_kwargs: dict[str, object],
    *,
    settings: HasWorkspace,
    executable_parameter: str,
) -> dict[str, object]:
    """Inject workspace, settings, and the executable when the service asks for them."""

    prepared = dict(tool_kwargs)
    override = prepared.pop("workspace_root", None)
    effective = settings
    if override not in (None, ""):
        effective = settings.model_copy(update={"workspace_root": Path(str(override))}).normalized()
    bound: dict[str, object] = {}
    for name, parameter in inspect.signature(service_fn).parameters.items():
        if name == "workspace_root":
            bound[name] = effective.workspace_root
        elif name == "settings":
            bound[name] = effective
        elif name == executable_parameter:
            bound[name] = effective.exe
        elif name in prepared:
            bound[name] = prepared[name]
        elif parameter.default is inspect.Parameter.empty:
            raise TypeError(f"Missing required tool argument {name!r}.")
    return bound


def error_payload(error: AppError) -> dict[str, object]:
    """Return the structured fields placed on an MCP error."""

    payload: dict[str, object] = {
        "error_code": error.error_code,
        "error_type": type(error).__name__,
    }
    line = getattr(error, "line", None)
    column = getattr(error, "column", None)
    exit_code = getattr(error, "exit_code", None)
    stderr = getattr(error, "stderr", None)
    if isinstance(line, int):
        payload["line"] = line
    if isinstance(column, int):
        payload["column"] = column
    if isinstance(exit_code, int):
        payload["exit_code"] = exit_code
    if isinstance(stderr, str):
        payload["stderr"] = stderr
    return payload
