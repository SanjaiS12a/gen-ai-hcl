# Explicit setup only. The running app never downloads a model or executable.
param(
    [string]$ToolsRoot = (Join-Path (Split-Path -Parent $PSScriptRoot | Split-Path -Parent) 'tools'),
    [string]$ModelRoot = (Join-Path (Split-Path -Parent $PSScriptRoot | Split-Path -Parent) 'models\Qwen3.5-0.8B-GGUF')
)
$ErrorActionPreference = 'Stop'
$runtimeVersion = 'b11755'
$archivePath = Join-Path $ToolsRoot "llama-$runtimeVersion.zip"
$runtimePath = Join-Path $ToolsRoot "llama-$runtimeVersion"
$modelFile = 'Qwen3.5-0.8B-Q8_0.gguf'
$modelPath = Join-Path $ModelRoot $modelFile
$revision = '807dfd9a6fadbf703207aac3bfb0b2b3040d077c'
New-Item -ItemType Directory -Force -Path $ToolsRoot,$ModelRoot | Out-Null
if (-not (Test-Path -LiteralPath $archivePath)) {
    Invoke-WebRequest "https://github.com/ggml-org/llama.cpp/releases/download/$runtimeVersion/llama-$runtimeVersion-bin-win-cpu-x64.zip" -OutFile $archivePath
}
if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLower() -ne '450b11d263c34e521ef0800bce69e3262d6657546fdedbd6f3005769f21a2568') {
    throw 'Runtime archive checksum mismatch; no executable was started.'
}
if (-not (Test-Path -LiteralPath (Join-Path $runtimePath 'llama-server.exe'))) {
    Expand-Archive -LiteralPath $archivePath -DestinationPath $runtimePath
}
if (-not (Test-Path -LiteralPath $modelPath)) {
    $hubCli = Get-Command hf -ErrorAction SilentlyContinue
    if ($hubCli) {
        $oldOffline = $env:HF_HUB_OFFLINE
        try {
            $env:HF_HUB_OFFLINE = '0'
            & $hubCli.Source download ggml-org/Qwen3.5-0.8B-GGUF $modelFile --revision $revision --local-dir $ModelRoot
            if ($LASTEXITCODE -ne 0) { throw 'Hugging Face download failed.' }
        } finally { $env:HF_HUB_OFFLINE = $oldOffline }
    } else {
        Invoke-WebRequest "https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/resolve/$revision/$modelFile" -OutFile $modelPath
    }
}
if ((Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash.ToLower() -ne '37ae482d336108d23516fa35e8e0c4126688d81018b87178a18d752a1357814f') {
    throw 'Model checksum mismatch; no model was started.'
}
Write-Output "Verified portable CPU runtime and Qwen3.5-0.8B Q8_0 model. Add these settings to .env:"
Write-Output 'LLM_PROVIDER=llamacpp'
Write-Output "LLAMA_SERVER_PATH=$(Join-Path $runtimePath 'llama-server.exe')"
Write-Output "MODEL_PATH=$modelPath"
Write-Output 'LLAMA_THREADS=4'
Write-Output 'LLAMA_BATCH_THREADS=8'
Write-Output 'MAX_NEW_TOKENS=300'
Write-Output 'GENERATION_TIMEOUT=90'
