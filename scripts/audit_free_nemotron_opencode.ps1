param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Version = "1.18.29",
    [string]$Model = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    [int]$TimeoutSeconds = 240,
    [string]$ValidationOutput = "artifacts/free_nemotron_opencode_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing Nemotron smoke on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}
if ($Version -ne "1.18.29") {
    throw "This smoke is pinned to OpenCode 1.18.29."
}
if ($Model -ne "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free") {
    throw "Only the exact OpenRouter Nemotron 3 Ultra :free model is allowed."
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
$binaryPath = Join-Path $controlRoot "opencode-cli-$Version\node_modules\opencode-ai\bin\opencode.exe"
if (-not (Test-Path -LiteralPath $binaryPath -PathType Leaf)) {
    throw "FREE_OPENCODE_CLI_NOT_BOOTSTRAPPED"
}
if ((Get-Item -LiteralPath $binaryPath).Length -lt 1000000) {
    throw "FREE_OPENCODE_CLI_BINARY_IS_PLACEHOLDER"
}

$envKeyPresent = -not [string]::IsNullOrWhiteSpace($env:OPENROUTER_API_KEY)
$authText = ""
try {
    $authRaw = @(& $binaryPath auth list --format json 2>$null)
    if ($LASTEXITCODE -eq 0) {
        $authText = [string](($authRaw | Out-String).Trim())
    }
} catch {
    $authText = ""
}
if ([string]::IsNullOrWhiteSpace($authText)) {
    try {
        $authRaw = @(& $binaryPath auth list 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $authText = [string](($authRaw | Out-String).Trim())
        }
    } catch {
        $authText = ""
    }
}
$storedOpenRouterAuth = $authText -match "(?i)openrouter"
$openRouterAuthenticated = $envKeyPresent -or $storedOpenRouterAuth

$validationPath = Join-Path $ProjectRoot $ValidationOutput
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $validationPath) | Out-Null

function Write-Validation {
    param(
        [string]$Status,
        [bool]$MarkerSeen = $false,
        [int]$ExitCode = -1,
        [int64]$StdoutBytes = 0,
        [int64]$StderrBytes = 0
    )
    @{
        status = $Status
        validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        computer_name = $env:COMPUTERNAME
        opencode_version = $Version
        provider = "openrouter"
        model = $Model
        free_model_suffix_verified = $Model.EndsWith(":free")
        openrouter_authenticated = [bool]$openRouterAuthenticated
        env_key_present = [bool]$envKeyPresent
        stored_openrouter_auth_present = [bool]$storedOpenRouterAuth
        paid_provider_used = $false
        paid_fallback_allowed = $false
        exact_model_required = $true
        api_key_auth_may_be_used = [bool]$openRouterAuthenticated
        codex_used = $false
        live_execution_enabled = $false
        marker_seen = [bool]$MarkerSeen
        exit_code = $ExitCode
        stdout_bytes = $StdoutBytes
        stderr_bytes = $StderrBytes
        raw_model_output_included = $false
        secrets_included = $false
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $validationPath -Encoding UTF8
}

if (-not $openRouterAuthenticated) {
    Write-Validation -Status "openrouter_not_authenticated"
    Write-Host "openrouter_authenticated=False"
    Write-Host "target_model=$Model"
    Write-Host "paid_fallback_allowed=False"
    throw "OPENROUTER_NOT_AUTHENTICATED"
}

$smokeRoot = Join-Path $controlRoot "free-nemotron-smoke"
$configRoot = Join-Path $controlRoot "free-nemotron-smoke-config"
foreach ($path in @($smokeRoot, $configRoot)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$configJson = @'
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
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
  }
}
'@

$env:OPENCODE_CONFIG_CONTENT = $configJson
$env:OPENCODE_CONFIG_DIR = $configRoot
$env:OPENCODE_DISABLE_PROJECT_CONFIG = "1"
$env:OPENCODE_PURE = "1"
$env:OPENCODE_DISABLE_AUTOUPDATE = "1"

$stdoutPath = Join-Path $smokeRoot "stdout.log"
$stderrPath = Join-Path $smokeRoot "stderr.log"
$prompt = "/no_think Reply exactly FREE_NEMOTRON_SMOKE_OK. Do not call tools. Do not create or edit files."
$sessionTitle = "HRP_FREE_NEMOTRON_$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
$escapedModel = '"' + $Model.Replace('"', '\"') + '"'
$escapedPrompt = '"' + $prompt.Replace('"', '\"') + '"'
$escapedTitle = '"' + $sessionTitle.Replace('"', '\"') + '"'
$escapedDir = '"' + $smokeRoot.Replace('"', '\"') + '"'
$argumentString = "--pure run --agent build --format json --dir $escapedDir --model $escapedModel --title $escapedTitle $escapedPrompt"

$process = Start-Process -FilePath $binaryPath -ArgumentList $argumentString -WorkingDirectory $smokeRoot -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
$completed = $process.WaitForExit($TimeoutSeconds * 1000)
if (-not $completed) {
    & taskkill.exe /PID $process.Id /T /F *> $null
    $process.WaitForExit()
    $stdoutBytes = if (Test-Path -LiteralPath $stdoutPath) { (Get-Item -LiteralPath $stdoutPath).Length } else { 0 }
    $stderrBytes = if (Test-Path -LiteralPath $stderrPath) { (Get-Item -LiteralPath $stderrPath).Length } else { 0 }
    Write-Validation -Status "timeout" -ExitCode -1 -StdoutBytes $stdoutBytes -StderrBytes $stderrBytes
    throw "Nemotron 3 Ultra free smoke timed out after $TimeoutSeconds seconds."
}

$exitCode = [int]$process.ExitCode
$stdoutText = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw -Encoding UTF8 } else { "" }
$markerSeen = $stdoutText -match "FREE_NEMOTRON_SMOKE_OK"
$stdoutBytes = if (Test-Path -LiteralPath $stdoutPath) { (Get-Item -LiteralPath $stdoutPath).Length } else { 0 }
$stderrBytes = if (Test-Path -LiteralPath $stderrPath) { (Get-Item -LiteralPath $stderrPath).Length } else { 0 }

Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
$unexpectedFiles = @(Get-ChildItem -LiteralPath $smokeRoot -File -Recurse -ErrorAction SilentlyContinue)

$status = "success"
if ($exitCode -ne 0) {
    $status = "failed_exit_code"
} elseif (-not $markerSeen) {
    $status = "missing_response_marker"
} elseif ($unexpectedFiles.Count -gt 0) {
    $status = "unexpected_file_write"
}
Write-Validation -Status $status -MarkerSeen $markerSeen -ExitCode $exitCode -StdoutBytes $stdoutBytes -StderrBytes $stderrBytes

Write-Host "openrouter_authenticated=True"
Write-Host "target_model=$Model"
Write-Host "paid_provider_used=False"
Write-Host "paid_fallback_allowed=False"
Write-Host "marker_seen=$markerSeen"

if ($status -ne "success") {
    throw "Nemotron 3 Ultra free smoke failed with status=$status."
}
Write-Host "Free Nemotron 3 Ultra OpenCode smoke PASS."
$global:LASTEXITCODE = 0
