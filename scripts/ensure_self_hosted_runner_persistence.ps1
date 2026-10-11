param(
    [switch]$Repair,
    [string]$ExpectedRunnerName = "Office-PC-01-HorseRacingPredictions"
)

$ErrorActionPreference = "Stop"

function Get-RunnerRoot {
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_WORKSPACE)) {
        $workspace = [System.IO.Path]::GetFullPath($env:GITHUB_WORKSPACE)
        $repoParent = Split-Path -LiteralPath $workspace -Parent
        $workRoot = Split-Path -LiteralPath $repoParent -Parent
        $runnerRoot = Split-Path -LiteralPath $workRoot -Parent
        if (
            (Test-Path -LiteralPath (Join-Path $runnerRoot ".runner") -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $runnerRoot "run.cmd") -PathType Leaf)
        ) {
            return $runnerRoot
        }
    }

    $candidateRoots = @(
        (Join-Path $env:USERPROFILE "actions-runner"),
        (Join-Path $env:USERPROFILE "github-actions-runner"),
        "C:\actions-runner",
        "C:\GitHubActions"
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    foreach ($root in $candidateRoots) {
        if (
            (Test-Path -LiteralPath (Join-Path $root ".runner") -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $root "run.cmd") -PathType Leaf)
        ) {
            return $root
        }
    }
    throw "Unable to locate the registered GitHub Actions runner root."
}

function Read-RunnerName([string]$RunnerRoot) {
    $config = Get-Content -LiteralPath (Join-Path $RunnerRoot ".runner") -Raw | ConvertFrom-Json
    $name = [string]$config.agentName
    if ([string]::IsNullOrWhiteSpace($name)) {
        throw ".runner does not contain agentName."
    }
    return $name
}

function Get-MatchingRunnerService([string]$RunnerRoot, [string]$RunnerName) {
    $escapedRoot = [Regex]::Escape($RunnerRoot)
    return @(Get-CimInstance Win32_Service | Where-Object {
        (
            $_.Name -like "actions.runner.*" -and
            ($_.Name -like "*$RunnerName*" -or $_.DisplayName -like "*$RunnerName*")
        ) -or (
            -not [string]::IsNullOrWhiteSpace([string]$_.PathName) -and
            [string]$_.PathName -match $escapedRoot
        )
    })
}

$runnerRoot = Get-RunnerRoot
$runnerName = Read-RunnerName -RunnerRoot $runnerRoot
if ($runnerName -ne $ExpectedRunnerName) {
    throw "Refusing persistence change: discovered runner '$runnerName' does not match expected '$ExpectedRunnerName'."
}

$services = Get-MatchingRunnerService -RunnerRoot $runnerRoot -RunnerName $runnerName
$result = [ordered]@{
    runner_name = $runnerName
    runner_root = $runnerRoot
    service_count = $services.Count
    service_names = @($services | ForEach-Object { $_.Name })
    service_states = @($services | ForEach-Object { $_.State })
    repair_requested = [bool]$Repair
    persistence_mode = $null
    repair_status = "not_requested"
}

if ($services.Count -gt 0) {
    $result.persistence_mode = "windows_service"
    if ($Repair) {
        try {
            foreach ($service in $services) {
                Set-Service -Name $service.Name -StartupType Automatic
                if ($service.State -ne "Running") { Start-Service -Name $service.Name }
            }
            $result.repair_status = "service_automatic"
        }
        catch {
            $result.repair_status = "service_repair_failed"
            $result.error = $_.Exception.Message
            $result | ConvertTo-Json -Depth 6
            exit 2
        }
    }
}
else {
    $result.persistence_mode = "hkcu_logon_wrapper"
    if ($Repair) {
        $source = Join-Path $PSScriptRoot "start_self_hosted_runner_if_needed.ps1"
        $wrapper = Join-Path $runnerRoot "start-horseracing-runner-if-needed.ps1"
        Copy-Item -LiteralPath $source -Destination $wrapper -Force
        $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
        if (-not (Test-Path -LiteralPath $runKey)) { New-Item -Path $runKey -Force | Out-Null }
        $command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $wrapper + '" -RunnerRoot "' + $runnerRoot + '"'
        New-ItemProperty -Path $runKey -Name "HorseRacingPredictionsGitHubRunner" -PropertyType String -Value $command -Force | Out-Null
        $result.wrapper = $wrapper
        $result.repair_status = "hkcu_logon_installed"
    }
}

$result | ConvertTo-Json -Depth 6