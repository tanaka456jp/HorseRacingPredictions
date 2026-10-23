# JRA Friday note: real-data readiness audit

**Status: offline diagnostics only. NOT a publication approval or an odds-free
model training/prediction pipeline.** The note magazine was created on PC159N
on 2026-10-24 (note ID `m18cae5764be3`). This does not resolve model/data
gaps or authorize any real-weekend issue.

This draft PR deliberately does not access the network, JRA-VAN, netkeiba,
the final 2025–2026 holdout, credentials, runners, Windows services, or note.
It reports only candidate file hashes, counts and reason codes.

## What to supply, when lawful source data exists

Use a separate working directory with **reviewed** input files. Do not commit
raw race-card or licensed-provider data into a public repository. Four candidate
inputs are accepted by the read-only audit:

1. `rights.json`: `{"schemaVersion":1,"providerId":"name","datasetKind":"historical-form","publicationPermission":true,"personalUseOnly":false,"capturedAt":"2026-10-29T14:00:00+09:00","permissionBasisUrl":"https://rights.example/terms"}`. This is only a self-attested candidate and must **never** be taken as permission without reviewing the actual terms and permitted scope. Use a real permission URL, not an example.
2. `races.json`: `{"schemaVersion":1,"issueDate":"2026-10-30","observedAt":"2026-10-30T14:00:00+09:00","expectedRaceIds":["JRA-..."]}`. The IDs must match a complete independently verified Saturday/Sunday weekend manifest. The actual race count varies with the schedule; do not force 72 or invent IDs.
3. `model.json`: `{"schemaVersion":1,"modelId":"frozen-model-id","frozenAt":"2026-10-29T21:00:00+09:00","artifactSha256":"64_lowercase_hex","featureNames":["prior_form","distance_fit"],"oddsFreeClaim":true}`. Hash and feature names must be matched against the **real frozen binary** and actual inference code by an independent reviewer. An editable file cannot prove this.
4. `forecast.json`: the exact curated `odds_free_friday_article.render_friday_jra_article` schema with all true JRA entrants, their *actual* pre-race model strengths and frozen independent upside scores, pre-cutoff factors and URLs. A JSON `input_approved_for_research` boolean cannot prove authorization. Run this only after Friday source/field availability has been established.

The `publicationPermission` claim does not grant rights. In particular,
[JRA-VAN terms §7](https://jra-van.jp/info/rule.html) generally prohibit
non-private reuse of service data under the normal contract. The separate
[JRA-VAN posting guideline](https://jra-van.jp/info/post_guide.html)
sets a limited exception for certain *permitted* captures/tables but
explicitly says that **JV-Link data cannot be posted**. Do not transform
a right to post a screenshot into a right to bulk publish dataset values or
forecasting features. Separately agreed, documentary rights require review.
The rights checker rejects ordinary JRA-VAN/JV-Link source claims by default.

## Run (does not write, scrape or publish)

```powershell
python scripts/audit_jra_friday_publication_inputs.py --issue-date 2026-10-30
```

Add `--forecast-json`, `--source-rights-json`, `--race-manifest-json`,
and `--model-manifest-json` pointing to actual reviewed candidate files
when they exist. Optional `--champion-artifact-dir` reads an existing
`model.cbm` / `manifest.json` pair and cross-checks the SHA-256 digest,
feature-column sequence, model identity and creation/freeze chronology
against the candidate model manifest; it never downloads or retrains a
model. It is **only a byte-integrity check**, not proof that the model
actually runs on current fields or has been validated as odds-free.

The repository's historical v7 training script uses `win_odds` to filter
training rows (`dropna`, then `win_odds > 1.0`) although current-target
odds are not model input features. That market-dependent selection needs
separate provenance / sampling-bias review before declaring an all-stages
odds-independent forecast. The v7 artifact's history cutoff of 2021-07-31
also leaves a multi-year gap. `predict_future_entries` rejects a >14-day
history gap by default, so **do not override it** to force forecasts for
2026. Acquiring approved up-to-date history and actual upcoming entries
comes before genuine inference.
 The output is JSON; **exit status is 2 by design**,
including when all four files are structurally consistent. This is a
preliminary auditor, **not** the independent verifier. It never returns
`publicationAuthorized: true` and cannot sign the Business Platform
verification receipt.

## Strict non-market research sample preparation (2026-10-24)

`src/horse_racing_predictions/odds_free_training.py` now implements
`prepare_strict_odds_free_training_sample`. This is a **research-only**
pure function: it normalizes approved local source frames after dropping all
odds, popularity, payout, betting and market fields **before row selection or
feature engineering**. It does not run CatBoost, evaluate performance, load a
2025–2026 final holdout or generate real forecasts. The test suite asserts
identical resulting sample and features when market columns are removed,
reordered in value, made null or populated with implausible odds.

- Rejects any input containing post-2024 rows, even if the caller requests
  an earlier training cutoff; no protected holdout access.
- Rejects ambiguous duplicate horse/race IDs, blank identities, incomplete
  results, races without exactly one winner, and impossible field sizes.
- Uses only historical finish positions as *labels* and past-race inputs for
  feature engineering. Target-race outcomes may never appear as prediction
  features.
- Does not reuse `scripts/train_champion_artifact.py`, which uses market
  values to select rows and writes a v7 manifest with predetermined historical
  evaluation values. New model promotion must require a separately executed
  **genuine** chronological validation, never copied metrics.

To actually produce a new trained candidate, the next independent steps are
documented verified training-source provenance; an explicit train/validation
split (through 2024 only, with protected final holdout untouched); retraining
via a separate no-market pipeline; calibration/feature freeze and source
rights. Until then it is *not* a frozen model or evidence of EV > 0.

## Release gates still required

- independently permitted, timestamped data with rights for the intended use;
- exact JRA weekend manifest and complete *real* horse identities;
- genuine frozen odds/popularity-independent model and pre-race feature trace;
- rank 1/2/3 plus one distinct condition-upside outsider per race, linked to
  legitimate pre-race evidence;
- no 2025–2026 protected holdout leakage, no artificially invented scores;
- Business Platform's five independent evidence checks, trusted Ed25519
  verification receipt, publisher preflight, PC159N authenticated note proof;
- successful one-time article and actual magazine membership receipt;
- only then authorize one Friday-only scheduled note posting cycle.

The old Champion v7 model is not proven profitable: its documented
2018–2021 research-only ROI is **-1.90%**. The separate odds-free forecast
magazine is **not** a claim of positive betting expected value.
