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


## Post-event 2022 official win dividend sensitivity

The PC② exploratory workflow now joins actual final 2022 official win
dividends privately, strictly **after** fitting and scoring, to the same
13,402 evaluable historical 2022 races and smoothed prior-win baseline.
It models one hypothetical 100-yen WIN stake per evaluable race, subtracts
stake from gross paid returns and reports an additional adverse-missingness
sensitivity treating every unevaluable 2022 flat race as a 100-yen loss.
Paired whole-day bootstrap estimates the retrospective model-minus-baseline
return difference; it is descriptive only.

This is **post-event historical simulation**, not verified advance prediction,
actual purchases, extra transaction cost audit, independent OOS, or proven
positive after-cost expected value. Source identities, individual results,
model binaries and raw licensed files remain on PC②. Missing or contradictory
selected official payout causes HOLD; it is never silently treated as zero.
2023–2024 and 2025–2026 sealed periods are untouched.
Quote aggregate returns only after a confirmed successful PC② run of the
new commit, not on the strength of code or fictional tests.


## Predeclared win + separate fourth-place-candidate scenario

The same 2022 evaluation population is also screened using the earlier
stated two-ticket option: 100 yen hypothetical win on first-ranked
model horse, plus 100 yen hypothetical place on the separate fourth
candidate outside the model's top three. Actual official **place** payouts,
not numeric third-place finishes, determine settlement. With 5–7 offered
runners, numeric third finish may return zero place payout.
One 200-yen combined stake is the denominator for each evaluable race;
a separate deliberately adverse full-flat stress charges 200 yen to every
non-evaluable race and assumes zero dividend. No favorable race is
selected by observed payouts. Race-day bootstrap bands are retrospective
and descriptive, not independent OOS confidence in true profitability.
This is NOT a genuine pre-off wager or positive-EV authorization.

## Real retrospective payout observations — PC②, 2026-11-09

**Verified actual PC② 2017–2021 fit / 2022 selection-period run:**
[Actions #42628497493](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42628497493),
commit `2fadee316640e44647801199bc8645601ba6e187` (**SUCCESS**).
Runs are reproducible through the strict 72-month private D-drive ZIPs,
but source data, individual horse/race records and model binaries were
not published. Preoff racecards/market prices were not independently
verified. This does **not** demonstrate deployable EV.

- 2022 evaluable flat races: **13,402**, with **138** other flat races
  retained in the full 13,540-race scope.
- Single 100-yen hypothetical model WIN: stake **1,340,200 yen**,
  official return **1,022,160 yen**, net **-318,040 yen**,
  return on stake **-23.7308%**.
- Same 100-yen historical-form comparator WIN: **-21.1357%**.
  Model-minus-form net ROI **-2.5951 percentage points**; paired racing
  day bootstrap descriptive 95% interval **[-8.1322, +2.4439] points**.
- Separate fourth-pick 100-yen hypothetical PLACE: stake **1,340,200 yen**,
  official return **1,004,020 yen**, net **-336,180 yen**,
  return on stake **-25.0843%**.
- Predeclared paired model WIN + fourth-pick PLACE: 200 yen per race,
  stake **2,680,400 yen**, official combined return **2,026,180 yen**,
  net **-654,220 yen**, ROI **-24.4076%**. Descriptive 95% race-day
  bootstrap ROI interval **[-26.4668%, -22.1488%]**.
- Adverse missingness stress assuming a stake and zero return in all
  13,540 flat races: model WIN **-24.5081%**, combined WIN+PLACE
  **-25.1780%**. This deliberately pessimistic scenario does not mean
  cancelled/unoffered bets were in fact placed.
- No additional payment-platform fees or operational costs were validated.
  Official tote dividends already reflect the payout system; there was
  **no actual ticket purchase**, no independently witnessed pre-off
  snapshot, no untouched OOS validation and no after-cost EV certification.

**Decision:** This specified all-race 2022 strategy is observationally
negative despite higher rank accuracy. Do **not** upgrade to positive
EV or live staking. Do not retune the same 2022 sample until it looks
profitable; that would intensify selection bias. Future analysis must
prioritize independent advance forecasts and contemporaneous lawful odds,
while leaving 2023–24 OOS and 2025–26 final holdout sealed.


## Research go/no-go gate for the tested 2022 unconditional strategy

The evaluation now explicitly classifies the fixed win-plus-place strategy
as `REJECT_UNCONDITIONAL_2022_POLICY` only when the retrospective ROI is
negative **and** the 2022 descriptive whole-day bootstrap upper limit
is below zero. Otherwise it returns
`RETROSPECTIVE_INCONCLUSIVE_NO_POSITIVE_EV_PROOF`; neither outcome
certifies future expected value, nor changes production permissions.
The pre-existing 2022 source and scenario are not reselected.
The zero-fee combined policy's measured shortfall to break even is
**654,220 yen** over 13,402 evaluable races; equivalently the observed
combined payout would need a substantial uplift just to reach zero
before any extra operating costs. The workflow asserts the known
source-derived 2022 figures as regression controls and prints only
summary decision metrics.

**Continuing to tweak 2022 post-hoc until it becomes profitable is
not authorized as independent evidence.** Prioritize prospective,
independently timestamped legitimate pre-off runner/odds inputs and
predeclared, no-cherry-pick paper-settlement measurement before
opening any separately protected OOS or deploying funds.
