# Project Status

## Current phase

Phase 1 — Research Core

## Main objective

人気馬を単純に追うのではなく、無料データから推定した勝率と市場オッズの差を使って期待値のあるレース・馬券だけを選択する。

## Implemented

- EV engine
- Fractional Kelly staking
- Race skip rules
- PaperBroker
- SQLite ledger
- Streamlit dashboard baseline
- Champion / Challenger promotion gate
- Free CSV adapter
- Leakage-safe expanding Walk-Forward splitter
- Baseline logistic probability model
- Race-level probability normalization
- Live betting hard-disabled

## Validation

- Original Phase 1 core: 4 tests PASS
- Walk-Forward / baseline modeling additions: 2 tests PASS locally before commit

## Next

1. Select a legally usable free historical dataset
2. Add explicit source/license/provenance metadata
3. Normalize race/horse/result schemas
4. Build leakage audit
5. Train baseline model by chronological folds
6. Compare model probability against market-implied probability
7. Simulate Paper bets only where EV threshold is exceeded
8. Report ROI, calibration, log loss, Brier score and max drawdown
9. Add feature families incrementally: surface, distance, course, weight, jockey, pedigree, pace
10. Promote only OOS improvements

## Paid-data rule

Paid data is not introduced until the free-data system demonstrates stable real profitability and a paid source shows reproducible incremental profit exceeding its cost.

## CI policy

This public repository uses GitHub-hosted `ubuntu-latest` as the default CI runner.

- push to `main`: run tests
- pull request to `main`: run tests
- manual dispatch: supported
- concurrency cancellation: enabled to prevent stale runs piling up
- timeout: 15 minutes per test job
- self-hosted runners are not the default for this repository
\n