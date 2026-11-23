# JRA/NAR: prospective actual-model accuracy and paper ROI (2026-11-23)

**Priority:** run an already fitted winner CatBoost and a distinct podium CatBoost on lawful, complete future pre-off rosters; freeze top1/top3/outsider **before** results; then independently join final official finish positions and WIN dividends.

Code: `src/horse_racing_predictions/prospective_dual_model_shadow.py`. The new engine scores actual **fitted CatBoostProbabilityModel** objects and rejects manually supplied probabilities, target labels, odds/popularity and any incomplete race group. Both JRA and NAR IDs are supported, but this is a core adapter, **not a claim that a new pre-off source or fitted NAR model is deployed**. Requires source-specific as-of features and trained artifacts. `load_dual_research_candidate` can verify the JRA two-CBM research artifact; the 2017–2022 NAR historical CatBoost screener still does not persist a production-ready inference artifact. Never relabel the 2026-11-10 NAR simple past-form baseline as CatBoost.

The immutable frozen **private** cohort contains full race roster, model-declared digest, UTC source/generation timestamps and each race's model top3 and independent outsider. Do not publish this cohort or use a GitHub-hosted log for horse/race data. A caller-provided SHA/date and local clock alone do **not** independently prove model lineage or prior receipt; the separate hosted blinded-digest receipt and rights review remain necessary.

Post-event evaluator reports exact top1 hit rate, numeric top3 precision, outsider numeric-top3 hit rate, and a 100 JPY hypothetical WIN stake+official return ROI using the **original full frozen denominator**. It holds the entire ROI if any outcome/payout is incomplete or ambiguous. It does not equate top-three finish with PLACE payouts, executable odds, independent data provenance, real-money profit or positive EV.

**Next genuine PC2 integration steps:** (1) independently review and bind complete JRA/NAR preoff roster and its as-of feature history, (2) persist a hash-checked 2-model artifact locally (new NAR artifact export is required), (3) freeze the model selections to PC2 D: before off with external blinded receipt, (4) independently ingest post-race official finishes and WIN payouts into the private evaluation, (5) report measured accuracy and actual official payout-based paper ROI by series, model and race day with missingness, then collect multiple future days. No JRA-VAN trial reactivation or paid feeds required for this no-network code.

Research status: **NO prospective fitted-model outcome or after-cost expected-value proof exists yet.** Synthetic regression tests exercise contracts, not real performance.

## PC2 offline fitted-model freeze command

The new `scripts/freeze_prospective_dual_catboost_private.py` consumes an operator-reviewed, pre-off **feature CSV** with columns `race_id`, `horse_id`, and the model's exact feature columns; a reviewed calendar JSON; and a hash-verified *existing* two-CBM candidate directory. It runs true native model inference and O_EXCL-writes one immutable private forward selection record for that race day and series. The public log includes **only aggregate counts and a blinded digest**, never selected horse/race keys or source rows. A second attempt cannot overwrite the recorded picks.

Calendar JSON has `schema=HorseRacing.PrivateFutureCalendar.v1`, `jurisdiction`, `race_day_jst`, `source_asof_utc`, `scheduled_off_utc` (race ID -> ISO UTC timestamp), `runner_count_by_race` (race ID -> full roster size), and two operator review booleans `operator_reviewed_asof_only` and `operator_reviewed_complete_roster`. These flags are **attestations, not verification**. No automatic collection of JRA-VAN or NAR data is performed, and an independently witnessed pre-off commitment remains necessary.

Example (PC2 only, local sources genuinely reviewed; use actual existing paths, do not copy placeholders):
```powershell
$env:PYTHONPATH = 'src'
python -B scripts/freeze_prospective_dual_catboost_private.py --candidate-dir 'D:\ApprovedResearch\dual-candidate' --preoff-features-csv 'D:\ApprovedResearch\future-features.csv' --reviewed-calendar-json 'D:\ApprovedResearch\future-calendar.json' --private-output-dir 'D:\Development\HorseRacingPredictions-PrivateReview\nar-prospective-captures'
```

**Not yet live:** The 2017–2022 NAR CatBoost screener currently discards its fitted models rather than exporting a verified, reusable two-CBM candidate. JRA future entries and fresh legal pre-off histories are also not presently confirmed available. This command does not pretend either one is ready and will HOLD on missing model/source artifacts.

## NAR fitted-model persistence (optional)
The 2017–2022 retrospective NAR trainer now accepts an **explicit opt-in** `--candidate-output-dir` when run on physical PC2. Only after completing the full 72-month source audit, 2017–2021 fit and 2022 descriptive metrics does it write the fitted two-CatBoost binaries and checksum manifest under an existing PC2 D: private parent. Without the opt-in (including the legacy self-hosted workflow), behavior stays unchanged: no model export. The export stays research-only, not independently licensed/approved, never accesses 2023–2026 sealed source, and is not a prospective outcome. Once persisted, it can be loaded by the existing verified two-CBM loader for as-of forward inference, if contemporary lawful complete features are actually available.
