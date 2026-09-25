# Experiments

## Shared validation

Historical source: Kaggle `takamotoki/jra-horse-racing-dataset`.
ROI values below use final historical win odds and are **research-only**.

OOS period: 2018-02-03 through 2021-07-31.
Rows: 167,166. Races: 12,114. Walk-forward folds: 19.
Market benchmark: Brier 0.058098, Log loss 0.206064.

| Version | Main change | Brier | Log loss | Research ROI |
|---|---|---:|---:|---:|
| v0 | normalized sigmoid | 0.064329 | 0.239325 | -67.20% |
| v1 | race softmax | 0.062840 | 0.231272 | -22.96% |
| v2 | pre-race context categories | 0.062810 | 0.230918 | -17.73% |
| v3 | context-conditioned histories | 0.062556 | 0.229346 | -22.09% |
| v4 | forward temperature calibration | 0.062666 | 0.229649 | -17.89% |
| v5 | CatBoost nonlinear model | **0.062190** | **0.227285** | -19.61% |

## v5 conclusion

Commit: `b34f82f6a651eb97c8fd9c8623f063a54c566b2a`.
Run: `36152828769`.

- Bets: 1,275
- Stake: ¥485,000
- Payout: ¥389,910
- Profit: -¥95,090
- Research ROI: -19.61%
- Max drawdown: 95.97%

CatBoost improves both Brier and Log loss versus the linear v3 baseline.
However, the EV-selected betting result remains strongly negative.

**Decision: KEEP CATBOOST AS THE NEW PROBABILITY BASELINE, NOT AS A
PRODUCTION BETTING MODEL.**

## v6 — OOS loss-structure diagnostics

Keep the v5 predictions unchanged. Do not tune the model.

Produce post-hoc research diagnostics for:

- EV bands
- decimal-odds bands
- race-confidence bands
- model probability minus market-implied probability bands
- an EV-threshold sweep

Each segment records count, wins, predicted win rate, actual win rate,
calibration error and flat-bet ROI.

This is explicitly diagnostic. Any threshold or filter discovered here must
later be selected using only prior folds and evaluated on later unseen folds
before it can become a strategy rule.
