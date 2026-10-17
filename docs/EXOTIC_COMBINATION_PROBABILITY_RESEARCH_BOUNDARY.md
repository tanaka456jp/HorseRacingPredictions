# Race-level 3連複・3連単 probability consistency — synthetic-only research

Updated: 2026-10-16 JST. Existing PR #141 remains Draft.

## What was implemented

`src/horse_racing_predictions/exotic_combination_probability.py`
provides a **mathematical hypothesis**, not a calibrated prediction model:

- `ordered_trifecta_probability(..., (A, B, C))`: sequential
  Plackett–Luce probability that A finishes 1st, B 2nd, C 3rd.
- `unordered_trio_probability(..., (A, B, C))`: sum of the six
  mutually exclusive finish orders for the same set of three horses.
- `synthetic_combination_probability_audit(...)`: enumerates the full
  mathematical distribution and verifies all possible 3連複 and 3連単
  probabilities separately sum to 1.0. Designed for 3–18 runners.

Hypothetical per-horse **winner strengths** `w_h > 0` are the only input.
For an exact order `(a,b,c)` among all runners H:

`P(a,b,c) = w_a/sum(w_H) * w_b/(sum(w_H)-w_a) * w_c/(sum(w_H)-w_a-w_b)`.

The implementation re-sums remaining positive weights to avoid subtractive
roundoff. Scaling all strengths by a common factor must not change any
probability. With four identical strengths each ordered trifecta has
probability 1/24 and each unordered trio has probability 1/4.

These mathematical identities do not depend on historical finishing results,
RACE access, oddsmakers or final payouts.

## Critical limitations

This model is **not approved for live or paper wagering**:

1. **Top-3 class probabilities are not winner strengths.** Reusing
   Phase 12/13 Top-3 scores as weights without separately modeling the
   generative winning-strength assumption would be a modeling error.
2. Plackett–Luce assumes sequential choice without replacement and can
   be wrong about dependencies, jockey tactics, track effects, or close
   finishes. The fact probabilities sum to one does **not** establish
   correct real-world calibration or ability to beat the market.
3. Predictive calibration needs independently proven pre-2025 RACE
   history, strict chronological training, held-out reliability plots,
   and a preregistered evaluation protocol. RACE is currently absent
   from the verified D-drive archive (original JVOpen -301).
4. Expected return further requires genuine legally retained
   **pre-purchase** trio/trifecta odds, precise timestamps, bookmaker /
   tote cutoffs, eligibility, and bounded execution costs. Historical
   final dividends or final win odds are **not** substituted as executable
   prices. No free approved source has been validated yet.
5. Neither this module nor its tests contacts providers, computes EV,
   authorizes purchases, alters Forward Paper, reads raw race data, or
   accesses the protected 2025–2026 final holdout.

## Research pathway when prerequisites are independently met

- Keep the successful BLDN snapshot and migrated archive intact.
- Resolve RACE authentication with the official PC2 validation tool
  without paid service or reading usage keys into logs.
- Require proof of a bounded pre-2025 RACE source before any research,
  and separately approved timestamped pre-purchase exotic quotes.
- Freeze a model calibration/split specification *before* real-data tests,
  and reserve 2025–2026 for final independent holdout.
- Only then test whether an ordered probability model beats a frozen
  market baseline with race-level clustered confidence intervals and
  model calibration. Never claim positive EV merely because the
  probability mass identity passes.
