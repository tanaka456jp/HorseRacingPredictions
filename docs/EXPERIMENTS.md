# Experiments

## Shared validation

Historical source: Kaggle `takamotoki/jra-horse-racing-dataset`.

All listed ROI values use final historical win odds and are therefore
**research-only**, not verified live profitability.

OOS period for v0-v3: 2018-02-03 through 2021-07-31.
Rows: 167,166. Races: 12,114. Walk-forward folds: 19.

## v0 — normalized binary-logit baseline

- Commit: `43970ea9649333028e1c97db6415055ee6789b26`
- Run: `36150124890`

| Metric | v0 | Market |
|---|---:|---:|
| Brier | 0.064329 | 0.058098 |
| Log loss | 0.239325 | 0.206064 |
| Research ROI | -67.20% | — |

**Decision: REJECTED.**

## v1 — race-softmax probability conversion

- Commit: `e3bc519ae925586d651026fe0792be27434cc8c5`
- Run: `36150569697`

| Metric | v1 | v0 | Market |
|---|---:|---:|---:|
| Brier | 0.062840 | 0.064329 | 0.058098 |
| Log loss | 0.231272 | 0.239325 | 0.206064 |
| Research ROI | -22.96% | -67.20% | — |

**Decision: REJECTED AS PRODUCTION; KEEP AS BASELINE.**

## v2 — pre-race context categories

- Commit: `09f2c49045e3c38b1f1856046697694cdda981a3`
- Run: `36151543415`
- Added: racecourse, turf/dirt, weather, track condition, sex
- One-hot encoding with unknown-category handling

| Metric | v2 | v1 | Market |
|---|---:|---:|---:|
| Brier | 0.062810 | 0.062840 | 0.058098 |
| Log loss | 0.230918 | 0.231272 | 0.206064 |
| Research ROI | -17.73% | -22.96% | — |

- Bets: 1,237
- Profit: -¥95,080
- Max drawdown: 97.89%

The direction is positive, but the improvement is too small and bankroll risk
remains unacceptable.

**Decision: REJECTED AS PRODUCTION; KEEP THE CONTEXT FEATURES.**

## v3 — context-conditioned historical aptitude

Keep all v2 behavior and add only past information:

- horse × surface historical record
- horse × racecourse historical record
- horse × 200m distance bucket historical record
- jockey × racecourse historical record
- trainer × racecourse historical record

For each group, create prior starts, prior win rate, prior average finish and
days since that exact context was previously seen. Same-day outcomes are
excluded by daily aggregation before cumulative history is computed.
