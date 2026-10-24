# Phase 13 selection bias and expected-value boundary

Updated: 2026-10-16 JST. Existing PR #141 only. Research-only.

## Problem identified

Phase 13's preregistered partner-ranking evaluation conditions the sample
on the **nominated longshot anchor actually finishing in the top three**.
The conditional exact-partner-pair hit-rate therefore is **not** the probability
that a three-horse combination hits across all races where an anchor would
be nominated. A model can improve the conditional partner measure while still
having a very low unconditional combination hit-rate.

Example using **fictional numbers only** (not an observed racing result):

- 40 evaluated races after the existing JRA/completeness/odds filters.
- 10 races have an eligible nominated longshot.
- Only 2 nominated anchors finish top-three.
- Of those 2 conditional races, the challenger identifies both partners in 2.

The conditional partner exact-pair hit-rate is 2/2 = **100%**, but the
historical proxy for **per-nomination exact-trio rate** is 2/10 = **20%**,
and the **per-evaluated-race rate** is 2/40 = **5%**. Neither is actionable
without truly available pre-purchase three-horse combination odds.

## Change without modifying preregistered gate

The new `unconditional_trio_diagnostic` is a **supplemental descriptive field**
in the period report and does **not** alter model hyperparameters, training
folds, candidate selection, any preregistered Phase 13 success threshold,
or the protected final holdout.

The function counts conditional successes, but restores the full nominated
candidate and eligible evaluation denominators. All anchor misses, and
eligible evaluation races with no eligible anchor, count as zero **exact
combination hits**. Conditional races with no exact partner match also count
as zero. This is a counting identity, **not** a calibrated probability
or estimated EV. It reports baseline and challenger counts and rates
separately to prevent "conditional partner improvement" from being mistaken
for "profitable trifecta/trio tickets."

## Caveats (mandatory with any such result)

1. Existing `win_odds` and resulting longshot-anchor inclusion may depend
   on historical final win odds. They are only a retrospective candidate
   proxy, **not** a proved pre-decision selection rule.
2. The denominator is the **already filtered research evaluation frame**,
   not all JRA races. A separate prospective trial will require a frozen
   pre-decision eligibility rule.
3. Even the exact combination outcome frequency is not EV. EV requires a
   properly calibrated pre-decision combination probability, lawful
   timestamped **pre-purchase** trio/trifecta quotes, actual transaction
   eligibility, and purchase-cutoff evidence. No qualifying free source has
   been independently approved yet.
4. Never use settled dividends/final payouts as if they were purchase-time
   odds, and never use 2025–2026 final holdout for feature selection or tuning.
5. No raw provider data is committed, no payment is made, no live/paper
   stakes are authorized by the new diagnostic.

## Provenance hardening

`validate_local_pre2025_archive` now additionally requires a nonempty
14-digit provider file timestamp whose year is 2017–2024 **for every required
successfully acquired dataspec**. A manifest assertion of
`research_use_allowed=true` plus a bounded JVOpen *request* is not enough.
An invalid, missing or 2025+ timestamp blocks before raw data hashing/parsing.

As of this update, the original locally archived `RACE` remains absent
(`JVOpen -301`, zero records). Phase 12/13 real 2023/2024 one-shot
evaluations **have not been dispatched**. The 2025–2026 holdout stays sealed.
