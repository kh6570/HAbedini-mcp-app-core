# In the name of God, the Most Gracious, the Most Merciful
"""PNG tool results for plots and schematic renders."""

from __future__ import annotations

import base64
from dataclasses import dataclass

from mcp_app_core.errors import ValidationError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IMAGE_MEDIA_TYPE = "image/png"
IMAGE_SUMMARY_MAX_CHARS = 280


@dataclass(frozen=True, slots=True)
class ImageResult:
    """PNG bytes plus a one-line summary a plot or render tool can return."""

    png: bytes
    summary: str

    def __post_init__(self) -> None:
        if not self.png.startswith(PNG_SIGNATURE):
            raise ValidationError("Image result must be PNG bytes.")
        summary = self.summary.strip()
        if not summary:
            raise ValidationError("Image result needs a short text summary.")
        if any(ord(char) < 32 for char in summary):
            raise ValidationError("Image summary must be a single line of text.")
        if len(summary) > IMAGE_SUMMARY_MAX_CHARS:
            raise ValidationError(
                f"Image summary must be at most {IMAGE_SUMMARY_MAX_CHARS} characters."
            )
        object.__setattr__(self, "summary", summary)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready payload. The PNG is base64."""

        return {
            "summary": self.summary,
            "media_type": IMAGE_MEDIA_TYPE,
            "png_base64": base64.b64encode(self.png).decode("ascii"),
        }
