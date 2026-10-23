# In the name of God, the Most Gracious, the Most Merciful
"""PNG image results."""

from __future__ import annotations

import base64

import pytest

from mcp_app_core.errors import ValidationError
from mcp_app_core.images import (
    IMAGE_MEDIA_TYPE,
    IMAGE_SUMMARY_MAX_CHARS,
    PNG_SIGNATURE,
    ImageResult,
)


def test_image_result_carries_png_bytes_and_a_summary() -> None:
    png = PNG_SIGNATURE + b"IHDR"
    image = ImageResult(png=png, summary="  Carrier stays inside the envelope.  ")
    assert image.summary == "Carrier stays inside the envelope."
    payload = image.as_dict()
    assert payload["media_type"] == IMAGE_MEDIA_TYPE
    assert payload["summary"] == image.summary
    encoded = payload["png_base64"]
    assert isinstance(encoded, str)
    assert base64.b64decode(encoded) == png


def test_image_result_rejects_a_non_png_and_a_long_summary() -> None:
    with pytest.raises(ValidationError, match="PNG"):
        ImageResult(png=b"\xff\xd8\xff", summary="A plot.")
    with pytest.raises(ValidationError, match="summary"):
        ImageResult(png=PNG_SIGNATURE, summary="   ")
    with pytest.raises(ValidationError, match="single line"):
        ImageResult(png=PNG_SIGNATURE, summary="two\nlines")
    with pytest.raises(ValidationError, match=str(IMAGE_SUMMARY_MAX_CHARS)):
        ImageResult(png=PNG_SIGNATURE, summary="x" * (IMAGE_SUMMARY_MAX_CHARS + 1))
    image = ImageResult(png=PNG_SIGNATURE, summary="x" * IMAGE_SUMMARY_MAX_CHARS)
    assert len(image.summary) == IMAGE_SUMMARY_MAX_CHARS
