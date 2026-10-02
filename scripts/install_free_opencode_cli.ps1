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

$targetBinaryPath = Join-Path $installRoot "node_modules\opencode-ai\bin\opencode.exe"
$existingVersion = $null
$existingExitCode = $null
$existingBinarySize = $null
$existingHealthy = $false

if (Test-Path -LiteralPath $cliPath -PathType Leaf) {
    try {
        $existingOutput = @(& $cliPath --version 2>$null)
        $existingExitCode = [int]$LASTEXITCODE
        $existingVersion = [string]($existingOutput | Select-Object -First 1)
    } catch {
        $existingExitCode = 1
    }
}
if (Test-Path -LiteralPath $targetBinaryPath -PathType Leaf) {
    $existingBinarySize = (Get-Item -LiteralPath $targetBinaryPath).Length
}
$existingHealthy = (
    $existingExitCode -eq 0 -and
    -not [string]::IsNullOrWhiteSpace($existingVersion) -and
    $existingVersion.Trim() -eq $Version -and
    $null -ne $existingBinarySize -and
    $existingBinarySize -ge 1000000
)

$installedNow = $false
$approvedInstallScript = "opencode-ai@$Version"
if (-not $existingHealthy) {
    $nodeModulesPath = Join-Path $installRoot "node_modules"
    $lockPath = Join-Path $installRoot "package-lock.json"
    if (Test-Path -LiteralPath $nodeModulesPath) {
        Remove-Item -LiteralPath $nodeModulesPath -Recurse -Force
    }
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        Remove-Item -LiteralPath $lockPath -Force
    }

    $allowScripts = @{}
    $allowScripts[$approvedInstallScript] = $true
    $manifest = [ordered]@{
        name = "horse-racing-predictions-free-opencode-runner"
        version = "0.0.0"
        private = $true
        allowScripts = $allowScripts
    }
    $manifestPath = Join-Path $installRoot "package.json"
    $manifest | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath $manifestPath -Encoding UTF8

    & npm install --prefix $installRoot --no-audit --no-fund --ignore-scripts "opencode-ai@$Version"
    if ($LASTEXITCODE -ne 0) {
        throw "Free OpenCode CLI npm package installation failed."
    }

    Push-Location $installRoot
    try {
        & npm approve-scripts opencode-ai
        if ($LASTEXITCODE -ne 0) {
            throw "OpenCode install-script approval failed."
        }

        $approvedManifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $allowedKeys = @($approvedManifest.allowScripts.PSObject.Properties.Name)
        if ($allowedKeys.Count -ne 1 -or $allowedKeys[0] -ne $approvedInstallScript) {
            throw "Unexpected install-script approval set: $($allowedKeys -join ',')"
        }
        if (-not [bool]$approvedManifest.allowScripts.$approvedInstallScript) {
            throw "Pinned OpenCode install script is not explicitly allowed."
        }

        $packageRoot = Join-Path $installRoot "node_modules\opencode-ai"
        $packageManifestPath = Join-Path $packageRoot "package.json"
        $postinstallPath = Join-Path $packageRoot "postinstall.mjs"
        if (-not (Test-Path -LiteralPath $packageManifestPath -PathType Leaf)) {
            throw "Pinned OpenCode package manifest is missing."
        }
        if (-not (Test-Path -LiteralPath $postinstallPath -PathType Leaf)) {
            throw "Pinned OpenCode postinstall script is missing."
        }

        $packageManifest = Get-Content -LiteralPath $packageManifestPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if ([string]$packageManifest.name -ne "opencode-ai") {
            throw "Unexpected package identity before postinstall."
        }
        if ([string]$packageManifest.version -ne $Version) {
            throw "Unexpected OpenCode package version before postinstall: $($packageManifest.version)"
        }

        if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
            throw "NODE_NOT_AVAILABLE"
        }
        & node $postinstallPath
        if ($LASTEXITCODE -ne 0) {
            throw "Pinned OpenCode postinstall execution failed."
        }

        if (-not (Test-Path -LiteralPath $targetBinaryPath -PathType Leaf)) {
            throw "OpenCode target binary is missing after postinstall."
        }
        $targetBinarySize = (Get-Item -LiteralPath $targetBinaryPath).Length
        if ($targetBinarySize -lt 1000000) {
            throw "OpenCode target binary remains a placeholder after postinstall."
        }
    } finally {
        Pop-Location
    }

    $installedNow = $true
}

if (-not (Test-Path -LiteralPath $cliPath -PathType Leaf)) {
    throw "OpenCode CLI wrapper was not created at the expected isolated path."
}

$actualOutput = @(& $cliPath --version 2>$null)
$actualExitCode = [int]$LASTEXITCODE
$actualVersion = [string]($actualOutput | Select-Object -First 1)
if ($actualExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($actualVersion)) {
    throw "OpenCode CLI --version failed after bootstrap."
}
if ($actualVersion.Trim() -ne $Version) {
    throw "OpenCode CLI version mismatch: expected=$Version actual=$actualVersion"
}
if (-not (Test-Path -LiteralPath $targetBinaryPath -PathType Leaf)) {
    throw "OpenCode target binary is missing after bootstrap."
}
$finalBinarySize = (Get-Item -LiteralPath $targetBinaryPath).Length
if ($finalBinarySize -lt 1000000) {
    throw "OpenCode target binary is still a placeholder after bootstrap."
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
    install_script_policy = "pinned_single_package_only"
    approved_install_script = $approvedInstallScript
    postinstall_execution = "explicit_pinned_package_script"
    target_binary_size_bytes = $finalBinarySize
    existing_install_healthy = [bool]$existingHealthy
    existing_version_exit_code = $existingExitCode
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
