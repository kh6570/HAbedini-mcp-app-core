# In the name of God, the Most Gracious, the Most Merciful
# Install mcp-app-core from GitHub, or from MCP_CORE_PATH when developing locally.
param(
    [string]$CorePath = $env:MCP_CORE_PATH,
    [string]$CoreRepo = "https://github.com/kh6570/HAbedini-mcp-app-core.git"
)

$ErrorActionPreference = "Stop"
$Python = "python"
if ($CorePath -and (Test-Path $CorePath)) {
    & $Python -m pip install -e $CorePath
    Write-Output "installed mcp-app-core from $CorePath"
    return
}

& $Python -m pip install "mcp-app-core @ git+$CoreRepo"
Write-Output "installed mcp-app-core from $CoreRepo"
