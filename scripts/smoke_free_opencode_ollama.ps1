param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Version = "1.18.29",
    [string]$Model = "ollama/qwen3:8b",
    [int]$TimeoutSeconds = 180,
    [string]$ValidationOutput = "artifacts/free_opencode_ollama_smoke_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing free OpenCode smoke on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}
if ($TimeoutSeconds -lt 30 -or $TimeoutSeconds -gt 600) {
    throw "TimeoutSeconds must be between 30 and 600."
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
$binaryPath = Join-Path $installRoot "node_modules\opencode-ai\bin\opencode.exe"
if (-not (Test-Path -LiteralPath $binaryPath -PathType Leaf)) {
    throw "FREE_OPENCODE_CLI_NOT_BOOTSTRAPPED"
}
$binarySize = (Get-Item -LiteralPath $binaryPath).Length
if ($binarySize -lt 1000000) {
    throw "FREE_OPENCODE_CLI_BINARY_IS_PLACEHOLDER"
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

$stdoutPath = Join-Path $smokeRoot "stdout.log"
$stderrPath = Join-Path $smokeRoot "stderr.log"
$prompt = "/no_think Reply with exactly FREE_LOCAL_SMOKE_OK. Do not edit or create files."
$escapedModel = '"' + $Model.Replace('"', '\"') + '"'
$escapedPrompt = '"' + $prompt.Replace('"', '\"') + '"'
$argumentString = "run --standalone --model $escapedModel $escapedPrompt"

$process = Start-Process -FilePath $binaryPath -ArgumentList $argumentString -WorkingDirectory $smokeRoot -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru

$completed = $process.WaitForExit($TimeoutSeconds * 1000)
$timedOut = -not $completed
if ($timedOut) {
    & taskkill.exe /PID $process.Id /T /F *> $null
    $process.WaitForExit()
    $exitCode = -1
} else {
    $exitCode = [int]$process.ExitCode
}

$stdoutText = ""
$stderrText = ""
if (Test-Path -LiteralPath $stdoutPath -PathType Leaf) {
    $stdoutText = Get-Content -LiteralPath $stdoutPath -Raw -Encoding UTF8
}
if (Test-Path -LiteralPath $stderrPath -PathType Leaf) {
    $stderrText = Get-Content -LiteralPath $stderrPath -Raw -Encoding UTF8
}
$outputText = [string]($stdoutText + [Environment]::NewLine + $stderrText)
$markerSeen = $outputText -match "FREE_LOCAL_SMOKE_OK"

Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue

$unexpectedFiles = @(
    Get-ChildItem -LiteralPath $smokeRoot -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "opencode.json" }
)
$repositoryModified = ($unexpectedFiles.Count -gt 0)

$status = "success"
if ($timedOut) {
    $status = "timeout"
} elseif ($exitCode -ne 0) {
    $status = "failed_exit_code"
} elseif (-not $markerSeen) {
    $status = "missing_marker"
} elseif ($repositoryModified) {
    $status = "unexpected_file_write"
}

$validation = @{
    status = $status
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    opencode_version = $Version
    opencode_binary_size_bytes = $binarySize
    provider = "ollama_local"
    model = $Model
    ollama_endpoint = "http://127.0.0.1:11434"
    standalone = $true
    output_format = "default"
    timeout_seconds = $TimeoutSeconds
    timed_out = [bool]$timedOut
    exit_code = $exitCode
    marker_seen = [bool]$markerSeen
    paid_provider_used = $false
    api_key_used = $false
    codex_used = $false
    repository_modified = [bool]$repositoryModified
    raw_model_output_included = $false
    secrets_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $validationPath) | Out-Null
$validation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $validationPath -Encoding UTF8

if ($timedOut) {
    throw "OpenCode local Ollama smoke timed out after $TimeoutSeconds seconds."
}
if ($exitCode -ne 0) {
    throw "OpenCode local Ollama smoke failed with exit code $exitCode."
}
if (-not $markerSeen) {
    throw "OpenCode local Ollama smoke completed but expected marker was not returned."
}
if ($repositoryModified) {
    throw "Smoke created unexpected files despite the no-edit instruction."
}

Write-Host "Free OpenCode + Ollama smoke PASS."
Write-Host "model=$Model"
Write-Host "marker_seen=$markerSeen"
Write-Host "paid_provider_used=False"
