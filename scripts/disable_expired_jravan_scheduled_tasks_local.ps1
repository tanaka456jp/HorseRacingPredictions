<#
Local-only safe incident response for expired JRA-VAN Data Lab trial.

No GitHub runner, JV-Link, network request or browser automation.
Default: inspect exact task names only. -Disable: disable these tasks.
Optional -StopRunning: also stop only currently running named tasks after
-Disable (never terminate Edge itself or touch user data).
Run on the Windows computer where the repeated expiry tabs appeared.
#>
[CmdletBinding()]
param(
    [switch]$Disable,
    [switch]$StopRunning
)
$ErrorActionPreference = "Stop"
if ($StopRunning -and -not $Disable) {
    throw "StopRunning requires -Disable to avoid accidental disruption."
}

$taskNames = @(
    "HorseRacingPredictions-ForwardPaper",
    "HorseRacingPredictions-RealtimeSettlement",
    "HorseRacingPredictions-IncrementalSettlement",
    "HorseRacingPredictions-ResidualReconcile"
)

foreach ($taskName in $taskNames) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host "NOT_INSTALLED: $taskName"
        continue
    }
    if ($Disable) {
        Disable-ScheduledTask -TaskName $taskName -ErrorAction Stop | Out-Null
        if ($StopRunning -and $task.State -eq "Running") {
            Stop-ScheduledTask -TaskName $taskName -ErrorAction Stop
        }
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    }
    $details = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction Stop
    Write-Host ("{0} | state={1} | lastResult={2}" -f
        $taskName, $task.State, $details.LastTaskResult)
}
Write-Host "No local horse-racing files, databases, JV-Link settings or Edge tabs were modified."
