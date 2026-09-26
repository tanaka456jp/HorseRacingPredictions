# Champion Inference to Paper Trading

The current forward pipeline is intentionally split into three auditable steps.

1. Train/save Champion artifact

   python scripts/train_champion_artifact.py --output-dir artifacts/champion_v7

2. Generate future race probabilities

   python scripts/predict_future_races.py --history data/history.csv --entries data/future_entries.csv --artifact-dir artifacts/champion_v7 --output artifacts/future_predictions.csv

3. Join predictions to timestamped pre-race odds

   python scripts/prepare_paper_input.py --predictions artifacts/future_predictions.csv --odds data/manual/odds_snapshots.csv --output artifacts/paper_input.csv

Then run the existing Paper Trading CLI:

   python scripts/run_paper_session.py --input artifacts/paper_input.csv --ledger data/paper/paper_trading.sqlite3 --bankroll-yen 100000

The prediction model does not consume the target race's current odds.
Odds are joined only after probability inference to calculate EV and create
Paper Trading evidence.

The preparation step chooses the latest odds snapshot observed no later than
the decision timestamp and rejects decisions at or after scheduled post time.
