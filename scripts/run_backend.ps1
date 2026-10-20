$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (Test-Path -LiteralPath '.env') {
    foreach ($line in Get-Content -LiteralPath '.env') {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $variableName = $Matches[1]
            if ($variableName -in @('HOME', 'CODEX_HOME', 'PATH', 'PYTHONPATH')) { continue }
            [Environment]::SetEnvironmentVariable($variableName, $Matches[2].Trim('"').Trim("'"), 'Process')
        }
    }
}
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DO_NOT_TRACK = '1'
if (-not $env:HF_HUB_OFFLINE) { $env:HF_HUB_OFFLINE = '1' }
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = 'python' }
& $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
