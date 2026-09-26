# Project Status

## Current phase

**Phase 2 — Forward Paper Validation Foundation**

The research core is established. The project is now focused on producing auditable forward predictions and Paper Trading evidence without enabling real-money execution.

## Current Champion

**v7 CatBoost recent-form model**

Validation:

- OOS period: 2018-02-03 through 2021-07-31
- 167,166 rows
- 12,114 races
- 19 Walk-Forward folds
- Brier: 0.061549
- Log loss: 0.223565
- research-only ROI: -1.90%

Rejected challengers:

- v8 forward isotonic calibration: probability metrics worsened
- v10 lagged market history: Brier/Log Loss improved only marginally while research ROI fell to -32.83%

Strategy result:

- v9 forward-only EV threshold selection evaluated 16 future folds
- active betting folds: 0
- abstain rate: 100%

This means the project does **not** currently claim a reusable profitable betting threshold.

## Implemented

### Research / modeling

- free-data historical adapter and provenance policy
- leakage-safe historical features
- race context and recent-form features
- CatBoost Champion
- expanding chronological Walk-Forward
- race-level probability normalization
- Brier / Log Loss / calibration diagnostics
- EV-band and longshot-overconfidence diagnostics
- Champion / Challenger promotion gate
- forward-only strategy selection

### Risk / execution

- Fractional Kelly sizing
- per-race exposure cap
- per-day exposure cap
- zero-bet / abstention support
- PaperBroker
- LiveBroker hard-disabled

### Evidence / ledger

- timezone-aware pre-race odds snapshots
- immutable odds evidence
- exact prediction-to-odds linkage
- Paper bet-to-prediction linkage
- SQLite ledger
- no-bet predictions retained to avoid selection bias

### Forward operation

- FREE-FIRST odds provider boundary
- manual/timestamped CSV odds provider
- Champion CatBoost native artifact save/load
- manifest with frozen feature order and validation metadata
- future entries normalization and inference
- predictions + pre-race odds -> Paper input bridge
- one-command Forward Paper runner

## Champion artifact validation

GitHub-hosted validation confirmed:

- CatBoost native save/load roundtrip: PASS
- frozen v7 full-period training: PASS
- saved artifact reload: PASS
- synthetic future-race inference: PASS
- race probabilities sum to 1.0: PASS
- artifact publication: PASS

The trained binary is an artifact, not committed to Git.

## CI / research execution

- normal CI: GitHub-hosted `ubuntu-latest`
- model feature pushes: short Historical Research Smoke
- full 19-fold research: explicit trigger only
- concurrency cancellation enabled
- main updates do not automatically repeat full research

## Current blocking dependency

The approved free historical source ends on **2021-07-31**.

No recent scraper-derived source has been approved as the canonical production input. JRA-VAN Data Lab is a technically viable formal provider but remains disabled because it is paid.

Therefore current-date Forward Paper validation requires an approved or user-supplied recent history source plus timestamped pre-race odds.

## Next

1. Obtain an approved/up-to-date history input without violating FREE-FIRST.
2. Run the frozen Champion on genuinely future races.
3. Store every prediction and eligible/no-bet decision before post time.
4. Accumulate a meaningful forward Paper sample.
5. Evaluate calibration, Brier, Log Loss, ROI, drawdown and EV bands on forward evidence.
6. Keep LiveBroker disabled unless forward Paper evidence supports progression.
7. Consider paid data only after its incremental value can be tested against the free baseline.

## Paid-data rule

Paid data is not introduced merely because a historical backtest looks attractive.
A paid source must show reproducible incremental predictive/economic value that exceeds its full cost.
