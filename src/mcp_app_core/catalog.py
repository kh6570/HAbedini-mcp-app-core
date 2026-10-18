# In the name of God, the Most Gracious, the Most Merciful
"""Service metadata and package discovery."""

from __future__ import annotations

from dataclasses import dataclass, replace
from importlib import import_module
from pkgutil import iter_modules
from types import ModuleType
from typing import Literal

ServicePhase = Literal["planned", "implemented"]
_SKIP_MODULES = frozenset({"operations", "mcp_contracts"})


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    """Metadata for one application service."""

    name: str
    title: str
    summary: str
    phase: ServicePhase = "planned"
    read_only: bool = True
    long_running: bool = False
    destructive: bool = False
    idempotent: bool | None = None
    description: str | None = None
    input_schema: dict[str, object] | None = None


def load_contracts(package_name: str) -> dict[str, dict[str, object]]:
    """Return MCP_CONTRACTS from ``package_name.mcp_contracts``."""

    try:
        module = import_module(f"{package_name}.mcp_contracts")
    except ModuleNotFoundError:
        return {}
    contracts = getattr(module, "MCP_CONTRACTS", None)
    if not isinstance(contracts, dict):
        return {}
    return {str(key): value for key, value in contracts.items() if isinstance(value, dict)}


def enrich_spec(spec: ServiceSpec, contract: dict[str, object] | None) -> ServiceSpec:
    """Copy title, description, and input schema from a contract row."""

    if contract is None:
        return spec
    input_schema = contract.get("input_schema")
    return replace(
        spec,
        title=str(contract.get("title", spec.title)),
        description=str(contract.get("description", spec.summary)),
        input_schema=dict(input_schema) if isinstance(input_schema, dict) else spec.input_schema,
    )


def discover_package_specs(package_name: str) -> tuple[ServiceSpec, ...]:
    """Return service specs declared as modules of one package."""

    package = import_module(package_name)
    package_path = getattr(package, "__path__", None)
    if package_path is None:
        raise TypeError(f"{package_name} is not a package.")
    contracts = load_contracts(package_name)
    specs: list[ServiceSpec] = []
    for module_info in sorted(iter_modules(package_path), key=lambda entry: entry.name):
        if module_info.name.startswith("_") or module_info.name in _SKIP_MODULES:
            continue
        module = import_module(f"{package.__name__}.{module_info.name}")
        service_spec = getattr(module, "SERVICE_SPEC", None)
        if not isinstance(service_spec, ServiceSpec):
            continue
        specs.append(enrich_spec(service_spec, contracts.get(service_spec.name)))
    return tuple(specs)


def discover_service_specs(
    package_names: tuple[str, ...] | list[str],
    *,
    extra_contract_modules: tuple[str, ...] = (),
    extra_specs: tuple[ServiceSpec, ...] = (),
) -> tuple[ServiceSpec, ...]:
    """Discover specs across packages, then apply extra contracts and specs."""

    contracts: dict[str, dict[str, object]] = {}
    for module_name in extra_contract_modules:
        module = import_module(module_name)
        raw = getattr(module, "MCP_CONTRACTS", None)
        if isinstance(raw, dict):
            rows = {str(key): value for key, value in raw.items() if isinstance(value, dict)}
            contracts.update(rows)
    catalog: list[ServiceSpec] = [
        enrich_spec(spec, contracts.get(spec.name)) for spec in extra_specs
    ]
    for package_name in package_names:
        for spec in discover_package_specs(package_name):
            catalog.append(enrich_spec(spec, contracts.get(spec.name)))
    return tuple(catalog)


def resolve_service_module(package_names: tuple[str, ...], service_name: str) -> ModuleType:
    """Import the module whose name matches one tool."""

    for package_name in package_names:
        package = import_module(package_name)
        package_path = getattr(package, "__path__", None)
        if package_path is None:
            continue
        for module_info in iter_modules(package_path):
            if module_info.name == service_name:
                return import_module(f"{package.__name__}.{module_info.name}")
    raise KeyError(f"No service module registered for tool {service_name!r}.")
