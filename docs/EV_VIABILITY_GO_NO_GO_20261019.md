# HorseRacingPredictions: economic viability / GO–NO-GO review

Decision record prepared 2026-10-19 JST for the remaining one-week
hourly EV-validation research. **Top priority: independently demonstrate
a positive expected net return for a legitimately purchasable market.
Otherwise recommend freezing/retiring this project.**

This is NOT a claim of verified positive or negative real-world EV.
It does not open data, request access, place orders or alter one-shot
evaluations. Retiring the project is a human decision; preserve repo and
private data unless explicitly authorized.

## Current evidence, with separate research and economic claims

| Finding | Evidence | What it establishes | Economic decision |
| --- | --- | --- | --- |
| Champion v7 historical research | README: 12,114 races / 19 OOS folds / research ROI **-1.90%**, 2018–2021 | Existing baseline is not profitable in its reported retrospective setup | No evidence of a positive edge |
| v12 Market Residual | Existing retrospective Brier/LogLoss diagnostics | Small gains in *probability quality*, not in executable returns | Insufficient |
| Recent synthetic-only modules | PR #141, latest source head at inception `fedd955216b3356266044c9f2d1f5b95b515484b`, CI #39207567830: 1097 passed/15 skipped | Software invariants and hypothetical arithmetic | NOT a real-market profitability experiment |
| RACE pre-2025 archive | Offline diagnosis #38390982174: `JVOpen=-301`, zero RACE records | History needed for relevant real-data experiments is absent from the approved PC2 archive | Blocked |
| Bloodline archive | 79,888 BLDN records and 62,880 snapshot rows, CI #38385246243 SUCCESS | Valid pedigree data, not the outcomes or executable price quotes | Insufficient |
| Pre-purchase exotic odds | No independently verified free/licensed timestamped trio/trifecta quote source | Final dividends and final O5/O6 are *not* executable prebet prices | Blocked |
| Existing single-win Paper infrastructure | `residual_paper_evidence.py` has immutable quote timestamps, 500 prospective race / 200 settled Paper-bet minimum and race-cluster bootstrap | An already-implemented prospective evaluation pathway, **not** proof that enough approved live quotes or bets exist | Missing verified current evidence |

The actual forward-Paper evaluated-race count, settled-bet count, economic
ROI, lower confidence bound, purchase-failure rate and market benchmark
on the **current live-data-approved cohort** are **NOT VERIFIED**.
Do not misstate "not verified" as zero, or a synthetic positive statistic
as a real-world edge.

## Shortest research path toward a defensible answer

1. **Stop expanding models by default.** Do not optimize more predictors
   or add synthetic modules simply to increase CI tests; only address an
   identified gate failure that blocks real EV evaluation.
2. **Prioritize any demonstrably affordable, lawful, timestamped prebet
   market, including SINGLE WIN**. Three-horse combinations are no longer
   assumed the mandatory first market. For win, reuse the existing
   immutable odds/prediction link and frozen Paper evidence gate. Do not
   change existing thresholds after inspecting results.
3. **Verify rights, cost and timestamps** for each candidate data
   provider *before* collecting anything. Public page visibility,
   freeware label and actual data license are different. No unlicensed
   scraping, automated purchases, new paid accounts, token reads or
   unlimited authentication retries.
4. **Verify price *before* the independent purchase cutoff**, with
   source/capture time, market ID, source rights, and all abstentions
   included. A display quote may diverge from the eventual pari-mutuel
   dividend; report a conservative bound for this instability.
   Model eligible attempts, refused attempts, quote outages, nonfills,
   purchase constraints and all costs as applicable. A retrospective
   final payout is an OUTCOME, never a prebet executable quote.
5. **Use original, independent strict-OOS evidence** with market baseline
   on identical eligible races and frozen policy. No touching protected
   2025–2026 final holdout to backfill current data. The 2023/2024
   one-shot Phase12/13 evaluation remains unconsumed.
6. **Meet existing Paper evidence gate**: at least 500 prospectively
   evaluated races AND 200 settled Paper bets; independently verify
   market comparator, all fees, lower return confidence bound and
   sufficiently independent race/day cohorts. Positive observed ROI
   alone or improved Brier/LogLoss are not sufficient.
7. **Report explicit decision and data gap every cycle**, including
   available eligible races, actual *approved* decision-time quotes,
   attempts/nonfills, settled bets, net ROI, market delta, interval
   lower bound and proof of rights. Missing entries must say UNKNOWN.

## Decision classification (not an automated trading permission)

- `PROVEN_POSITIVE_EV_FOR_HUMAN_REVIEW`: only after all evidence/rights,
  cutoff, frozen OOS, settled costs, sample and comparator checks pass,
  net ROI > 0, *independently justified lower bound* > 0, and sensitivity
  to price deterioration/selection and missing opportunities remains
  positive. Still **NOT** permission to bet; a statistical estimate is
  never certainty.
- `MEASUREMENT_BLOCKED`: outcome or executable quote records, rights,
  sampled opportunities, OOS provenance, or settlement evidence missing.
  This is the **current status**, not a finding of zero/negative EV.
- `EVIDENCE_AGAINST_EDGE`: sufficiently powered, independently valid
  economic test finds nonpositive/negative net edge or the plausible
  lower-bound threshold fails. A small/inconclusive test must not be
  mislabeled a strong negative conclusion.
- `NO_GO_RECOMMENDED`: at scheduled one-week conclusion,
  *either* required no-cost lawful acquisition route is unavailable
  *or* the necessary economic evidence cannot credibly be obtained
  within the project's budget/horizon *or* trustworthy testing rejects
  profitability. Explain which cause applies. Recommend pausing
  development and preserving artifacts, not deleting anything.

The last scheduled hourly iteration follows the existing automation
(`DTSTART=2026-10-16T18:31:15Z`; `FREQ=HOURLY;COUNT=168`,
ending approximately 2026-10-24 02:31 JST). If evidence is still absent
at the conclusion, do not perpetuate indefinite purely synthetic
development. Provide a negative continuation recommendation and identify
what new independent evidence would justify reopening research.

## Important 2025–2026 boundary

The already-frozen 2025–2026 holdout must NOT be read, replayed,
rebuilt, mined for retrospective evidence, or used for feature
selection. JRA-VAN realtime historical snapshots generally expire
rapidly and historical final odds are insufficient to reconstruct
purchase-time trio/trifecta quotes. Under the current freeze, recording
new 2026 odds as research data **cannot be assumed authorized**.
A new future prospective cohort would require a separately established
and reviewed data/split policy; the task may not silently redefine
the protected final holdout.

## Independent source references

- Official JRA-VAN Data Lab current standard subscription:
  https://jra-van.jp/dlb/ (JPY 2,090/month).
- JRA-VAN free-trial FAQ:
  https://support.jra-van.jp/jravan/detail?category=2&id=431&site=SVKNEGBV
  (a trial is conditional; do not infer it remains valid at PC2).
- JRA public website usage terms:
  https://www.jra.go.jp/use/index.html
- Existing repository source review:
  `docs/PHASE11_FREE_PREBET_RIGHTS_DECISION_20261010_CYCLE49.md`
  and `docs/EXOTIC_PREBET_ODDS_EVIDENCE_GATES_20261010.md`.
- PC2 RACE offline failure:
  `docs/JRAVAN_RACE_FREE_TRIAL_HANDOFF.md`.
- Existing 500/200 evidence criteria:
  `src/horse_racing_predictions/residual_paper_evidence.py`.

**At preparation:** `MEASUREMENT_BLOCKED` — no established
purchase-executable positive EV and no approved free path with complete
evidence. Recommendations are reversible upon new independent proof.
