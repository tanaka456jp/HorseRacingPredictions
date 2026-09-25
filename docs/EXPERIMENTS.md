# Experiments

## Shared validation

Historical source: Kaggle `takamotoki/jra-horse-racing-dataset`.

All listed ROI values use final historical win odds and are therefore
**research-only**, not verified live profitability.

OOS period for v0-v4: 2018-02-03 through 2021-07-31.
Rows: 167,166. Races: 12,114. Walk-forward folds: 19.

## v0

Normalized binary-logit baseline.

- Brier: 0.064329
- Log loss: 0.239325
- Research ROI: -67.20%

**REJECTED.**

## v1

Race-level softmax replaces normalized independent sigmoids.

- Brier: 0.062840
- Log loss: 0.231272
- Research ROI: -22.96%

**REJECTED AS PRODUCTION; KEPT AS BASELINE.**

## v2

Added pre-race racecourse/surface/weather/track/sex categories.

- Brier: 0.062810
- Log loss: 0.230918
- Research ROI: -17.73%

**REJECTED AS PRODUCTION; CONTEXT FEATURES KEPT.**

## v3

Added prior-only contextual aptitude histories:

- horse × surface
- horse × course
- horse × 200m distance bucket
- jockey × course
- trainer × course

Run: `36151962433`

- Brier: **0.062556**
- Log loss: **0.229346**
- Market Brier: 0.058098
- Market Log loss: 0.206064
- Bets: 1,370
- Research ROI: **-22.09%**
- Max drawdown: **96.59%**

v3 improves probability quality but worsens the EV betting result versus v2.
This indicates probability calibration is a separate problem from ranking and
raw predictive accuracy.

**REJECTED AS PRODUCTION; CONTEXTUAL HISTORY KEPT FOR NEXT TEST.**

## v4 — forward temperature calibration

No feature additions.

Within each Walk-Forward fold:

1. reserve the most recent 20 training dates as calibration data
2. fit the model only on earlier dates
3. choose temperature on the calibration period
4. freeze that temperature
5. predict the future test period

This prevents test-period information from influencing calibration and directly
tests whether over/under-confidence is responsible for poor EV selection.
