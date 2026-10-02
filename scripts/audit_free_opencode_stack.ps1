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


function Get-OpenCodeCandidates {
    $candidates = @()

    $command = Get-Command opencode -ErrorAction SilentlyContinue
    if ($null -ne $command -and -not [string]::IsNullOrWhiteSpace([string]$command.Source)) {
        $candidates += [string]$command.Source
    }

    if (Get-Command npm -ErrorAction SilentlyContinue) {
        try {
            $npmPrefix = (& npm prefix -g 2>$null | Select-Object -First 1)
            if (-not [string]::IsNullOrWhiteSpace([string]$npmPrefix)) {
                $candidates += (Join-Path ([string]$npmPrefix) "opencode.cmd")
                $candidates += (Join-Path ([string]$npmPrefix) "opencode.exe")
            }
        } catch {}
    }

    $machineCandidates = @(
        "C:\ProgramData\chocolatey\bin\opencode.exe",
        "C:\ProgramData\chocolatey\bin\opencode.cmd",
        "C:\Program Files\OpenCode\opencode.exe",
        "C:\Program Files\opencode\opencode.exe"
    )
    $candidates += $machineCandidates

    if (Test-Path -LiteralPath "C:\Users" -PathType Container) {
        foreach ($profile in Get-ChildItem -LiteralPath "C:\Users" -Directory -ErrorAction SilentlyContinue) {
            $root = $profile.FullName
            $relativeCandidates = @(
                "AppData\Roaming\npm\opencode.cmd",
                "AppData\Roaming\npm\opencode.exe",
                "AppData\Local\pnpm\opencode.cmd",
                "AppData\Local\pnpm\opencode.exe",
                ".bun\bin\opencode.exe",
                ".bun\bin\opencode.cmd",
                "scoop\shims\opencode.exe",
                "scoop\shims\opencode.cmd",
                ".local\bin\opencode.exe",
                ".local\bin\opencode.cmd",
                ".opencode\bin\opencode.exe",
                ".opencode\bin\opencode.cmd",
                "AppData\Local\Microsoft\WinGet\Links\opencode.exe",
                "AppData\Local\Microsoft\WinGet\Links\opencode.cmd",
                "AppData\Local\mise\shims\opencode.exe",
                "AppData\Local\mise\shims\opencode.cmd",
                ".local\share\mise\shims\opencode.exe",
                ".local\share\mise\shims\opencode.cmd",
                "AppData\Local\Programs\opencode\opencode.exe",
                "AppData\Local\Programs\OpenCode\opencode.exe"
            )
            foreach ($relative in $relativeCandidates) {
                $candidates += (Join-Path $root $relative)
            }
        }
    }

    $candidates += Get-LoadedUserEnvironmentCandidates

    return @(
        $candidates |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace([string]$_) -and
            (Test-Path -LiteralPath $_ -PathType Leaf)
        } |
        Select-Object -Unique
    )
}


function Get-LoadedUserEnvironmentCandidates {
    $candidates = @()
    $profileListRoot = "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"

    $sidKeys = @(
        Get-ChildItem -Path "Registry::HKEY_USERS" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.PSChildName -match "^S-1-5-21-" -and
            $_.PSChildName -notmatch "_Classes$"
        }
    )

    foreach ($sidKey in $sidKeys) {
        $sid = [string]$sidKey.PSChildName
        $profilePath = $null
        try {
            $profileProps = Get-ItemProperty -LiteralPath (Join-Path $profileListRoot $sid) -ErrorAction Stop
            $profilePath = [Environment]::ExpandEnvironmentVariables([string]$profileProps.ProfileImagePath)
        } catch {}

        if ([string]::IsNullOrWhiteSpace([string]$profilePath)) {
            continue
        }

        $envPathValue = $null
        try {
            $envProps = Get-ItemProperty -LiteralPath ("Registry::HKEY_USERS\$sid\Environment") -ErrorAction Stop
            $envPathValue = [string]$envProps.Path
        } catch {}

        if ([string]::IsNullOrWhiteSpace($envPathValue)) {
            continue
        }

        $appData = Join-Path $profilePath "AppData\Roaming"
        $localAppData = Join-Path $profilePath "AppData\Local"

        foreach ($entryRaw in ($envPathValue -split ";")) {
            $entry = ([string]$entryRaw).Trim().Trim('"')
            if ([string]::IsNullOrWhiteSpace($entry)) {
                continue
            }

            $entry = $entry.Replace("%USERPROFILE%", $profilePath)
            $entry = $entry.Replace("%APPDATA%", $appData)
            $entry = $entry.Replace("%LOCALAPPDATA%", $localAppData)
            $entry = [Environment]::ExpandEnvironmentVariables($entry)

            foreach ($name in @(
                "opencode.exe",
                "opencode.cmd",
                "opencode.ps1",
                "opencode2.exe",
                "opencode2.cmd",
                "opencode2.ps1"
            )) {
                $candidate = Join-Path $entry $name
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    $candidates += $candidate
                }
            }
        }
    }

    return @($candidates | Select-Object -Unique)
}

function Get-OpenCodeInstalledAppMatches {
    $matches = @()
    $roots = @(
        "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    )

    foreach ($sidKey in @(
        Get-ChildItem -Path "Registry::HKEY_USERS" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.PSChildName -match "^S-1-5-21-" -and
            $_.PSChildName -notmatch "_Classes$"
        }
    )) {
        $roots += "Registry::HKEY_USERS\$($sidKey.PSChildName)\Software\Microsoft\Windows\CurrentVersion\Uninstall"
    }

    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }
        foreach ($key in Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue) {
            try {
                $props = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction Stop
                $displayName = [string]$props.DisplayName
                if ($displayName -match "(?i)opencode") {
                    $matches += @{
                        display_name = $displayName
                        display_version = [string]$props.DisplayVersion
                        install_location = [string]$props.InstallLocation
                        display_icon = [string]$props.DisplayIcon
                        uninstall_string = [string]$props.UninstallString
                        quiet_uninstall_string = [string]$props.QuietUninstallString
                    }
                }
            } catch {}
        }
    }

    return $matches
}


function Get-ExecutablePathFromCommandText {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }
    $trimmed = $Text.Trim()
    if ($trimmed -match '^\s*"([^"]+\.exe)"') {
        return [string]$Matches[1]
    }
    if ($trimmed -match '^\s*([^, ]+\.exe)') {
        return [string]$Matches[1]
    }
    return $null
}

function Get-OpenCodeInstalledAppDerivedCandidates {
    param($InstalledApps)

    $candidates = @()
    foreach ($app in @($InstalledApps)) {
        $roots = @()

        if (-not [string]::IsNullOrWhiteSpace([string]$app.install_location)) {
            $roots += [string]$app.install_location
        }

        foreach ($text in @(
            [string]$app.display_icon,
            [string]$app.uninstall_string,
            [string]$app.quiet_uninstall_string
        )) {
            $exe = Get-ExecutablePathFromCommandText -Text $text
            if (-not [string]::IsNullOrWhiteSpace($exe)) {
                try {
                    $roots += (Split-Path -Parent $exe)
                } catch {}
            }
        }

        foreach ($root in ($roots | Where-Object {
            -not [string]::IsNullOrWhiteSpace([string]$_)
        } | Select-Object -Unique)) {
            foreach ($relative in @(
                "bin\opencode.exe",
                "bin\opencode.cmd",
                "cli\opencode.exe",
                "cli\opencode.cmd",
                "resources\bin\opencode.exe",
                "resources\bin\opencode.cmd",
                "resources\cli\opencode.exe",
                "resources\cli\opencode.cmd"
            )) {
                $candidate = Join-Path $root $relative
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    $candidates += $candidate
                }
            }
        }
    }

    return @($candidates | Select-Object -Unique)
}

function Get-OpenCodeProcessMatches {
    $matches = @()
    foreach ($proc in Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -match "(?i)opencode"
    }) {
        $path = $null
        try {
            $path = [string]$proc.Path
        } catch {}
        $matches += @{
            process_name = [string]$proc.ProcessName
            path = $path
        }
    }
    return $matches
}

function Test-OpenCodeCliCandidate {
    param([string]$Path)

    try {
        $output = & $Path --version 2>$null
        $exitCode = [int]$LASTEXITCODE
        $first = [string]($output | Select-Object -First 1)
        return @{
            path = $Path
            runnable = ($exitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($first))
            version = if ($exitCode -eq 0) { $first } else { $null }
        }
    } catch {
        return @{
            path = $Path
            runnable = $false
            version = $null
        }
    }
}

function Resolve-OpenCodePath {
    foreach ($candidate in (Get-OpenCodeCandidates)) {
        $test = Test-OpenCodeCliCandidate -Path $candidate
        if ($test.runnable) {
            return [string]$candidate
        }
    }
    return $null
}

function Sanitize-UserPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }
    return ($Path -replace '^C:\\Users\\[^\\]+\\', 'C:\Users\<USER>\')
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

$openCodeInstalledApps = @(Get-OpenCodeInstalledAppMatches)
$openCodeProcesses = @(Get-OpenCodeProcessMatches)
$installedAppDerivedCandidates = @(
    Get-OpenCodeInstalledAppDerivedCandidates -InstalledApps $openCodeInstalledApps
)

$openCodeCandidateResults = @(
    (@(Get-OpenCodeCandidates) + $installedAppDerivedCandidates) |
    Select-Object -Unique |
    ForEach-Object {
        Test-OpenCodeCliCandidate -Path $_
    }
)
$resolvedOpenCodePath = $null
foreach ($candidateResult in $openCodeCandidateResults) {
    if ($candidateResult.runnable) {
        $resolvedOpenCodePath = [string]$candidateResult.path
        break
    }
}

$commands = @{
    git = Test-CommandAvailable "git"
    gh = Test-CommandAvailable "gh"
    node = Test-CommandAvailable "node"
    npm = Test-CommandAvailable "npm"
    opencode = -not [string]::IsNullOrWhiteSpace([string]$resolvedOpenCodePath)
    ollama = Test-CommandAvailable "ollama"
    python = Test-CommandAvailable "python"
}

$versions = @{
    git = Get-VersionLine -Name "git" -Arguments @("--version")
    gh = Get-VersionLine -Name "gh" -Arguments @("--version")
    node = Get-VersionLine -Name "node" -Arguments @("--version")
    npm = Get-VersionLine -Name "npm" -Arguments @("--version")
    opencode = $null
    ollama = Get-VersionLine -Name "ollama" -Arguments @("--version")
    python = Get-VersionLine -Name "python" -Arguments @("--version")
}

if ($commands.opencode) {
    try {
        $output = & $resolvedOpenCodePath --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $versions.opencode = [string]($output | Select-Object -First 1)
        }
    } catch {}
}

$localModels = @()
$ollamaApiReachable = $false
try {
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 5
    $ollamaApiReachable = $true
    foreach ($item in @($tags.models)) {
        $name = [string]$item.name
        if (-not [string]::IsNullOrWhiteSpace($name)) {
            $localModels += @{
                name = $name
                size = if ($null -ne $item.size) { [int64]$item.size } else { $null }
                cloud_like_name = ($name -match "(?i)(cloud|remote)")
            }
        }
    }
} catch {
    $ollamaApiReachable = $false
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
    opencode_discovery = @{
        found = $commands.opencode
        source_path_sanitized = Sanitize-UserPath -Path $resolvedOpenCodePath
        candidates = @(
            $openCodeCandidateResults | ForEach-Object {
                @{
                    path_sanitized = Sanitize-UserPath -Path $_.path
                    runnable = [bool]$_.runnable
                    version = $_.version
                }
            }
        )
        installed_app_matches = @(
            $openCodeInstalledApps | ForEach-Object {
                @{
                    display_name = $_.display_name
                    display_version = $_.display_version
                    install_location_sanitized = Sanitize-UserPath -Path $_.install_location
                    display_icon_sanitized = Sanitize-UserPath -Path $_.display_icon
                    uninstall_string_sanitized = Sanitize-UserPath -Path $_.uninstall_string
                    quiet_uninstall_string_sanitized = Sanitize-UserPath -Path $_.quiet_uninstall_string
                }
            }
        )
        running_process_matches = @(
            $openCodeProcesses | ForEach-Object {
                @{
                    process_name = $_.process_name
                    path_sanitized = Sanitize-UserPath -Path $_.path
                }
            }
        )
    }
    gh_authenticated = [bool]$ghAuthenticated
    ollama_local_endpoint = "http://127.0.0.1:11434"
    ollama_api_reachable = [bool]$ollamaApiReachable
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
Write-Host "opencode_source=$(Sanitize-UserPath -Path $resolvedOpenCodePath)"
Write-Host "ollama_available=$($commands.ollama)"
Write-Host "ollama_api_reachable=$ollamaApiReachable"
Write-Host "free_local_model_count=$($freeLocalCandidates.Count)"
Write-Host "paid_cloud_provider_allowed=False"
