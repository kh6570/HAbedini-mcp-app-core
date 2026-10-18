# In the name of God, the Most Gracious, the Most Merciful
"""Framework tests. No simulator is required."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from mcp_app_core.app import AppDefinition
from mcp_app_core.budgets import DataBudget, downsample_indices
from mcp_app_core.catalog import ServiceSpec, discover_service_specs
from mcp_app_core.errors import OperationTimeoutError, SandboxViolationError, ValidationError
from mcp_app_core.handlers import call_kwargs, expose_tool_schema, to_json_object
from mcp_app_core.paths import resolve_workspace_path
from mcp_app_core.process import run_command
from mcp_app_core.registry import build_tool_registry
from mcp_app_core.settings import make_settings_class
from sample_services.widgets.make_widget import make_widget


def test_sandbox_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(SandboxViolationError):
        resolve_workspace_path(Path("C:/Windows/notepad.exe"), workspace_root=tmp_path)


def test_budget_rejects_tiny_cap() -> None:
    with pytest.raises(ValidationError):
        DataBudget(max_points=1)
    indexes = downsample_indices(10, 3)
    assert indexes[0] == 0
    assert indexes[-1] == 9
    assert len(indexes) == 3


def test_settings_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    definition = AppDefinition(
        name="demo",
        title="Demo",
        env_prefix="DEMO_",
        default_error_code="demo_error",
        instructions="demo",
        cache_name="demo-app",
        service_packages=(),
    )
    settings_cls = make_settings_class(definition)
    monkeypatch.setenv("DEMO_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("DEMO_TIMEOUT_S", "7")
    loaded = settings_cls().normalized()
    assert loaded.workspace_root == tmp_path.resolve()
    assert loaded.timeout_s == 7
    assert loaded.resolve_timeout_s(0) is None


def test_catalog_and_handler(tmp_path: Path) -> None:
    specs = discover_service_specs(("sample_services.widgets",))
    assert specs[0].name == "make_widget"
    assert specs[0].description == "Make a widget inside the workspace."
    tools = build_tool_registry(specs)
    assert "workspace_root" in tools[0].input_schema["properties"]
    definition = AppDefinition(
        name="demo",
        title="Demo",
        env_prefix="DEMO_",
        default_error_code="demo_error",
        instructions="demo",
        cache_name="demo-app",
        service_packages=("sample_services.widgets",),
        executable_parameter="exe",
    )
    settings = make_settings_class(definition)(workspace_root=tmp_path).normalized()

    def raw(**kwargs: object) -> dict[str, object]:
        return to_json_object(
            make_widget(
                **call_kwargs(
                    make_widget,
                    kwargs,
                    settings=settings,
                    executable_parameter="exe",
                )
            )
        )

    handler = expose_tool_schema(raw, tools[0])
    result = handler(label="bolt")
    assert result["label"] == "bolt"
    assert result["root"] == str(tmp_path.resolve())


def test_subprocess_timeout(tmp_path: Path) -> None:
    with pytest.raises(OperationTimeoutError):
        run_command(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            timeout_s=0.2,
        )


def test_extra_spec_is_enriched() -> None:
    extra = ServiceSpec(name="ping", title="Ping", summary="Ping.", phase="implemented")
    specs = discover_service_specs((), extra_specs=(extra,))
    assert specs[0].name == "ping"
