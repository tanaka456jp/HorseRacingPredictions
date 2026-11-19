# Preregistered research: omit WIN tickets when top-ranked prediction is #1 favorite

**Status at creation: IMPLEMENTED SIMULATION/PRIVATE AUDIT CONTRACT ONLY.
NO REAL NON-FAVORITE ROI MEASURED; NO EVIDENCE OF PROFIT.**

## Hypothesis and decision

The operator proposes: instead of always buying the model's frozen top
WIN selection, purchase a 100-yen hypothetical WIN ticket ONLY when
that horse's **genuinely pre-off observed market popularity rank is
greater than 1**. This may raise mean ROI by avoiding low-odds favorites;
it can also decrease both ROI and total profit by excluding fairly
priced winners. Popularity is NOT itself a measure of positive EV.

Freeze exactly these two arms BEFORE seeing any newly collected outcomes:

- A: 100-yen WIN on model's top frozen winner selection in every
  eligible predeclared race, with documented refunds/unoffered rules.
- B: same frozen horse, 100-yen WIN only if its pre-off popularity rank
  is 2 or lower in popularity (integer rank >=2). Rank=1 => no ticket.
- Missing/ambiguous/tied popularity, missing price, late source,
  late receipt, stale quote, no independent forecast witness, or
  unresolved result: **HOLD the entire cohort's numeric ROI**.
  Retain every originally frozen race in the denominator.
- Do not switch the selection, market, threshold, cutoff, day,
  or venues using observed payouts.

## Data acceptance

- Full immutable forecast roster and winner top pick, with independent
  GitHub-hosted pre-first-off digest receipt before the market decision.
- Actual daily pre-off NAR WIN price for the same race and horse,
  **source-generated and locally received timestamps** more than
  10 minutes before that race's scheduled off (source freshness
  <=25 minutes). Popularity rank must be a positive integer within
  the entrant count. A final popularity rank is NEVER valid.
- Complete independently reconciled official final WIN dividends
  AFTER all races, refund/scratch/DNF classes and full original
  race-day scope, including nonbetting races.
- Data acquired under user-reported personal-use NAR phone permission,
  preferably manually via local private ZIPs, with no automated
  provider polling or raw ZIP disclosure. If provider-origin
  evidence or genuine independent receipt is absent, no claim of
  executable prices or positive EV is allowed.
- The actual 2022 historical CatBoost study did NOT have independently
  recorded pre-off popularity or quote timestamps. **Never reconstruct
  the missing popularity from final dividends.** Historical 2022
  model 29.4508% top1 win accuracy, but no B-filter ROI can be
  calculated from it.
- The different 2026-11-10 forward career-form comparator had ZERO
  observed pre-off prices, so cannot evaluate B either. Its 59-race
  WIN+PLACE paper ROI -38.8136% is not a comparable WIN-only B result.

## Private scripts

The pure evaluator, with *no network or file I/O*, is in
`src/horse_racing_predictions/nar_nonfavorite_win_policy.py`.

A separate bounded private JSON reader is in
`scripts/evaluate_nar_nonfavorite_preoff_local.py`. Example on
Windows PC② only, after independently reviewed and frozen private
records actually exist:

```powershell
$env:PYTHONPATH = (Resolve-Path .\\src).Path
python -B .\\scripts\\evaluate_nar_nonfavorite_preoff_local.py --reviewed-local-json "D:\\Development\\HorseRacingPredictions-PrivateReview\\nar-prospective-captures\\nonfavorite_forward_PRIVATE.json"
```

No private records exist merely because this code exists. The
reviewed local JSON must have exact top-level keys
`schema`, `input_mode`,
`frozen_race_days`, `observations`,
`ticket_unit_yen`, `market_observations_preoff_only`,
`forecast_registered_before_off`.
Use schema `NAR.PC2.PrivateNonfavoriteForwardEvidence.v1`,
input mode `LOCAL_PERSONAL_MANUAL_PREOFF_SOURCE`, unit 100,
and both preoff checks `true` ONLY after reviewing the genuine
timestamped original records. Each observation has exactly the
`NonfavoriteWinRace` dataclass fields, with timezone-aware
ISO8601 timestamps or null. The complete predeclared
`frozen_race_days` is a race-id-to-JST-day object, and no
observation outside it is accepted.

The local private input adapter performs deterministic all-race
denominator checks, rejects corrupted data, and produces aggregate
counts only. It does not independently authenticate user-provided
booleans, original NAR data, hosted digest or actual execution.

## Predeclared evidence and stopping

A and B must be compared on the **same frozen race population**.
Publish both invested stake, gross official payout, net paper P&L,
and paper ROI, alongside the number and fraction of bets omitted,
missing odds, refunds, unoffered entries, and complete days.
An increase in paper ROI alone is not proof of a better strategy if
total yen profit falls or data coverage deteriorates.

Estimate uncertainty by paired **racing-day-clustered** bootstrap
(minimum 20 independent days for a descriptive interval).
Do not interpret a one-day winning sample as proof. For decision-grade
positive EV evidence, preregister a completely new future evaluation
period, maintain missingness/cost and actual price observability,
use independent venue/day validation and multiplicity-corrected
lower confidence bound for after-cost ROI >0. Inability to get
future odds => experimental HOLD, not a fabricated result.

NO reopening 2023–24 sealed OOS or 2025–26 protected holdout,
no money bets, no paid provider, no auto scraping, no publication
of raw licensed NAR contents or private selections.
