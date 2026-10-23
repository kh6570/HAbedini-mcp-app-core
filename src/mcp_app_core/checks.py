# In the name of God, the Most Gracious, the Most Merciful
"""Check findings a later schematic or netlist tool can return."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mcp_app_core.errors import ValidationError

CheckSeverity = Literal["error", "warning", "info"]
_SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True, slots=True)
class CheckFinding:
    """One check observation.

    ``fixable`` tells a later edit whether this finding is one it can repair.
    ``location`` is an optional schematic or netlist place, such as a reference
    designator or line number.
    """

    severity: CheckSeverity
    code: str
    message: str
    fixable: bool = False
    location: str | None = None

    def __post_init__(self) -> None:
        raw_severity: object = self.severity
        if raw_severity not in _SEVERITIES:
            raise ValidationError(f"Unknown check severity {raw_severity!r}.")
        if not isinstance(self.fixable, bool):
            raise ValidationError("fixable must be a boolean.")
        code = self.code.strip()
        message = self.message.strip()
        if not code:
            raise ValidationError("Check finding code must not be empty.")
        if not message:
            raise ValidationError("Check finding message must not be empty.")
        location = self.location.strip() if self.location is not None else ""
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "location", location or None)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable finding."""

        payload: dict[str, object] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "fixable": self.fixable,
        }
        if self.location is not None:
            payload["location"] = self.location
        return payload


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Findings for one check, plus an optional output schema.

    The schema describes this payload when a tool wants to publish one. It does
    not turn structured MCP output on by itself.
    """

    findings: tuple[CheckFinding, ...] = ()
    output_schema: dict[str, object] | None = None

    def __post_init__(self) -> None:
        findings: list[CheckFinding] = []
        for finding in self.findings:
            if not isinstance(finding, CheckFinding):
                raise TypeError("Check results contain CheckFinding values.")
            findings.append(finding)
        object.__setattr__(self, "findings", tuple(findings))
        if self.output_schema is None:
            return
        if not isinstance(self.output_schema, dict):
            raise TypeError("output_schema must be a dictionary.")
        copied = {str(key): value for key, value in self.output_schema.items()}
        object.__setattr__(self, "output_schema", copied)

    @property
    def error_count(self) -> int:
        """Return the number of error findings."""

        return sum(1 for finding in self.findings if finding.severity == "error")

    @property
    def warning_count(self) -> int:
        """Return the number of warning findings."""

        return sum(1 for finding in self.findings if finding.severity == "warning")

    @property
    def info_count(self) -> int:
        """Return the number of info findings."""

        return sum(1 for finding in self.findings if finding.severity == "info")

    @property
    def ok(self) -> bool:
        """Return True when the result has no error findings."""

        return self.error_count == 0

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable result. The schema is omitted when unset."""

        payload: dict[str, object] = {
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "findings": [finding.as_dict() for finding in self.findings],
        }
        if self.output_schema is not None:
            payload["output_schema"] = dict(self.output_schema)
        return payload
