# In the name of God, the Most Gracious, the Most Merciful
"""Profile filter and optional output schema."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mcp_app_core.catalog import (
    ServiceSpec,
    discover_service_specs,
    enrich_spec,
    profile_for_area,
)
from mcp_app_core.registry import build_tool_registry
from mcp_app_core.server import register_tools


def _spec(
    name: str,
    *,
    profile: str = "default",
    input_schema: dict[str, object] | None = None,
    output_schema: dict[str, object] | None = None,
) -> ServiceSpec:
    schema = {"type": "object", "properties": {}} if input_schema is None else input_schema
    return ServiceSpec(
        name=name,
        title=name,
        summary=name,
        phase="implemented",
        input_schema=schema,
        profile=profile,  # type: ignore[arg-type]
        output_schema=output_schema,
    )


def test_discovered_spec_stays_on_the_default_profile() -> None:
    specs = discover_service_specs(("sample_services.widgets",))
    assert specs[0].profile == "default"
    assert specs[0].output_schema is None


def test_omitted_profile_filter_keeps_extended_specs() -> None:
    extended = _spec("submit_batch", profile="extended")
    default = _spec("measure_waveform")
    tools = build_tool_registry((extended, default))
    assert [tool.name for tool in tools] == ["submit_batch", "measure_waveform"]
    assert tools[0].summary()["profile"] == "extended"


def test_active_profiles_keep_the_requested_subset() -> None:
    extended = _spec("submit_batch", profile="extended")
    default = _spec("measure_waveform")
    specs = (extended, default)
    assert [tool.name for tool in build_tool_registry(specs, active_profiles={"default"})] == [
        "measure_waveform"
    ]
    assert [tool.name for tool in build_tool_registry(specs, active_profiles=["extended"])] == [
        "submit_batch"
    ]
    both = build_tool_registry(specs, active_profiles=("default", "extended"))
    assert [tool.name for tool in both] == ["submit_batch", "measure_waveform"]
    assert build_tool_registry(specs, active_profiles=frozenset()) == ()


def test_hidden_profile_does_not_require_an_input_schema() -> None:
    hidden = ServiceSpec(
        name="submit_remote_simulation",
        title="Remote",
        summary="Remote.",
        profile="extended",
    )
    visible = _spec("measure_waveform")
    tools = build_tool_registry((hidden, visible), active_profiles={"default"})
    assert [tool.name for tool in tools] == ["measure_waveform"]
    with pytest.raises(KeyError, match="submit_remote_simulation"):
        build_tool_registry((hidden, visible))


def test_unknown_active_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="gui"):
        build_tool_registry((), active_profiles={"gui"})
    with pytest.raises(TypeError):
        build_tool_registry((), active_profiles="default")  # type: ignore[arg-type]


def test_contract_sets_profile_and_output_schema() -> None:
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    enriched = enrich_spec(
        ServiceSpec(name="check_schematic", title="Check", summary="Check."),
        {"profile": "extended", "output_schema": schema},
    )
    assert enriched.profile == "extended"
    assert enriched.output_schema == schema
    schema["type"] = "array"
    assert enriched.output_schema == {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def test_unknown_contract_profile_is_rejected() -> None:
    spec = ServiceSpec(name="ping", title="Ping", summary="Ping.")
    with pytest.raises(ValueError, match="admin"):
        enrich_spec(spec, {"profile": "admin"})
    with pytest.raises(TypeError, match="output_schema"):
        enrich_spec(spec, {"output_schema": ["nope"]})


def test_service_spec_rejects_an_unknown_profile() -> None:
    with pytest.raises(ValueError, match="admin"):
        ServiceSpec(name="ping", title="Ping", summary="Ping.", profile="admin")  # type: ignore[arg-type]


@pytest.mark.parametrize("area", ["remote", "batch", "live_gui", "topology_ingest"])
def test_extended_areas(area: str) -> None:
    assert profile_for_area(area) == "extended"


@pytest.mark.parametrize("area", ["schematic", "simulation", "waveform", "topology"])
def test_other_areas_stay_on_the_default_profile(area: str) -> None:
    assert profile_for_area(area) == "default"


class _Registered:
    def __init__(self) -> None:
        self.parameters: dict[str, object] | None = None


class _Manager:
    def __init__(self) -> None:
        self.registered = _Registered()

    def get_tool(self, name: str) -> _Registered:
        assert name == "check_schematic"
        return self.registered


class _FakeApp:
    def __init__(self) -> None:
        self._tool_manager = _Manager()
        self.calls: list[dict[str, object]] = []

    def tool(
        self, **kwargs: object
    ) -> Callable[[Callable[..., dict[str, object]]], Callable[..., dict[str, object]]]:
        self.calls.append(kwargs)

        def decorate(
            fn: Callable[..., dict[str, object]],
        ) -> Callable[..., dict[str, object]]:
            return fn

        return decorate


def test_output_schema_does_not_enable_structured_output() -> None:
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    spec = _spec(
        "check_schematic",
        input_schema={
            "type": "object",
            "properties": {"schematic_path": {"type": "string"}},
            "required": ["schematic_path"],
        },
        output_schema=schema,
    )
    tool = build_tool_registry((spec,))[0]
    assert tool.output_schema == schema
    schema["type"] = "array"
    assert tool.output_schema is not None
    assert tool.output_schema["type"] == "object"
    app = _FakeApp()

    def handler(**_kwargs: object) -> dict[str, object]:
        return {"ok": True}

    register_tools(app, (tool,), lambda _name: handler)  # type: ignore[arg-type]
    assert app.calls[0]["structured_output"] is False
    parameters = app._tool_manager.registered.parameters
    assert isinstance(parameters, dict)
    properties = parameters["properties"]
    assert isinstance(properties, dict)
    assert "workspace_root" in properties
