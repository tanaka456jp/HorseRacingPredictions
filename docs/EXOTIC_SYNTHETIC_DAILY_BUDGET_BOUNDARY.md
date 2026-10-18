# Synthetic daily exposure and EV aggregation — refused-cycle recovery

Date: 2026-10-19 JST. Research-only. Recovery of the uncommitted
`exotic_synthetic_daily_budget.py` work from the hourly EV-research cycle.

## Purpose

Previous `exotic_synthetic_fill_price_bounds.py` validates a hypothetical
single ticket, its per-ticket race/day caps, a *conditional-on-fill*
probability lower bound, displayed odds, haircut, and costs. However, multiple
individually compliant attempts may collectively violate the daily exposure
limit. Hypothetical low fill rates **cannot be used to justify funding more
simultaneous attempts**.

The new `audit_synthetic_daily_budget` aggregates an explicit, finite list of
**fictional attempts** identified by `T1`, `T2`, etc., and synthetic races
identified by `S1`, `S2`, etc. Inputs contain no real race identifiers,
actual betting account data, or provider odds. It rejects missing/extra
fields, duplicate attempt IDs, non-100-yen stakes, invalid synthetic quote
assumptions, more than 1,024 attempts, and any aggregate race/day cap breach.

The reservation rule is intentionally conservative:

- **Worst-case day exposure** = sum of the entire stake for every attempted
  ticket, regardless of the assumed fill fraction.
- **Worst-case same-race exposure** = sum of all attempted stakes for that
  synthetic race, including correlated combinations.
- **Hypothetical net EV per attempt set** = sum of existing per-attempt
  calculations including *both* fill fees and fees paid on failed attempts.
- Expected filled stake may also be shown, but **never** substitutes for
  full-stake reservation or actual measured fill-rate evidence.

The output distinguishes the internally tested
`synthetic_aggregate_reservation_passed` from unsupported real-world
claims. In particular, `daily_aggregate_cap_verified`,
`eligible_opportunity_coverage_verified`,
`quote_rights_verified`, `purchase_price_verified`,
`calibration_verified`, `positive_executable_ev_proven`, and
`paper_or_live_action_authorized` remain **false**.

## Example: fictional numbers only

Three separate 100-yen attempts, a 200-yen per-race cap and 300-yen
daily cap, with two attempts for synthetic race `S1` and one for `S2`,
reserve **300 yen** even if each *assumed* fill fraction is 0.5.
The corresponding fill-weighted stake is just an illustrative 150 yen;
it cannot be used as reserved capital. A fourth 100-yen attempt fails
the day limit. Three attempts at the same race fail the per-race limit.

## Do not infer profitability

No broker connections, betting screens, real-money accounts, raw JRA-VAN data,
provider authentication, 2025–2026 holdout, actual betting or paper orders are
involved. The above is **not a validated bankroll-risk model** or empirical
selection procedure. There is no execution-ready odds evidence, legally
verified free source, calibration reliability report, confidence interval,
or proof of positive net expectation. The unretrieved RACE dataspec remains
blocked at JVOpen -301 until separate lawful, free entitlement verification.

The new module is an isolated synthetic mathematical guard; it does not alter
the frozen Phase 12/13 one-shot gates, their evaluation receipts, main branch,
or production decision code.
