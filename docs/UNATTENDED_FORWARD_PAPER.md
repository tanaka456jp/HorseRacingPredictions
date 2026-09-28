# Unattended Forward Paper Schedule

The unattended schedule is designed to accumulate prospective evidence without
requiring chat prompts and without enabling real-money execution.

All times below are Japan Standard Time (JST).

- 09:00-17:00, hourly: capture the bounded pre-race decision window and run
  Champion Paper plus frozen Residual v12 Paper v1.
- 18:00: settle eligible Paper bets from JRA-VAN 0B12.
- 20:00: refresh completed local history incrementally and settle any remaining
  eligible Paper bets.
- 21:30: reconcile pending Residual v12 shadow results.

The forward decision window remains strictly greater than 10 and less than or
equal to 70 minutes before scheduled post time. Residual v12 Paper v1 also
rejects odds older than 10 minutes when the Paper decision is actually created.

Schedules run every day rather than only on weekends so special weekday JRA
meetings are not silently omitted. On days without eligible races the forward
pipeline exits without creating Paper decisions.

Workflows that access JV-Link or mutate local JRA/Paper state share the
`horse-racing-jravan-self-hosted` concurrency group with
`cancel-in-progress: false`. This serializes access instead of cancelling an
in-progress state update.

Horse-level data, odds, predictions, results, model caches, and SQLite ledgers
remain local. GitHub artifacts are sanitized aggregate validation only.
LiveBroker remains disabled.
