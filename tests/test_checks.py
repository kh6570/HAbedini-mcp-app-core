# In the name of God, the Most Gracious, the Most Merciful
"""Check result schema and fixable hint."""

from __future__ import annotations

import pytest

from mcp_app_core.checks import CheckFinding, CheckResult
from mcp_app_core.errors import ValidationError


def test_finding_defaults_to_not_fixable() -> None:
    finding = CheckFinding(severity="warning", code="floating_net", message="Net is floating.")
    assert finding.fixable is False
    assert finding.as_dict() == {
        "severity": "warning",
        "code": "floating_net",
        "message": "Net is floating.",
        "fixable": False,
    }


def test_result_carries_fixable_location_and_optional_schema() -> None:
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    finding = CheckFinding(
        severity="error",
        code="unconnected_pin",
        message="Pin is open.",
        fixable=True,
        location="R1",
    )
    result = CheckResult(findings=(finding,), output_schema=schema)
    payload = result.as_dict()
    assert result.ok is False
    assert payload["error_count"] == 1
    assert payload["warning_count"] == 0
    assert payload["findings"] == [
        {
            "severity": "error",
            "code": "unconnected_pin",
            "message": "Pin is open.",
            "fixable": True,
            "location": "R1",
        }
    ]
    assert payload["output_schema"] == schema
    schema["type"] = "array"
    assert result.output_schema == {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def test_schema_is_omitted_when_unset() -> None:
    result = CheckResult(
        findings=(CheckFinding(severity="info", code="note", message="Looks fine.", location="  "),)
    )
    assert result.ok is True
    assert result.info_count == 1
    payload = result.as_dict()
    assert "output_schema" not in payload
    assert "location" not in payload["findings"][0]  # type: ignore[index]


def test_invalid_finding_is_rejected() -> None:
    with pytest.raises(ValidationError, match="severity"):
        CheckFinding(severity="fatal", code="x", message="y")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="fixable"):
        CheckFinding(severity="error", code="x", message="y", fixable="yes")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="code"):
        CheckFinding(severity="error", code="  ", message="y")
    with pytest.raises(TypeError, match="CheckFinding"):
        CheckResult(findings=("nope",))  # type: ignore[arg-type]
