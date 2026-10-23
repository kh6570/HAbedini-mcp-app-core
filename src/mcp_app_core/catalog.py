# In the name of God, the Most Gracious, the Most Merciful
"""Service metadata and package discovery."""

from __future__ import annotations

from dataclasses import dataclass, replace
from importlib import import_module
from pkgutil import iter_modules
from types import ModuleType
from typing import Literal

ServicePhase = Literal["planned", "implemented"]
ServiceProfile = Literal["default", "extended"]
SERVICE_PROFILES: tuple[ServiceProfile, ...] = ("default", "extended")
# Remote simulation, batch runs, live GUI, and topology ingest.
EXTENDED_PROFILE_AREAS = frozenset({"remote", "batch", "live_gui", "topology_ingest"})
_SKIP_MODULES = frozenset({"operations", "mcp_contracts"})


def profile_for_area(area: str) -> ServiceProfile:
    """Return the profile for one capability area.

    ``remote``, ``batch``, ``live_gui``, and ``topology_ingest`` are extended.
    Typed edit, simulate, and measure areas stay on the default profile.
    """

    if area in EXTENDED_PROFILE_AREAS:
        return "extended"
    return "default"


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    """Metadata for one application service.

    ``profile`` selects the tool group a server loads. ``output_schema`` is
    optional metadata and does not by itself turn on structured tool output.
    """

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
    profile: ServiceProfile = "default"
    output_schema: dict[str, object] | None = None

    def __post_init__(self) -> None:
        raw_profile: object = self.profile
        if raw_profile not in {"default", "extended"}:
            raise ValueError(f"Unknown service profile {raw_profile!r}.")
        if self.output_schema is not None:
            object.__setattr__(self, "output_schema", dict(self.output_schema))


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


def _profile_from_contract(spec: ServiceSpec, contract: dict[str, object]) -> ServiceProfile:
    if "profile" not in contract:
        return spec.profile
    raw = contract["profile"]
    if raw == "default":
        return "default"
    if raw == "extended":
        return "extended"
    raise ValueError(f"Unknown service profile {raw!r} for {spec.name!r}.")


def _output_schema_from_contract(
    spec: ServiceSpec, contract: dict[str, object]
) -> dict[str, object] | None:
    if "output_schema" not in contract:
        return spec.output_schema
    raw = contract["output_schema"]
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise TypeError(f"output_schema for {spec.name!r} must be a dictionary.")
    return {str(key): value for key, value in raw.items()}


def enrich_spec(spec: ServiceSpec, contract: dict[str, object] | None) -> ServiceSpec:
    """Copy title, description, schemas, and profile from a contract row."""

    if contract is None:
        return spec
    input_schema = contract.get("input_schema")
    return replace(
        spec,
        title=str(contract.get("title", spec.title)),
        description=str(contract.get("description", spec.summary)),
        input_schema=dict(input_schema) if isinstance(input_schema, dict) else spec.input_schema,
        output_schema=_output_schema_from_contract(spec, contract),
        profile=_profile_from_contract(spec, contract),
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
