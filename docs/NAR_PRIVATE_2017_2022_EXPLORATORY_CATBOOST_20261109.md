# 2017–2022 NAR private CatBoost: first real retrospective rank screening

**Date:** 2026-11-09. **Scope:** PC② only, approved 2017-01 through
2022-12 local official NAR monthly ZIPs. This is *exploratory* research,
NOT real-money performance and NOT independent out-of-sample validation.
The 2023–2024 sealed OOS and the 2025–2026 protected final holdout were
NOT opened. No source data, individual horse or race IDs, odds, scores,
model binary or private ZIPs were sent to GitHub Actions.

## Real-data evidence

[PC② research run #42612165495](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42612165495)
**SUCCESS** after CatBoost 1.2.10 was installed in a dedicated
PC② D-drive virtual environment. The global Python environment and
original monthly NAR archives were not modified.

| Read-only aggregate | Observed |
| --- | ---: |
| Original races 2017–2022 | 89,654 |
| Predeclared banei outside flat scope | 10,223 |
| Original 2017–2022 flat population | 79,431 |
| Unresolved flat results (kept in denominator) | 851 |
| Retrospectively evaluable **2017–2021 fitting** races | 65,173 |
| Retrospectively evaluable **2022 tuning** races | 13,402 |
| Additional 2022 flat races with unavailable outcomes | 138 |
| All 2022 flat races for missingness bounds | 13,540 |
| 2022 top1 winner hit rate (evaluable only) | **29.4508%** |
| Same race population, uniformly random horse baseline | 10.5158% |
| 2022 top-three picks' finished top-three precision | 49.4180% |
| Fourth, independent top-three pick's finished podium rate | 34.4352% |
| Whole-2022 worst case (all missing = not correct) | **29.1507%** |
| Whole-2022 best case (all missing = correct) | 30.1699% |

**Important:** a historical top-three finish is different from a
place ticket's paid positions when 5–7 horses are offered. The models
were separately fitted on winner and *numeric top-three finisher*
labels, not on a 5–7-runner place-tote dividend indicator.

The observed fourth-pick metric is a horse chosen **outside the first
model's predicted top three**. It is NOT independently shown to be
an unpopular horse or a high-odds outsider: market price/popularity
was not used in the historical 2017–2022 dataset.

## How these observations were obtained

`scripts/screen_nar_pc2_exploratory_status_aware.py` streams 72 local
ZIPs, reconstructs chronological horse histories by official horse
name and birthdate, then passes the 2017–2022 *post-event* targets to
`src/horse_racing_predictions/nar_exploratory_rank_screen.py`.
Only earlier DATE race results enter five prior-form feature columns:
past starts, win rate, top-three rate, average numeric finish, and
days since last start. Current race rank, odds, popularity, payback
and same-day results are excluded from predictors.

Two independent CatBoost classifiers use 2017–2021 fitting data.
The model's choice of the first three and a separate fourth pick is
then evaluated retrospectively on 2022. The 2022 set is explicitly
a **model-selection/tuning** period, NOT an untouched final test.

A non-default `allow_explicit_exploratory_sample=True` mode allows
*research-only* retrospective comparison of the 78,580 completed
result records when 851 source outcomes remain unresolved.
The original STRICT source readiness and official settlement rules
remain HOLD; this mode **never** sets training/EV/rights approvals.

## Non-negotiable limitations

- **No contemporary preoff roster/forecast snapshots or historical
  preoff odds:** no genuine 2017–2022 bet could have been placed or
  audited using this retrospective pipeline alone.
- **Unresolved 851 races:** 2022 missingness bounds keep all 138
  unscored races in the full 2022 denominator. The 2017–21
  fitting sample is still retrospectively selected for results
  that can be interpreted; not a random missingness mechanism.
- **No wagering ROI:** hit rate above uniform random is *not*
  sufficient for positive expected value after takeout, transaction
  costs, and bookmaker/pari-mutuel prices.
- **No independent final evaluation:** protected 2023–24
  independent OOS and 2025–26 final holdout stay sealed; no
  repeated feature/threshold tuning using those data.
- **No authorized customer posting:** model and source data remain
  private.

A stronger simple pre-date historical win-rate baseline and a paired
whole-race-day descriptive bootstrap were added afterward for the
same 2022 tuning sample. This **must be evaluated before any
claim that CatBoost is better than basic past-performance form**.
Any 2022 bootstrap interval is descriptive and cannot substitute
for untouched independent OOS or genuine prospective net EV.

**Research outcome so far:** there is a genuine historical
*rank-predictive signal*, but a **positive after-cost betting
expectation has NOT been demonstrated**.
