param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Version = "1.18.29",
    [string]$Model = "ollama/qwen3:8b",
    [string]$ValidationOutput = "artifacts/free_opencode_ollama_smoke_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing free OpenCode smoke on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}

foreach ($name in @(
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "OLLAMA_API_KEY"
)) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

$controlRoot = Join-Path $env:LOCALAPPDATA "HorseRacingPredictionsAutonomousDev"
$installRoot = Join-Path $controlRoot "opencode-cli-$Version"
$cliPath = Join-Path $installRoot "node_modules\.bin\opencode.cmd"
if (-not (Test-Path -LiteralPath $cliPath -PathType Leaf)) {
    throw "FREE_OPENCODE_CLI_NOT_BOOTSTRAPPED"
}

$tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 5
$modelNames = @($tags.models | ForEach-Object { [string]$_.name })
if ($modelNames -notcontains "qwen3:8b") {
    throw "Required local model qwen3:8b is not available."
}

$smokeRoot = Join-Path $controlRoot "free-opencode-smoke"
if (Test-Path -LiteralPath $smokeRoot) {
    Remove-Item -LiteralPath $smokeRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null

$configPath = Join-Path $smokeRoot "opencode.json"
@'
{
  "$schema": "https://opencode.ai/config.json",
  "model": "ollama/qwen3:8b",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local only)",
      "options": {
        "baseURL": "http://127.0.0.1:11434/v1"
      },
      "models": {
        "qwen3:8b": {
          "name": "qwen3:8b"
        }
      }
    }
  }
}
'@ | Set-Content -LiteralPath $configPath -Encoding UTF8

Push-Location $smokeRoot
try {
    $prompt = "Reply with exactly FREE_LOCAL_SMOKE_OK. Do not edit or create files."
    $output = @(& $cliPath run --model $Model $prompt 2>&1)
    $exitCode = [int]$LASTEXITCODE
} finally {
    Pop-Location
}

$outputText = [string](($output | Out-String).Trim())
$markerSeen = $outputText -match "FREE_LOCAL_SMOKE_OK"
if ($exitCode -ne 0) {
    throw "OpenCode local Ollama smoke failed with exit code $exitCode."
}
if (-not $markerSeen) {
    throw "OpenCode local Ollama smoke completed but expected marker was not returned."
}

$unexpectedFiles = @(
    Get-ChildItem -LiteralPath $smokeRoot -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "opencode.json" }
)
if ($unexpectedFiles.Count -gt 0) {
    throw "Smoke created unexpected files despite the no-edit instruction."
}

$validation = @{
    status = "success"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    opencode_version = $Version
    provider = "ollama_local"
    model = $Model
    ollama_endpoint = "http://127.0.0.1:11434"
    marker_seen = [bool]$markerSeen
    paid_provider_used = $false
    api_key_used = $false
    codex_used = $false
    repository_modified = $false
    raw_model_output_included = $false
    secrets_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $validationPath) | Out-Null
$validation | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Free OpenCode + Ollama smoke PASS."
Write-Host "model=$Model"
Write-Host "marker_seen=$markerSeen"
Write-Host "paid_provider_used=False"
