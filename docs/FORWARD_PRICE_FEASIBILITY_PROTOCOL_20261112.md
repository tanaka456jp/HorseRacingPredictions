# Forward market-price feasibility protocol (2026-11-12)

Status: **PREREGISTERED DESIGN ONLY — NO LIVE DATA, NO POSITIVE EV CLAIM**.

## Hypothesis and stop rule
A legally accessible, free, time-stamped NAR/JRA pre-off WIN/PLACE quote can be observed independently of the frozen prediction, with sufficient completeness to assess hypothetical executable pricing. This is a **data-feasibility** hypothesis, not a prediction of profit.

Before any future race-day observation, freeze an immutable full-race manifest, complete entrant roster, predictions, ticket type, unit stake, fee assumptions, timestamp and external digest. Retain every preregistered race/ticket in the denominator, including non-runners, refunds, missing quotes and unusable prices. Record reasons separately, without post-outcome exclusions.

A quote is evidence of *observed indicative pricing* only, not of order acceptance or execution. Preserve official source timestamp, independent receipt timestamp, pre-off cutoff and market identity. Reject future-dated, stale, post-cutoff or unmatched prices. WIN and PLACE are distinct; place-range bounds are not guaranteed executable returns.

## Predeclared evaluation
- Report full preregistered race/ticket counts, quote availability, missing/invalid/refunded counts and exact stake reconciliation.
- Keep **quote feasibility**, **prospective paper settlement**, **actual order execution**, and **after-cost positive EV** as separate conclusions.
- Use a fixed non-optimizing baseline. No threshold, model, ticket-type or denominator selection based on 2022 exploration, 2026-11-10 results or protected holdouts.
- Account for all ticket stakes, official refunds, actual payout rules, transaction fees and execution constraints. Missing prices cannot contribute evidence for positive EV.
- For sufficiently many *independent prospective* race-day clusters, report cluster-aware uncertainty intervals and a preregistered one-sided lower confidence bound for net ROI; do not claim statistical proof from a positive point estimate alone. A finite dataset cannot guarantee future profitability.
- If lawful pre-off independent prices cannot be captured with verified provenance, declare **HOLD / NO-GO** and reassess continuation rather than tuning toward historical profits.

## Privacy and operations
Keep private NAR ZIPs, horse names, race IDs, salts, individual payouts, source data and logs on approved private PC2 storage only. Public GitHub may contain only synthetic tests, generic policy and privacy-reviewed aggregate counts. Do not open sealed 2023–24 OOS or protected 2025–26 holdouts. No paid source, expired JRA-VAN trial, real bet, deployment or main merge without prior authorization.

## Existing technical blocker
The PC2 daily interim odds workflow still hardcodes **2026-11-10 / 59 races / 641 entrants** and triggers on edits to its own workflow. Do not edit that workflow merely to force a new live fetch. First separate an inert, synthetic-only parameter-validation test from any capture trigger; review permissions and a no-network dry-run before enabling a future dated capture.
