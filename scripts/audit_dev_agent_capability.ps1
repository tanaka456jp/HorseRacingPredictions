param(
    [string]$ExpectedComputerName = "DESKTOP-MVV1FD4",
    [string]$ValidationOutput = "artifacts/dev_agent_capability_validation.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Refusing dev-agent capability audit on $($env:COMPUTERNAME); expected $ExpectedComputerName."
}

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-CommandVersion {
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
        $line = ($output | Select-Object -First 1)
        if ($null -eq $line) {
            return $null
        }
        return [string]$line
    } catch {
        return $null
    }
}

function Test-ExitZero {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    if (-not (Test-CommandAvailable -Name $Name)) {
        return $false
    }

    try {
        & $Name @Arguments *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$commands = @{
    git = Test-CommandAvailable "git"
    gh = Test-CommandAvailable "gh"
    codex = Test-CommandAvailable "codex"
    opencode = Test-CommandAvailable "opencode"
    claude = Test-CommandAvailable "claude"
    aider = Test-CommandAvailable "aider"
    python = Test-CommandAvailable "python"
    pwsh = Test-CommandAvailable "pwsh"
    powershell = Test-CommandAvailable "powershell.exe"
    ollama = Test-CommandAvailable "ollama"
}

$auth = @{
    gh_authenticated = Test-ExitZero -Name "gh" -Arguments @(
        "auth", "status", "--hostname", "github.com"
    )
    codex_authenticated = Test-ExitZero -Name "codex" -Arguments @(
        "login", "status"
    )
}

$gitIdentity = @{
    user_name_configured = $false
    user_email_configured = $false
}
if ($commands.git) {
    try {
        $name = (& git config --get user.name 2>$null)
        $gitIdentity.user_name_configured = (
            -not [string]::IsNullOrWhiteSpace([string]$name)
        )
    } catch {}
    try {
        $email = (& git config --get user.email 2>$null)
        $gitIdentity.user_email_configured = (
            -not [string]::IsNullOrWhiteSpace([string]$email)
        )
    } catch {}
}

$preferredAgent = $null
foreach ($candidate in @("codex", "opencode", "claude", "aider")) {
    if ($commands[$candidate]) {
        $preferredAgent = $candidate
        break
    }
}

$versions = @{
    git = Get-CommandVersion -Name "git" -Arguments @("--version")
    gh = Get-CommandVersion -Name "gh" -Arguments @("--version")
    codex = Get-CommandVersion -Name "codex" -Arguments @("--version")
    opencode = Get-CommandVersion -Name "opencode" -Arguments @("--version")
    claude = Get-CommandVersion -Name "claude" -Arguments @("--version")
    aider = Get-CommandVersion -Name "aider" -Arguments @("--version")
    python = Get-CommandVersion -Name "python" -Arguments @("--version")
}

$validation = @{
    status = "audited"
    validated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    computer_name = $env:COMPUTERNAME
    expected_computer_name = $ExpectedComputerName
    commit_sha = (& git rev-parse HEAD).Trim()
    commands = $commands
    auth = $auth
    git_identity = $gitIdentity
    preferred_agent = $preferredAgent
    versions = $versions
    secrets_included = $false
    raw_auth_output_included = $false
    live_execution_enabled = $false
}

$validationPath = Join-Path $ProjectRoot $ValidationOutput
$validationDir = Split-Path -Parent $validationPath
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$validation | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $validationPath -Encoding UTF8

Write-Host "Dev-agent capability audit PASS."
Write-Host "preferred_agent=$preferredAgent"
Write-Host "codex_available=$($commands.codex)"
Write-Host "codex_authenticated=$($auth.codex_authenticated)"
Write-Host "gh_available=$($commands.gh)"
Write-Host "gh_authenticated=$($auth.gh_authenticated)"
Write-Host "git_identity_ready=$($gitIdentity.user_name_configured -and $gitIdentity.user_email_configured)"
