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

### v0 result

| Metric | Model v0 | Final-odds market benchmark |
|---|---:|---:|
| Brier | 0.064329 | 0.058098 |
| Log loss | 0.239325 | 0.206064 |

- Bets: 553
- Profit: **-¥95,090**
- ROI: **-67.20%**
- Max drawdown: **95.09%**

**Decision: REJECTED.**

## v1 — race-softmax probability conversion

- Commit: `e3bc519ae925586d651026fe0792be27434cc8c5`
- GitHub Actions run: `36150569697`
- Same OOS period, folds, features, EV threshold and bankroll rules as v0
- Single change: convert logistic utility scores with race-level softmax

### v1 result

| Metric | Model v1 | Model v0 | Market |
|---|---:|---:|---:|
| Brier | 0.062840 | 0.064329 | 0.058098 |
| Log loss | 0.231272 | 0.239325 | 0.206064 |

- Bets: 1,056
- Stake: ¥414,100
- Payout: ¥319,030
- Profit: **-¥95,070**
- ROI: **-22.96%**
- Ending bankroll: ¥4,930
- Max drawdown: **97.24%**

v1 materially improves probability quality and research ROI versus v0, but
still underperforms the final-odds market benchmark and still loses heavily.

**Decision: REJECTED AS PRODUCTION MODEL; KEEP AS NEW BASELINE.**

## v2 — add pre-race context categories

Keep v1 race-softmax and add only information known before the race:

- racecourse
- surface (turf/dirt)
- weather
- track condition
- horse sex

These are one-hot encoded inside the baseline pipeline. This experiment tests
whether race context explains enough conditional performance to improve the
OOS probability distribution without using market odds as a model feature.
