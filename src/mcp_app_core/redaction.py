# In the name of God, the Most Gracious, the Most Merciful
"""Redact workspace, executable, and schematic paths before logs or traces.

Servers call these helpers with the paths they already know. Nothing here
opens a network connection or enables telemetry.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

_BEFORE = frozenset(" \t\r\n\"'`=,;()[]{}<>|")
_AFTER = frozenset(" \t\r\n\"'`=,;()[]{}<>|\\/.")
_MIN_NEEDLE = 3


@dataclass(frozen=True, slots=True)
class _Needle:
    text: str
    replacement: str
    rank: int


def _trim_trailing_separator(item: str) -> str:
    trimmed = item.rstrip("\\/")
    if len(trimmed) == 2 and trimmed[1] == ":":
        return item
    return trimmed or item


def _variants(raw: Path | str, *, directory: bool) -> tuple[str, ...]:
    text = str(raw).strip().strip('"')
    if len(text) < _MIN_NEEDLE:
        return ()
    path = Path(text)
    forms = {text, str(path)}
    if path.is_absolute():
        with contextlib.suppress(OSError):
            forms.add(str(path.resolve(strict=False)))
    expanded: set[str] = set()
    for form in forms:
        slash_forms = {form, form.replace("\\", "/"), form.replace("/", "\\")}
        for item in slash_forms:
            if len(item) < _MIN_NEEDLE:
                continue
            expanded.add(item)
            trimmed = _trim_trailing_separator(item)
            if len(trimmed) >= _MIN_NEEDLE:
                expanded.add(trimmed)
            escaped = item.replace("\\", "\\\\")
            if len(escaped) >= _MIN_NEEDLE:
                expanded.add(escaped)
            if directory and not item.endswith(("\\", "/")):
                expanded.add(item + "\\")
                expanded.add(item + "/")
    if not directory:
        name = Path(text).name
        if len(name) >= _MIN_NEEDLE and len(Path(name).suffix) >= 2:
            expanded.add(name)
    return tuple(item for item in expanded if len(item) >= _MIN_NEEDLE)


def _replacement(token: str, needle: str) -> str:
    if needle.endswith("\\"):
        return token + "\\"
    if needle.endswith("/"):
        return token + "/"
    return token


def _collect(
    needles: list[_Needle],
    raw: Path | str,
    token: str,
    *,
    rank: int,
    directory: bool,
) -> None:
    for variant in _variants(raw, directory=directory):
        needles.append(_Needle(variant, _replacement(token, variant), rank))


def _find_case_insensitive(text: str, needle: str, start: int) -> int:
    folded = needle.casefold()
    limit = len(text) - len(needle)
    for index in range(start, limit + 1):
        if text[index : index + len(needle)].casefold() == folded:
            return index
    return -1


def _boundaries_ok(text: str, start: int, end: int, needle: str) -> bool:
    if start > 0 and text[start - 1] not in _BEFORE:
        return False
    if end >= len(text):
        return True
    if needle.endswith(("\\", "/")):
        return True
    return text[end] in _AFTER


def _replace_bounded(text: str, needle: str, replacement: str) -> str:
    if len(needle) < _MIN_NEEDLE:
        return text
    pieces: list[str] = []
    copy_from = 0
    search_from = 0
    last_start = len(text) - len(needle)
    while search_from <= last_start:
        index = _find_case_insensitive(text, needle, search_from)
        if index < 0:
            break
        end = index + len(needle)
        if _boundaries_ok(text, index, end, needle):
            pieces.append(text[copy_from:index])
            pieces.append(replacement)
            copy_from = end
            search_from = end
            continue
        # A lookalike such as "work" inside "workspace" stays in the text.
        search_from = index + 1
    pieces.append(text[copy_from:])
    return "".join(pieces)


def _apply(text: str, needles: Sequence[_Needle]) -> str:
    best: dict[str, _Needle] = {}
    for needle in needles:
        key = needle.text.casefold()
        current = best.get(key)
        if (
            current is None
            or needle.rank < current.rank
            or (needle.rank == current.rank and len(needle.text) > len(current.text))
        ):
            best[key] = needle
    ordered = sorted(best.values(), key=lambda item: (-len(item.text), item.rank))
    redacted = text
    for needle in ordered:
        redacted = _replace_bounded(redacted, needle.text, needle.replacement)
    return redacted


def redact_paths(
    text: str,
    *,
    workspace_root: Path | str | None = None,
    executable_path: Path | str | None = None,
    schematic_paths: Sequence[Path | str] = (),
) -> str:
    """Replace known paths with stable tokens.

    One schematic path becomes ``<schematic>``. Several become
    ``<schematic:1>`` in the order given. The executable becomes
    ``<executable>`` and the workspace root becomes ``<workspace>``. A
    workspace prefix keeps the relative remainder. The helper does not send
    telemetry.
    """

    if not isinstance(text, str):
        raise TypeError("redact_paths expects a string.")
    needles: list[_Needle] = []
    for index, schematic in enumerate(schematic_paths, start=1):
        token = "<schematic>" if len(schematic_paths) == 1 else f"<schematic:{index}>"
        _collect(needles, schematic, token, rank=0, directory=False)
    if executable_path is not None:
        _collect(needles, executable_path, "<executable>", rank=1, directory=False)
    if workspace_root is not None:
        _collect(needles, workspace_root, "<workspace>", rank=2, directory=True)
    return _apply(text, needles)


def redact_log_value(
    value: object,
    *,
    workspace_root: Path | str | None = None,
    executable_path: Path | str | None = None,
    schematic_paths: Sequence[Path | str] = (),
) -> object:
    """Redact paths inside strings, path objects, mappings, and sequences."""

    def redact_text(text: str) -> str:
        return redact_paths(
            text,
            workspace_root=workspace_root,
            executable_path=executable_path,
            schematic_paths=schematic_paths,
        )

    def redact(item: object) -> object:
        if isinstance(item, str):
            return redact_text(item)
        if isinstance(item, Path):
            return redact_text(str(item))
        if isinstance(item, BaseException):
            return redact_text(f"{type(item).__name__}: {item}")
        if isinstance(item, Mapping):
            redacted: dict[str, object] = {}
            for key, nested in item.items():
                key_text = key if isinstance(key, str) else str(key)
                redacted[redact_text(key_text)] = redact(nested)
            return redacted
        if isinstance(item, tuple):
            return tuple(redact(nested) for nested in item)
        if isinstance(item, list):
            return [redact(nested) for nested in item]
        return item

    return redact(value)


def redact_paths_processor(
    *,
    workspace_root: Path | str | None = None,
    executable_path: Path | str | None = None,
    schematic_paths: Sequence[Path | str] = (),
) -> Callable[[object, str, dict[str, object]], dict[str, object]]:
    """Return a structlog processor that redacts paths and does not emit telemetry.

    Insert it in the server's processor chain before the renderer.
    """

    def processor(
        _logger: object,
        _method: str,
        event_dict: dict[str, object],
    ) -> dict[str, object]:
        redacted = redact_log_value(
            event_dict,
            workspace_root=workspace_root,
            executable_path=executable_path,
            schematic_paths=schematic_paths,
        )
        if isinstance(redacted, dict):
            return redacted
        return event_dict

    return processor
