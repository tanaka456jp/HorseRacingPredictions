# One-command JRA-VAN free-trial pipeline

For the local Windows PC with JV-Link installed:

Smoke only:

    powershell -ExecutionPolicy Bypass -File scripts/run_jravan_trial.ps1 -BaseHistory data/raw/19860105-20210731_race_result.csv

After the smoke passes, run the full setup acquisition:

    powershell -ExecutionPolicy Bypass -File scripts/run_jravan_trial.ps1 -BaseHistory data/raw/19860105-20210731_race_result.csv -Full

The full flow is:

1. JV-Link doctor
2. bounded RA/SE smoke
3. setup RA/SE raw acquisition
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
