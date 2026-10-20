$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'frontend')
if (-not (Test-Path -LiteralPath 'node_modules')) {
    Write-Error 'Install frontend dependencies first: cd frontend; npm ci'
    exit 1
}
& npm.cmd run dev
exit $LASTEXITCODE
