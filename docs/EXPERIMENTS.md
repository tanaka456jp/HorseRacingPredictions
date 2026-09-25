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
| v5 | CatBoost nonlinear model | 0.062190 | 0.227285 | -19.61% |
| v7 | recent form / pace history | **0.061549** | **0.223565** | **-1.90%** |

## v6 — OOS loss-structure diagnostics

Commit: `62d6df6b963ce82fdc2a05eb867631794bcd7025`.
Run: `36155468906`.

The CatBoost probability model is materially overconfident on market longshots.
Raising the EV threshold makes the selected population worse rather than better.

Examples from the post-hoc diagnostic:

- EV 1.15-1.25: predicted win rate 7.88%, actual 5.05%
- EV 1.50-2.00: predicted 6.40%, actual 2.96%
- EV >=3.00: predicted 5.18%, actual 0.76%
- model minus market >=10pt: predicted 22.88%, actual 8.47%
- flat ¥100 ROI at EV>=1.15: -30.61%
- flat ¥100 ROI at EV>=3.00: -37.69%

This demonstrates that the immediate problem is probability estimation for
supposed value longshots, not an insufficiently high EV cutoff.

**Decision: DO NOT TUNE THE EV THRESHOLD ON THIS SAMPLE. Improve horse-state
features first, then re-evaluate on unseen future folds.**

## v7 — recent form, pace history and race-relative context

Commit: `f0f0bd7151fc822b0ccb7fb4efb0422f2bb9500d`.
Run: `36157815918`.

Merged to `main` after CI and historical research both passed.

Keep the v5 CatBoost model and add only information available before the target
race:

- field size
- relative post position
- carried-weight difference versus race mean
- horse-weight difference versus race mean
- race class and graded-race category
- prior 3/5 race average finish
- prior 3/5 race win and top-3 rate
- prior 3/5 race average last-3F
- prior best last-3F over five races
- prior 3/5 race early/late corner-position ratios
- short-versus-medium recent finish trend

Current-race last-3F and corner positions remain forbidden as model inputs.
They are used only after a one-day shift as historical features.


### v7 result

- Brier: 0.061549
- Log loss: 0.223565
- Research bets: 2,063
- Stake: ¥4,991,300
- Payout: ¥4,896,250
- Profit: -¥95,050
- Research ROI: **-1.90%**
- Max drawdown: 99.70%

This is a material probability-quality improvement over v5 and the first model
to approach break-even on the research-only final-odds simulation.

The result is **not live-profit evidence** because historical final odds are not
a timestamped pre-race quote. The extreme drawdown also prevents production use.

**Decision: ACCEPT THE v7 FEATURES AS THE NEW RESEARCH BASELINE.**

## v8 — forward-only isotonic calibration

Keep the v7 model and features unchanged.

For each Walk-Forward fold:

1. reserve the latest portion of the training period as a calibration window,
2. fit CatBoost only on earlier dates,
3. fit an isotonic calibrator on raw win probabilities versus actual outcomes,
4. apply it to the future test fold,
5. renormalize probabilities within each race.

No odds are used by the calibrator. The goal is specifically to shrink the
nonlinear longshot overconfidence identified by v6 without tuning an EV cutoff
on the same test sample.

## v9 — forward-only strategy rule selection

Branch: `feature/v9-forward-validation`.

Keep the accepted v7 CatBoost probability model unchanged.

For every target OOS fold, select an EV threshold using only earlier OOS folds.
A threshold is eligible only when:

- it belongs to the predeclared threshold grid,
- at least 200 prior bets are available,
- prior flat-bet ROI is positive.

If no threshold satisfies the rule, the strategy abstains for that target fold.

This tests whether the system can learn **when not to bet** without choosing a
threshold from the same future fold used to report performance. The result
remains research-only because the Kaggle price is final historical odds.

