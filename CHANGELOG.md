In the name of God, the Most Gracious, the Most Merciful

# Changelog

## Unreleased

- Service specs carry a `default` or `extended` profile. `build_tool_registry` can keep one profile, and omitting that filter still returns every spec.
- Check findings carry a `fixable` hint, and a check result can carry an optional output schema. Tool registration still leaves structured output off.
- `content_sha256` and `commit_file` hash one file and replace it through a temporary file only when the hash still matches.
- `minmax` downsampling keeps each bucket's minimum and maximum. `lttb` and `decimate` keep even spacing.
- `ImageResult` carries PNG bytes and a short text summary.
- `redact_paths` strips workspace, executable, and schematic paths from text before it is logged or traced.
- A skill manifest records a name, a trigger, when not to use the skill, and reference filenames. Loading a skill reads the short body only; a reference file is read only when its name is listed.
- A Linux zombie is not a running process. The orphan watchdog stops waiting once the parent has exited, even when that parent has not been reaped yet.

## 0.1.0

- First release of the shared MCP server framework: catalog, tool registry, workspace sandbox, data budget, error codes, settings base, and process helpers.
- No simulator-specific code. QSpice MCP and LTspice MCP depend on this package.
