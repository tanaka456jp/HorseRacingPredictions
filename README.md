# HorseRacingPredictions

JRA競馬を対象に、**的中率ではなく期待値（EV）**を中心として、予測・レース選別・仮想購入・実績蓄積・モデル改善を繰り返す研究/運用基盤です。

## Core policy

- 初期開発・検証・運用は無料データと無料ツールのみで行う。
- 有料情報は、無料構成で実収益が安定し、追加費用以上のOOS期待値改善が再現できる場合に限り検討する。
- 人気順をそのまま買うのではなく、モデル推定確率と市場オッズの乖離を探す。
- 全レースを買わず、EV・信頼度・リスク条件を満たす場合だけ購入候補にする。
- 未来情報リークを禁止する。
- 実馬券購入はPaper TradingとOOS検証を通過するまで無効。

## Architecture

```
Free Data Providers
  -> Raw / Normalized Data
  -> Feature Store
  -> Probability Models
  -> Calibration
  -> Race / Ticket Simulation
  -> EV Engine
  -> Race Selector
  -> Stake Optimizer
  -> Paper Broker
  -> Result Ledger
  -> Dashboard
  -> Champion / Challenger Learning Loop
```

## Phase 1 status

- [x] Prediction domain model
- [x] EV calculation
- [x] Fractional Kelly staking
- [x] Race skip rules
- [x] Paper broker
- [x] SQLite prediction/bet/result ledger
- [x] Baseline Streamlit dashboard
- [x] Champion/Challenger promotion gate
- [x] Generic free CSV adapter
- [x] Unit tests
- [ ] Real historical dataset ingestion
- [ ] Baseline probability model
- [ ] Time-series Walk-Forward backtest

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q
python -m horse_racing_predictions.demo
streamlit run src/horse_racing_predictions/dashboard.py
```

Live betting is intentionally disabled in Phase 1.
