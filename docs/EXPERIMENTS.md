# Experiments

## v0 — normalized binary-logit baseline

- Commit: `43970ea9649333028e1c97db6415055ee6789b26`
- GitHub Actions run: `36150124890`
- Historical source: Kaggle `takamotoki/jra-horse-racing-dataset`
- OOS period: 2018-02-03 to 2021-07-31
- OOS rows: 167,166
- Races: 12,114
- Walk-forward folds: 19
- Odds evidence: final historical win odds
- ROI status: research only / not live verified

### Probability quality

| Metric | Model v0 | Final-odds market benchmark |
|---|---:|---:|
| Brier | 0.064329 | 0.058098 |
| Log loss | 0.239325 | 0.206064 |

The market benchmark is materially stronger than v0. The model does not yet
justify betting against the market.

### Betting result

- Bets: 553
- Stake: ¥141,500
- Payout: ¥46,410
- Profit: **-¥95,090**
- ROI: **-67.20%**
- Ending bankroll from ¥100,000: **¥4,910**
- Max drawdown: **95.09%**

### Decision

**REJECTED.**

This is the first failure record in the learning loop. It is retained rather
than hidden or tuned away.

## v1 — race-softmax probability conversion

Change only the race probability conversion:

- v0: independent binary sigmoid probabilities, then divide by race total
- v1: logistic utility score, then race-level softmax

The feature set, date windows, EV threshold and bankroll rules remain unchanged.
The purpose is to isolate whether the probability-conversion method improves
OOS probability quality and betting behavior.
