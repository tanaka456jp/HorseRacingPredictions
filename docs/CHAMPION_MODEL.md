# Champion Model

Current Champion: **v7 CatBoost recent-form model**.

Validation evidence:

- OOS period: 2018-02-03 through 2021-07-31
- rows: 167,166
- races: 12,114
- walk-forward folds: 19
- Brier: 0.061549
- Log loss: 0.223565
- research-only ROI: -1.90%

v8 calibration was rejected.
v9 forward strategy selection abstained on every evaluable fold.
v10 lagged market-history features slightly improved probability metrics but
materially worsened the research-only EV result, so v10 is not promoted.

## Artifact policy

The repository stores artifact-building code, tests and manifests, but not the
large trained CatBoost binary.

Run the Champion training script to create:

- model.cbm
- manifest.json

The manifest freezes:

- model/experiment version
- exact feature column order
- categorical column list
- train period
- source identifier
- OOS validation metrics

Future inference must load this manifest together with the native model.
