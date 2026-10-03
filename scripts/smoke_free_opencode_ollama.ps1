param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Version = "1.18.29",
    [string]$Model = "ollama/qwen3:8b",
    [int]$TimeoutSeconds = 240,
    [string]$ValidationOutput = "artifacts/free_opencode_ollama_smoke_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing free OpenCode smoke on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}
if ($Version -ne "1.18.29") {
    throw "This smoke is pinned to OpenCode 1.18.29."
}
if ($Model -ne "ollama/qwen3:8b") {
    throw "Only the local model ollama/qwen3:8b is allowed."
}
if ($TimeoutSeconds -lt 30 -or $TimeoutSeconds -gt 600) {
    throw "TimeoutSeconds must be between 30 and 600."
}

foreach ($name in @(
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "OLLAMA_API_KEY",
    "OPENCODE_SERVER_PASSWORD",
    "OPENCODE_SERVER_USERNAME",
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_CONTENT",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_PERMISSION"
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
$configRoot = Join-Path $controlRoot "free-opencode-smoke-config"
foreach ($path in @($smokeRoot, $configRoot)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$configJson = @'
{
  "$schema": "https://opencode.ai/config.json",
  "model": "ollama/qwen3:8b",
  "share": "disabled",
  "default_agent": "build",
  "agent": {
    "build": {
      "mode": "primary",
      "permission": {
        "read": "deny",
        "edit": "deny",
        "glob": "deny",
        "grep": "deny",
        "list": "deny",
        "bash": "deny",
        "task": "deny",
        "external_directory": "deny",
        "webfetch": "deny",
        "websearch": "deny",
        "question": "deny",
        "doom_loop": "deny"
      }
    }
  },
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
'@

$env:OPENCODE_CONFIG_CONTENT = $configJson
$env:OPENCODE_CONFIG_DIR = $configRoot
$env:OPENCODE_DISABLE_PROJECT_CONFIG = "1"
$env:OPENCODE_PURE = "1"
$env:OPENCODE_DISABLE_AUTOUPDATE = "1"
$env:OPENCODE_DISABLE_MODELS_FETCH = "1"

$stdoutPath = Join-Path $smokeRoot "stdout.log"
$stderrPath = Join-Path $smokeRoot "stderr.log"
$prompt = "/no_think Reply exactly FREE_LOCAL_SMOKE_OK. Do not call tools. Do not create or edit files."
$sessionTitle = "HRP_FREE_LOCAL_SMOKE_$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
$escapedModel = '"' + $Model.Replace('"', '\"') + '"'
$escapedPrompt = '"' + $prompt.Replace('"', '\"') + '"'
$escapedTitle = '"' + $sessionTitle.Replace('"', '\"') + '"'
$escapedDir = '"' + $smokeRoot.Replace('"', '\"') + '"'

# OpenCode 1.18.29 non-attach run uses its in-process server. This smoke only
# proves local model connectivity. Repository editing is verified by the
# guarded autonomous cycle itself via repo_changes + fail-fast.
$argumentString = "--pure run --agent build --format json --dir $escapedDir --model $escapedModel --title $escapedTitle $escapedPrompt"

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
if (Test-Path -LiteralPath $stdoutPath -PathType Leaf) {
    $stdoutText = Get-Content -LiteralPath $stdoutPath -Raw -Encoding UTF8
}
$markerSeenStdout = $stdoutText -match "FREE_LOCAL_SMOKE_OK"
$verificationChannel = if ($markerSeenStdout) { "stdout_json_events" } else { "none" }

$stdoutBytes = if (Test-Path -LiteralPath $stdoutPath) {
    (Get-Item -LiteralPath $stdoutPath).Length
} else {
    0
}
$stderrBytes = if (Test-Path -LiteralPath $stderrPath) {
    (Get-Item -LiteralPath $stderrPath).Length
} else {
    0
}

Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue

$unexpectedFiles = @(
    Get-ChildItem -LiteralPath $smokeRoot -File -Recurse -ErrorAction SilentlyContinue
)
$workspaceModifiedUnexpectedly = ($unexpectedFiles.Count -gt 0)

$status = "success"
if ($timedOut) {
    $status = "timeout"
} elseif ($exitCode -ne 0) {
    $status = "failed_exit_code"
} elseif (-not $markerSeenStdout) {
    $status = "missing_response_marker"
} elseif ($workspaceModifiedUnexpectedly) {
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
    run_transport = "in_process_non_attach"
    pure_mode = $true
    shared_service_used = $false
    session_persistence_required = $false
    output_format = "json"
    timeout_seconds = $TimeoutSeconds
    timed_out = [bool]$timedOut
    exit_code = $exitCode
    stdout_bytes = [int64]$stdoutBytes
    stderr_bytes = [int64]$stderrBytes
    marker_seen = [bool]$markerSeenStdout
    verification_channel = $verificationChannel
    connectivity_only = $true
    tool_write_required = $false
    model_invocation_explicit = $true
    local_model_present = $true
    isolated_config_dir = $true
    project_config_disabled = $true
    external_plugins_disabled = $true
    paid_provider_used = $false
    api_key_used = $false
    codex_used = $false
    repository_modified = [bool]$workspaceModifiedUnexpectedly
    raw_model_output_included = $false
    secrets_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $validationPath) | Out-Null
$validation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "opencode_run_transport=in_process_non_attach"
Write-Host "opencode_pure=True"
Write-Host "opencode_agent=build"
Write-Host "smoke_scope=connectivity_only"
Write-Host "opencode_result exit_code=$exitCode stdout_bytes=$stdoutBytes stderr_bytes=$stderrBytes marker_seen=$markerSeenStdout"

if ($timedOut) {
    throw "OpenCode local Ollama connectivity smoke timed out after $TimeoutSeconds seconds."
}
if ($exitCode -ne 0) {
    throw "OpenCode local Ollama connectivity smoke failed with exit code $exitCode."
}
if (-not $markerSeenStdout) {
    throw "OpenCode local Ollama connectivity smoke completed but expected response marker was not returned."
}
if ($workspaceModifiedUnexpectedly) {
    throw "OpenCode connectivity smoke created unexpected files despite all tools being denied."
}

Write-Host "Free OpenCode + Ollama connectivity smoke PASS."
Write-Host "model=$Model"
Write-Host "marker_seen=$markerSeenStdout"
Write-Host "paid_provider_used=False"
