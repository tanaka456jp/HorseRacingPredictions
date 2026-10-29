# Incident: repeated Microsoft Edge Data Lab trial-expired pages — 2026-10-29

**Evidence:** User-supplied screenshot from a Windows desktop shown via mobile client. Microsoft Edge displays many open tabs/windows entitled `DataLab.お試し期間終了 | JRA-VAN`. This screenshot alone **does not prove which process opened them**.

## Confirmed risk in repository

The repo still had a Windows local scheduler installer which defines four named tasks:
- `HorseRacingPredictions-ForwardPaper`: daily 09:17–17:47, every 30 minutes
- `HorseRacingPredictions-RealtimeSettlement`: daily 18:17
- `HorseRacingPredictions-IncrementalSettlement`: daily 20:23
- `HorseRacingPredictions-ResidualReconcile`: daily 21:37

The task wrapper invoked JRA-VAN runner scripts, some of which used Python JV-Link COM for new data. **This is a credible repeat-launch mechanism**, but the actual task installation/running state, process ancestry and attribution on the pictured PC have not been observed. Do not assume these tasks caused every Edge tab. JRA-VAN's own software, a separate Windows startup entry, or repeated manual clicks are also possible.

## Fail-closed code changes (Draft PR #142 only)

- `src/horse_racing_predictions/jravan.py`: normal *real* COM factory always raises `JRA_VAN_TRIAL_EXPIRED_LIVE_COM_DISABLED` **before creating a Windows COM object**. Fake injected test clients remain usable for synthetic regression. Restoring live service would require a separate reviewed design and subscription/licence proof; there is no environment variable bypass.
- `src/horse_racing_predictions/jravan_runtime.py`: runtime inspection now produces a disabled status without COM Dispatch or browser UI.
- `scripts/run_local_jravan_scheduled_task.ps1`: writes a local `disabled_trial_expired` heartbeat and exits safely before spawning a child process. Does not delete old data or paper records.
- `scripts/install_local_jravan_scheduler.ps1`: refuses to reinstall or overwrite old JRA-VAN scheduled task entries.
- `scripts/disable_expired_jravan_scheduled_tasks_local.ps1`: manual-only, exact-name Windows task scanner/disable helper. It is **not** scheduled, run automatically, dispatched remotely or invoked in CI. Without `-Disable` it only lists status; with `-Disable` it disables future starts. With `-Disable -StopRunning` it also requests the Windows Task Scheduler to stop those named currently running tasks. No Edge process kill or file deletion.
- `tests/test_expired_jravan_popup_loop_guard.py`: synthetic tests ensure the new fail-closed behavior.

**This PR branch does not immediately alter installed tasks on the user's Windows computer.** Existing tasks pointing to an older checked-out `main` may still invoke old scripts. The user must disable them on the actual affected Windows PC; do not claim the screenshot's issue is resolved solely by GitHub commits.

## Immediate operator procedure (local PowerShell, no GitHub runner required)

With appropriate local Task Scheduler permissions:

```powershell
$names = @(
    'HorseRacingPredictions-ForwardPaper',
    'HorseRacingPredictions-RealtimeSettlement',
    'HorseRacingPredictions-IncrementalSettlement',
    'HorseRacingPredictions-ResidualReconcile'
)
foreach ($name in $names) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        Disable-ScheduledTask -TaskName $name
        Get-ScheduledTask -TaskName $name |
            Select-Object TaskName, State
    }
}
```

Optional local-only tool when this branch is present: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\disable_expired_jravan_scheduled_tasks_local.ps1 -Disable`.

Do not delete private archives, disable unrelated automation, blindly terminate all Edge processes or reinstall JV-Link. After the currently running processes stop, close the repeated trial-expired tabs and observe whether they return. If they do, investigate Windows Task Scheduler history, startup entries and the process tree **without reading protected racing datasets**. Only sanitized task-name / last-run / status / process name information should leave the PC.

## Project continuation

Free-only development proceeds with offline fictional fixtures and independently rights-cleared alternative data. No new Data Lab/JV-Link connection attempts, no paid subscription, no note publication and no use of the previously refused archival source-byte reader. Model positive expected value remains unproven.
