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


## Smoke acceptance vs full-history acceptance

The current-week smoke is a transport/parser test, not a completed-history
quality gate. Current-week RACE data may contain future or not-yet-final races.

Therefore smoke parsing uses completed_only=False and succeeds when RA/SE
records can be matched and parsed structurally.

Full historical acquisition remains strict: completed_only=True is retained,
so rows without final finish position and valid final win odds are excluded
before Current History Intake.


## Free-trial setup authentication fallback

Some free-trial environments allow current-week/normal data with
JVInit("UNKNOWN") but return JVOpen=-301 for setup option 3/4.

When the historical setup open returns exactly -301, the pipeline now retries
with option 1 using a recent 365-day from_time. Other JVOpen errors are not
hidden and still fail closed.

The fallback is recorded explicitly:

- acquisition_mode=recent_normal_fallback
- effective_option=1
- effective_from_time=<recent one-year timestamp>
- fallback_reason=<the -301 setup authentication reason>
- history_gap_days=<gap from the 2021 base>

The merged file is therefore marked status=ready_recent_history_gap rather than
ready. This is usable for forward research/Paper Trading data collection, but
it is not treated as equivalent to a continuous 2021-2026 history.

FREE-FIRST remains in force. A paid Data Lab subscription is not required just
to continue the present research workflow.


## Resume after a completed acquisition

If JV-Link acquisition and RA/SE parsing already completed but a later CSV
decode/intake step failed, do not reacquire hundreds of thousands of records.

Run:

    RUN_JRAVAN_RESUME.cmd

Resume reuses:

    data/jravan/full/parsed_history.csv

and restarts from base-history loading / Current History Intake only.

Japanese CSV loading tries UTF-8 BOM, CP932, Shift-JIS, EUC-JP and UTF-8, and
the JRA history loader only accepts an encoding when the required canonical
columns can be normalized.

Successful resume output:

    data/jravan/full/current_history.csv


## Winner-conflict quarantine

The raw/parsed JRA-VAN files are preserved exactly as acquired/parsed.

Before Current History Intake, supplemental races are classified by the number
of rows with finish_position=1:

- exactly one winner: kept for the single-winner probability model
- zero winners: quarantined from current_history
- multiple winners: quarantined from current_history

This protects the race-softmax single-winner model invariant without deleting
source evidence. Multiple-winner cases may represent dead heats; zero-winner
cases may indicate incomplete/unsupported race records. The pipeline does not
guess which explanation applies.

Audit output:

    artifacts/jravan_full/winner_conflict_filter.json

The report records counts, excluded row counts, and exact race IDs. Full and
Resume console output also shows zero_winner_races and
multiple_winner_races.
