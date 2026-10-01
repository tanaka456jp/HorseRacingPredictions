param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$ValidationOutput = "artifacts/codex_cli_install_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing Codex installation on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI is required to resolve the official Codex release."
}
& gh auth status --hostname github.com *> $null
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated."
}

$releaseJson = & gh api repos/openai/codex/releases/latest
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve the latest openai/codex release."
}
$release = $releaseJson | ConvertFrom-Json
$asset = $release.assets | Where-Object {
    $_.name -eq "codex-x86_64-pc-windows-msvc.exe"
} | Select-Object -First 1
if ($null -eq $asset) {
    throw "Windows x64 Codex release asset was not found."
}

$installDir = Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
$codexPath = Join-Path $installDir "codex.exe"
$tempPath = Join-Path $env:TEMP "codex-download-$PID.exe"

try {
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tempPath -UseBasicParsing
    if (-not (Test-Path -LiteralPath $tempPath -PathType Leaf)) {
        throw "Codex download did not produce a file."
    }
    $downloadLength = (Get-Item -LiteralPath $tempPath).Length
    $expectedLength = [int64]$asset.size
    if ($downloadLength -ne $expectedLength) {
        throw "Codex download size mismatch: expected=$expectedLength actual=$downloadLength"
    }
    Move-Item -LiteralPath $tempPath -Destination $codexPath -Force
    Unblock-File -LiteralPath $codexPath -ErrorAction SilentlyContinue
} finally {
    Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
}

$stdoutPath = Join-Path $env:TEMP "codex-version-$PID.stdout.txt"
$stderrPath = Join-Path $env:TEMP "codex-version-$PID.stderr.txt"
try {
    $process = Start-Process -FilePath $codexPath -ArgumentList "--version" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $versionOutput = ""
    if (Test-Path -LiteralPath $stdoutPath) {
        $versionOutput = ([string](Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue)).Trim()
    }
    $stderrOutput = ""
    if (Test-Path -LiteralPath $stderrPath) {
        $stderrOutput = ([string](Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue)).Trim()
    }
    if ($process.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($versionOutput)) {
        $safeError = $stderrOutput
        if ($safeError.Length -gt 1000) {
            $safeError = $safeError.Substring(0, 1000)
        }
        throw "Installed Codex binary failed --version: exit_code=$($process.ExitCode); stderr=$safeError"
    }
    $version = ($versionOutput -split "`r?`n")[0]
} finally {
    Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathParts = @()
if (-not [string]::IsNullOrWhiteSpace($userPath)) {
    $pathParts = $userPath.Split(";") | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_)
    }
}
if ($pathParts -notcontains $installDir) {
    $newPath = (($pathParts + $installDir) -join ";")
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
}
if (($env:Path.Split(";")) -notcontains $installDir) {
    $env:Path = "$installDir;$env:Path"
}

# Never authenticate this validation run with an API key.
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue

$authenticated = $false
try {
    & $codexPath login status *> $null
    $authenticated = ($LASTEXITCODE -eq 0)
} catch {
    $authenticated = $false
}

$validation = @{
    status = "installed"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    expected_computer_name = $ExpectedComputerName
    release_tag = [string]$release.tag_name
    version = [string]$version
    install_directory = $installDir
    user_path_contains_install_directory = (
        ([Environment]::GetEnvironmentVariable("Path", "User").Split(";")) -contains $installDir
    )
    chatgpt_login_authenticated = [bool]$authenticated
    api_key_used = $false
    secrets_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$validation | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Codex CLI installation PASS."
Write-Host "release_tag=$($release.tag_name)"
Write-Host "version=$version"
Write-Host "chatgpt_login_authenticated=$authenticated"
Write-Host "api_key_used=False"
