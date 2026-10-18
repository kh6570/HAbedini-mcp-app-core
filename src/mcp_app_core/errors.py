# In the name of God, the Most Gracious, the Most Merciful
"""Domain errors and the stable MCP error-code list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ErrorCodeStatus = Literal["implemented", "reserved"]
DEFAULT_ERROR_CODE = "app_error"


@dataclass(frozen=True, slots=True)
class ErrorCodeDefinition:
    """One published error code."""

    code: str
    title: str
    summary: str
    status: ErrorCodeStatus
    mapped_exceptions: tuple[str, ...] = ()

    def summary_dict(self) -> dict[str, object]:
        """Return a JSON-serializable summary."""

        return {
            "code": self.code,
            "title": self.title,
            "summary": self.summary,
            "status": self.status,
            "mapped_exceptions": list(self.mapped_exceptions),
        }


class AppError(Exception):
    """Base error for every server built on this framework."""

    default_error_code = DEFAULT_ERROR_CODE

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code or self.default_error_code


class BackendUnavailableError(AppError):
    """A required local executable or backend is missing."""

    default_error_code = "backend_unavailable"


class ArtifactMissingError(AppError):
    """An expected file was not created or could not be found."""

    default_error_code = "artifact_missing"


class ParseError(AppError):
    """A text or binary artifact could not be parsed."""

    default_error_code = "parse_failed"

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code)
        self.line = line
        self.column = column


class BudgetExceededError(AppError):
    """A data budget could not be satisfied."""

    default_error_code = "budget_exceeded"


class SandboxViolationError(AppError):
    """A path escaped the workspace root."""

    default_error_code = "sandbox_violation"


class ValidationError(AppError, ValueError):
    """Caller input failed a precondition."""

    default_error_code = "validation_failed"


class ConfigurationError(AppError):
    """Runtime configuration is missing or invalid."""

    default_error_code = "configuration_invalid"


class OperationTimeoutError(AppError):
    """An operation exceeded its timeout."""

    default_error_code = "timeout_exceeded"


class UnsupportedError(AppError):
    """The operation has no equivalent in this server."""

    default_error_code = "unsupported"


class BatchConflictError(AppError):
    """A persisted batch action conflicts with existing state."""

    default_error_code = "batch_conflict"


class UnsupportedManifestVersionError(ValidationError):
    """A saved manifest uses a schema this server cannot load."""

    default_error_code = "unsupported_manifest_version"


SHARED_ERROR_CODES: tuple[ErrorCodeDefinition, ...] = (
    ErrorCodeDefinition(
        code="backend_unavailable",
        title="Backend Unavailable",
        summary="A required local executable or backend is missing.",
        status="implemented",
        mapped_exceptions=("BackendUnavailableError",),
    ),
    ErrorCodeDefinition(
        code="artifact_missing",
        title="Artifact Missing",
        summary="An expected file was not created or could not be found.",
        status="implemented",
        mapped_exceptions=("ArtifactMissingError",),
    ),
    ErrorCodeDefinition(
        code="parse_failed",
        title="Parse Failed",
        summary="An artifact could not be parsed.",
        status="implemented",
        mapped_exceptions=("ParseError",),
    ),
    ErrorCodeDefinition(
        code="budget_exceeded",
        title="Budget Exceeded",
        summary="A data budget could not be satisfied.",
        status="implemented",
        mapped_exceptions=("BudgetExceededError",),
    ),
    ErrorCodeDefinition(
        code="sandbox_violation",
        title="Sandbox Violation",
        summary="A path escaped the workspace root.",
        status="implemented",
        mapped_exceptions=("SandboxViolationError",),
    ),
    ErrorCodeDefinition(
        code="validation_failed",
        title="Validation Failed",
        summary="Caller input failed a precondition.",
        status="implemented",
        mapped_exceptions=("ValidationError",),
    ),
    ErrorCodeDefinition(
        code="configuration_invalid",
        title="Configuration Invalid",
        summary="Runtime configuration is missing or invalid.",
        status="implemented",
        mapped_exceptions=("ConfigurationError",),
    ),
    ErrorCodeDefinition(
        code="timeout_exceeded",
        title="Timeout Exceeded",
        summary="An operation exceeded its timeout.",
        status="implemented",
        mapped_exceptions=("OperationTimeoutError",),
    ),
    ErrorCodeDefinition(
        code="unsupported",
        title="Unsupported",
        summary="The operation has no equivalent in this server.",
        status="implemented",
        mapped_exceptions=("UnsupportedError",),
    ),
    ErrorCodeDefinition(
        code="batch_conflict",
        title="Batch Conflict",
        summary="A persisted batch action conflicts with existing state.",
        status="implemented",
        mapped_exceptions=("BatchConflictError",),
    ),
    ErrorCodeDefinition(
        code="unsupported_manifest_version",
        title="Unsupported Manifest Version",
        summary="A saved manifest uses a schema this server cannot load.",
        status="implemented",
        mapped_exceptions=("UnsupportedManifestVersionError",),
    ),
)


def describe_error_codes(
    codes: tuple[ErrorCodeDefinition, ...],
    *,
    default_code: str,
    document_path: str = "docs/errors.md",
) -> dict[str, object]:
    """Return a JSON-serializable error catalog."""

    return {
        "document_path": document_path,
        "default_code": default_code,
        "codes": [item.summary_dict() for item in codes],
    }
