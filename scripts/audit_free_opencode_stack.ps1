param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$ValidationOutput = "artifacts/free_opencode_stack_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing free-stack audit on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-VersionLine {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    if (-not (Test-CommandAvailable -Name $Name)) {
        return $null
    }
    try {
        $output = & $Name @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        $line = $output | Select-Object -First 1
        if ($null -eq $line) {
            return $null
        }
        return [string]$line
    } catch {
        return $null
    }
}

$commands = @{
    git = Test-CommandAvailable "git"
    gh = Test-CommandAvailable "gh"
    node = Test-CommandAvailable "node"
    npm = Test-CommandAvailable "npm"
    opencode = Test-CommandAvailable "opencode"
    ollama = Test-CommandAvailable "ollama"
    python = Test-CommandAvailable "python"
}

$versions = @{
    git = Get-VersionLine -Name "git" -Arguments @("--version")
    gh = Get-VersionLine -Name "gh" -Arguments @("--version")
    node = Get-VersionLine -Name "node" -Arguments @("--version")
    npm = Get-VersionLine -Name "npm" -Arguments @("--version")
    opencode = Get-VersionLine -Name "opencode" -Arguments @("--version")
    ollama = Get-VersionLine -Name "ollama" -Arguments @("--version")
    python = Get-VersionLine -Name "python" -Arguments @("--version")
}

$localModels = @()
if ($commands.ollama) {
    try {
        $jsonText = & ollama list --json 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace([string]$jsonText)) {
            $parsed = $jsonText | ConvertFrom-Json
            foreach ($item in @($parsed.models)) {
                $name = [string]$item.name
                if (-not [string]::IsNullOrWhiteSpace($name)) {
                    $localModels += @{
                        name = $name
                        size = [int64]$item.size
                        cloud_like_name = (
                            $name -match "(?i)(cloud|remote)"
                        )
                    }
                }
            }
        } else {
            $lines = @(& ollama list 2>$null)
            foreach ($line in ($lines | Select-Object -Skip 1)) {
                $parts = ([string]$line).Trim() -split "\s{2,}"
                if ($parts.Count -ge 1 -and -not [string]::IsNullOrWhiteSpace($parts[0])) {
                    $name = [string]$parts[0]
                    $localModels += @{
                        name = $name
                        size = $null
                        cloud_like_name = (
                            $name -match "(?i)(cloud|remote)"
                        )
                    }
                }
            }
        }
    } catch {
        $localModels = @()
    }
}

$freeLocalCandidates = @(
    $localModels | Where-Object {
        -not $_.cloud_like_name
    }
)

$ghAuthenticated = $false
if ($commands.gh) {
    try {
        & gh auth status --hostname github.com *> $null
        $ghAuthenticated = ($LASTEXITCODE -eq 0)
    } catch {
        $ghAuthenticated = $false
    }
}

$cloudCredentialFlags = @{
    openai_api_key_present = -not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)
    anthropic_api_key_present = -not [string]::IsNullOrWhiteSpace($env:ANTHROPIC_API_KEY)
    google_api_key_present = -not [string]::IsNullOrWhiteSpace($env:GOOGLE_API_KEY)
    groq_api_key_present = -not [string]::IsNullOrWhiteSpace($env:GROQ_API_KEY)
    ollama_api_key_present = -not [string]::IsNullOrWhiteSpace($env:OLLAMA_API_KEY)
}

$validation = @{
    status = "audited"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    expected_computer_name = $ExpectedComputerName
    commit_sha = (& git rev-parse HEAD).Trim()
    commands = $commands
    versions = $versions
    gh_authenticated = [bool]$ghAuthenticated
    ollama_local_endpoint = "http://127.0.0.1:11434"
    local_models = $localModels
    free_local_candidates = $freeLocalCandidates
    cloud_credential_presence = $cloudCredentialFlags
    policy = @{
        opencode_allowed = $true
        ollama_local_allowed = $true
        paid_cloud_provider_allowed = $false
        codex_allowed_without_explicit_approval = $false
        api_key_usage_allowed_without_explicit_approval = $false
    }
    secrets_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$validation | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Free OpenCode stack audit PASS."
Write-Host "opencode_available=$($commands.opencode)"
Write-Host "ollama_available=$($commands.ollama)"
Write-Host "free_local_model_count=$($freeLocalCandidates.Count)"
Write-Host "paid_cloud_provider_allowed=False"
