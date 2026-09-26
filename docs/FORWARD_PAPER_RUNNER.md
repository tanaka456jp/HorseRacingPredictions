# One-command Forward Paper Runner

After a Champion artifact has been built, the forward Paper pipeline can be
executed in one command.

    python scripts/run_forward_paper.py --history data/history.csv --entries data/future_entries.csv --artifact-dir artifacts/champion_v7 --odds data/manual/odds_snapshots.csv --bankroll-yen 100000

The runner performs:

1. Champion artifact load
2. leakage-safe feature generation for future entries
3. race-normalized win probability inference
4. selection of the latest odds snapshot available by the decision time
5. immutable prediction/evidence creation
6. EV/Kelly decision
7. shared race/day exposure caps
8. PaperBroker execution only
9. SQLite ledger persistence
10. JSON/CSV output for audit

It never invokes LiveBroker.

Current limitation: the approved free historical source ends in 2021, so a
current forward run still requires an approved or user-supplied up-to-date
history file. The code does not silently scrape an unapproved source.


## Local JRA-VAN free-trial runner

When the one-month local JRA-VAN free trial is active, a Windows self-hosted
runner can prepare the three Forward Paper inputs without purchasing a data
contract:

1. reuse `data/jravan/full/current_history.csv`,
2. capture current-week RA/SE locally and derive future entries,
3. capture realtime `0B31` win odds for races that are still safely pre-race,
4. run the frozen Champion and PaperBroker only when every active entry has a
   valid timestamped odds snapshot.

Use `.github/workflows/jravan-forward-paper-self-hosted.yml`. The workflow
fails/defer-closes when inputs are incomplete and uploads only sanitized counts.
