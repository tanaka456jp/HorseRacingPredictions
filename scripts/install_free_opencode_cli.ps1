param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$Version = "1.18.29",
    [string]$ValidationOutput = "artifacts/free_opencode_cli_install_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing free OpenCode CLI bootstrap on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "NPM_NOT_AVAILABLE"
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
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
$cliPath = Join-Path $installRoot "node_modules\.bin\opencode.cmd"

$existingVersion = $null
if (Test-Path -LiteralPath $cliPath -PathType Leaf) {
    try {
        $existingVersion = [string]((& $cliPath --version 2>$null | Select-Object -First 1))
    } catch {}
}

$installedNow = $false
if ($existingVersion -ne $Version) {
    & npm install --prefix $installRoot --no-audit --no-fund "opencode-ai@$Version"
    if ($LASTEXITCODE -ne 0) {
        throw "Free OpenCode CLI npm installation failed."
    }
    $installedNow = $true
}

if (-not (Test-Path -LiteralPath $cliPath -PathType Leaf)) {
    throw "OpenCode CLI wrapper was not created at the expected isolated path."
}

$actualVersion = [string]((& $cliPath --version 2>$null | Select-Object -First 1))
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($actualVersion)) {
    throw "OpenCode CLI --version failed after bootstrap."
}
if ($actualVersion.Trim() -ne $Version) {
    throw "OpenCode CLI version mismatch: expected=$Version actual=$actualVersion"
}

$validation = @{
    status = "installed"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    expected_computer_name = $ExpectedComputerName
    package = "opencode-ai"
    requested_version = $Version
    actual_version = $actualVersion.Trim()
    installed_now = $installedNow
    install_scope = "runner_isolated_localappdata"
    install_path_sanitized = "%LOCALAPPDATA%\HorseRacingPredictionsAutonomousDev\opencode-cli-$Version"
    paid_provider_used = $false
    api_key_used = $false
    codex_used = $false
    secrets_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $validationPath) | Out-Null
$validation | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Free OpenCode CLI bootstrap PASS."
Write-Host "version=$($actualVersion.Trim())"
Write-Host "installed_now=$installedNow"
Write-Host "paid_provider_used=False"
