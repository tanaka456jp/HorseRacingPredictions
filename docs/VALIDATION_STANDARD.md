# Validation Standard

## Two different ROI classes

HorseRacingPredictions never treats every backtest ROI as equivalent.

### Research-only ROI

Research-only includes any result using:

- final historical win odds
- post-race payout information
- estimated combination odds
- reconstructed odds without a timestamp proving availability before post time

These results are useful for model research, threshold exploration and detecting obvious failures. They are **not evidence of stable live profitability**.

### Verified paper ROI

ROI may be labeled verified only when:

1. the prediction was saved before post time
2. the exact odds used for the decision were captured before post time
3. the model version and features were frozen at prediction time
4. no result-derived feature was available to the model
5. settlement used the official result/payout
6. skipped races and rejected bets are retained, not silently removed

## Profitability gate

Paid data must not be purchased because a research-only backtest looks profitable.

The paid-data gate requires stable results from forward paper trading and then small-capital live validation. A paid source must subsequently show reproducible incremental benefit exceeding its full cost.

## Why this exists

Historical racing datasets frequently contain final odds or only winning-combination payouts. Using those values as though they were available at the actual bet decision time can materially overstate expected value and ROI.

This project therefore records odds provenance as part of every backtest summary.
