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
| v3 | context-conditioned histories | **0.062556** | **0.229346** | -22.09% |
| v4 | forward temperature calibration | 0.062666 | 0.229649 | -17.89% |

## v4 conclusion

Run: `36152406362`.

Temperature range across folds:

- minimum: 0.8881
- median: 0.9261
- maximum: 1.0504

The forward-only calibration did not improve Brier or Log loss versus v3.
Research ROI improved versus v3 but remains deeply negative, and final odds make
that ROI unsuitable as live-profit evidence.

**Decision: REJECT TEMPERATURE CALIBRATION. Retain v3 as the probability baseline.**

## v5 — CatBoost model-only replacement

Keep the v3 feature set and race softmax, but replace the linear logistic model
with CatBoost.

Why:

- race effects are nonlinear
- distance and carried weight can interact
- horse aptitude depends on surface/course context
- jockey/trainer histories interact with venue
- categorical conditions should not be forced into a purely additive linear form

No market odds are added to model inputs. No paid data is introduced.
