In the name of God, the Most Gracious, the Most Merciful

# mcp-app-core

Shared framework for local [Model Context Protocol](https://modelcontextprotocol.io) servers. QSpice MCP and LTspice MCP depend on this package. A future server can use the same catalog, sandbox, settings, and error envelope without copying them.

This repository is a library. It does not start an MCP server and it does not know about `.qsch` or `.asc` files.

## What you get

- Service catalog: one Python module per tool, discovered from a package list you pass in
- Tool registry and the handler that injects `workspace_root`, settings, and the simulator executable
- Workspace path checks that reject files outside the configured root
- Data budget (2000 points, 64 KB) for anything returned to the assistant
- `AppError` and the shared error codes (`sandbox_violation`, `validation_failed`, `timeout_exceeded`, and the rest)
- Settings base class with a per-server environment prefix (`QSPICE_`, `LTSPICE_`, or your own)
- Subprocess timeout, Windows process-tree stop, a kill-on-close job object, and an orphan watchdog

## Install for development

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\python.exe -m mypy --strict src\mcp_app_core
```

Python 3.11 or newer. The tests do not need QSpice or LTspice. Your local folder name does not matter.

## How the servers get it

QSpice MCP and LTspice MCP depend on this package with a Git URL:

```text
mcp-app-core @ git+https://github.com/kh6570/HAbedini-mcp-app-core.git
```

`pip install` of either server clones this repository from GitHub. People who clone a server do not clone this one by hand. Git does not download dependencies during `git clone`; `pip install` does.

If a checkout of this repository already sits next to a server, that server's setup script and test runner use the local checkout. Set `MCP_CORE_PATH` when the checkout is in another folder.

The public Git repository for this package is https://github.com/kh6570/HAbedini-mcp-app-core.

## Using it from a new server

Depend on `mcp-app-core`, then subclass `AppError` and `AppSettings` with your environment prefix. Pass your service package names to `discover_service_specs`. Keep file formats and executables in the server repository.

## License

MIT. See [LICENSE](LICENSE).
