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
    Move-Item -LiteralPath $tempPath -Destination $codexPath -Force
} finally {
    Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
}

$version = (& $codexPath --version | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$version)) {
    throw "Installed Codex binary did not respond to --version."
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
