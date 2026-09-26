# HorseRacingPredictions

JRA競馬を対象に、**的中率ではなく期待値（EV）**を中心として、予測・レース選別・Paper Trading・実績蓄積・モデル改善を繰り返す研究/運用基盤です。

## Core policy

- 初期開発・検証・運用は無料データと無料ツールを優先する。
- 有料情報は、無料構成とForward Paperで価値が確認でき、追加費用以上の再現可能な改善が見込める場合に限り検討する。
- 人気順をそのまま買うのではなく、モデル推定確率と市場オッズの差を評価する。
- EV・信頼度・リスク条件を満たさない場合は **買わない**。
- 未来情報リークを禁止する。
- 実馬券購入は無効。LiveBrokerはハード停止したまま。

## Current Champion

**v7 CatBoost recent-form model**

- OOS period: 2018-02-03 through 2021-07-31
- rows: 167,166
- races: 12,114
- walk-forward folds: 19
- Brier: 0.061549
- Log loss: 0.223565
- research-only ROI: -1.90%

v8 calibration and v10 lagged market-history challenger were rejected.
v9 forward threshold selection selected **no bet** on every evaluable fold.

The current Champion is a probability-research baseline, not evidence of live profitability.

## Implemented

- leakage-safe historical feature generation
- CatBoost race probability model with race-level normalization
- expanding Walk-Forward validation
- Brier / Log Loss / calibration / EV diagnostics
- Champion / Challenger promotion gate
- Fractional Kelly staking
- race and daily exposure caps
- immutable timestamped pre-race odds evidence
- PaperBroker and SQLite ledger
- prediction-to-paper-bet evidence linkage
- manual/timestamped odds CSV provider
- FREE-FIRST paid-provider gate
- Champion native artifact save/load
- future entries inference
- prediction + odds -> Paper input bridge
- one-command Forward Paper runner
- Streamlit dashboard baseline
- LiveBroker disabled

## Architecture

```
Approved / User-supplied Data
  -> Normalized History + Future Entries
  -> Leakage-safe Features
  -> Champion Probability Model
  -> Timestamped Pre-race Odds
  -> EV / Risk Rules
  -> PaperBroker
  -> Immutable Ledger
  -> Evaluation / Dashboard
  -> Champion / Challenger Loop
```

## Validation workflow

Model changes on `feature/**` run a short historical **Smoke** automatically.

The expensive full historical research run is explicit-only:

- workflow dispatch, or
- update `research/full_run_request.txt` on an experiment branch.

This avoids duplicate 19-fold CatBoost runs.

## Development quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,research]"
pytest -q
```

## Build the frozen Champion artifact

```powershell
python scripts/train_champion_artifact.py `
  --start 2017-01-01 `
  --end 2021-07-31 `
  --output-dir artifacts/champion_v7
```

This produces:

- `model.cbm`
- `manifest.json`

## Forward Paper run

Once an approved/up-to-date history file, future entries file and timestamped odds snapshots are available:

```powershell
python scripts/run_forward_paper.py `
  --history data/history.csv `
  --entries data/future_entries.csv `
  --artifact-dir artifacts/champion_v7 `
  --odds data/manual/odds_snapshots.csv `
  --bankroll-yen 100000
```

The runner generates probabilities, joins only eligible pre-race odds, applies EV/Kelly and exposure caps, records Paper orders, and never calls LiveBroker.

## Current data limitation

The currently approved free historical research source ends on **2021-07-31**.
The system therefore does not silently scrape recent JRA/netkeiba pages.

Forward Paper validation needs either:

- an approved current free source, or
- a user-supplied current history / timestamped odds input.

JRA-VAN Data Lab remains a reserved paid provider and is disabled by the FREE-FIRST gate.

See `docs/CHAMPION_MODEL.md`, `docs/FORWARD_PIPELINE.md`, `docs/PAPER_TRADING_EVIDENCE.md`, and `docs/CURRENT_DATA_GAP.md` for details.
