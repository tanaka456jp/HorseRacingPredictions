# Paper Trading CSV CLI

This CLI allows the current evidence/risk pipeline to be exercised without a
live data subscription or real-money execution.

Required input columns:

- race_id
- horse_id
- horse_name
- predicted_win_probability
- decimal_odds
- confidence
- model_version
- observed_at
- predicted_at
- scheduled_post_time

Optional columns:

- source
- source_reference

All timestamps must include a timezone offset.

Example PowerShell command:

    python scripts/run_paper_session.py --input data/manual/paper_predictions.csv --ledger data/paper/paper_trading.sqlite3 --bankroll-yen 100000

The runner stores every prediction, verifies the exact pre-race quote, applies
EV/Kelly selection, enforces shared race/day exposure caps, records accepted
PaperBroker orders, subtracts open stake from uncommitted bankroll, and never
invokes LiveBroker.

Settlement is intentionally a separate later step.
