# Prospective price-feasibility pilot: preregistration and decision record

Status at creation (2026-11-14): **NOT STARTED / RIGHTS AND PRICE FEED UNVERIFIED**. This is a blank, outcome-blind control document, not a claim that three dates have been registered or that any quotes were obtained. The immutable scope must be externally timestamped before the first eligible race. Do not fill dates retrospectively.

## Start gate (all mandatory)
- [ ] Document provider, exact WIN/PLACE source and permitted usage, including whether local private retention and evaluation are authorized. Do not assume public visibility implies research/reuse rights.
- [ ] Verify a legal, free source actually returns nonempty intermediate pre-off quotes, rather than final dividends or an empty ZIP.
- [ ] Verify source publication time, independent receipt time, timezone/clock sync, scheduled off time, and practical purchase constraints can be privately recorded.
- [ ] Freeze exactly three future eligible race dates, complete eligible-race denominator and collection windows **before** any eligible outcome; obtain independent external timestamp of a digest.
- [ ] Define how missing quotes, cancelled races, suspension, invalid timestamps, rights failures and unknown prices remain in the denominator. No post-result replacement days.
- [ ] Verify PC2 execution identity and local-only private storage; public Actions logs and artifacts may contain sanitized aggregate status only.

**If any start gate is false or unknown, do not start the three-day pilot.** Record BLOCKED with the missing prerequisite. Do not manufacture a three-day failure from days when collection was never authorized or attempted.

## Private execution record (never commit completed private records)
For each preregistered day record: local immutable manifest digest; scheduled race count; collection attempts; source and receipt timestamp attestations; WIN and PLACE quote counts; valid nonempty pre-off price count; lawful-rights status; tradability status; cancellation/refund handling; missing/unknown count; source file hashes; sanitized PC2 identity attestation. Keep all private race IDs, horse names, salts, original ZIPs, per-ticket data and local paths off GitHub.

## Public aggregate-only decision record
Report three frozen dates and aggregate eligible races, valid price counts and coverage, rights and independent-time attestation status, missing-price count, and reproducible sanitized evidence digest. No public private identifiers or reversible per-race hashes.

- **NO-GO / RESEARCH_PAUSE**: all three genuinely attempted, preregistered days have zero lawfully usable, independently timestamped nonempty pre-off prices. Recommend suspending profitability research. This is not a profitability estimate.
- **HOLD**: some prices exist but coverage, lawful rights, independent receipt time, or tradability is incomplete; or start gate remains blocked.
- **FEASIBILITY PASS (not EV GO)**: usable price evidence exists and all integrity checks pass. Only then preregister a separate independent future ROI cohort, including costs/refunds and race-day clustered uncertainty.

2022 exploratory ROI and the 2026-11-10 fixed career-form comparison remain diagnostic, not evidence of positive EV. Do not open 2023–24 sealed OOS or 2025–26 protected holdout; do not acquire paid or expired-trial data, place bets, deploy, merge main or trigger additional workflows without approval.
