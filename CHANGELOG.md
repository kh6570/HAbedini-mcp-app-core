In the name of God, the Most Gracious, the Most Merciful

# Changelog

## Unreleased

- A Linux zombie is not a running process. The orphan watchdog stops waiting once the parent has exited, even when that parent has not been reaped yet.

## 0.1.0

- First release of the shared MCP server framework: catalog, tool registry, workspace sandbox, data budget, error codes, settings base, and process helpers.
- No simulator-specific code. QSpice MCP and LTspice MCP depend on this package.
