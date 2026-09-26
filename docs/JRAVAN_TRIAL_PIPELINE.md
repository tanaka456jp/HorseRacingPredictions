# One-command JRA-VAN free-trial pipeline

For the local Windows PC with JV-Link installed:

Smoke only:

    powershell -ExecutionPolicy Bypass -File scripts/run_jravan_trial.ps1

After the smoke passes, run the full setup acquisition:

    powershell -ExecutionPolicy Bypass -File scripts/run_jravan_trial.ps1 -Full

The script installs pywin32 and kagglehub automatically. During the full run,
the approved 1986-2021 Kaggle base history is downloaded automatically. An
explicit -BaseHistory path can still be supplied when an existing local copy
should be used.

The full flow is:

1. JV-Link COM/runtime preflight
2. one bounded current-week RA/SE smoke (single JVOpen)
3. setup RA/SE raw acquisition for full mode
4. official-spec RA/SE parsing
5. discard race dates at/before the approved base cutoff
6. provenance manifest creation
7. fail-closed Current History Intake
8. current_history.csv creation

The full acquisition uses JVOpen dataspec RACE with setup option 3 or 4.
The from_time parameter is a Data Lab data-provision timestamp, not a race-date
end filter. The parser therefore filters the completed RA/SE records by actual
race date after acquisition.

Output files remain under ignored data/ directories. Raw JV-Data is not
committed or redistributed.

The final current history can then be supplied to scripts/run_forward_paper.py.


JVOpen may return before setup files finish downloading. The acquisition layer
therefore polls JVStatus until the reported downloaded-file count reaches
JVOpen download_count before it starts JVGets.


## Why the smoke uses only one JVOpen

A repeated current-week JVOpen in the same bootstrap sequence can cause the
second connection to report a much larger pending download count. The smoke
therefore does not invoke the Doctor internally.

The bootstrap performs COM/runtime validation first, then the smoke performs
exactly one current-week RACE open with fromtime 00000000000000 and option 2.
Full mode performs the historical setup open only after the smoke succeeds.
