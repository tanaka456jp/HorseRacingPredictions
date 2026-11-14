# Prospective WIN/PLACE evidence gate (research-only, 2026-11-14)

This protocol is **not** a claim of profitability, a betting recommendation, or authorization to acquire data. It must be frozen **before** any new eligible race starts and before its outcome is known. The 2022 exploration and 2026-11-10 fixed career-form comparison are historical diagnostics, not independent evidence of positive EV.

## Preregistered immutable scope
- Fix the prospective start/end dates, venues, all eligible races, market(s) (WIN/PLACE), candidate selection algorithm, stake per selection, abstention rules, costs, refund treatment, and stopping threshold in a dated externally timestamped digest **before** evaluating outcomes.
- Record the full eligible-race denominator, including races with no quote, canceled races, missing entrant lists, non-runners and unplaced tickets. Do not delete any because they lose or have missing prices. Publish only aggregate, sanitized counts and hashes that cannot identify private records.
- Never tune model, market, cutoff, selection threshold, or stopping time on this evaluation. Any change starts a **new** preregistered cohort and the original cohort remains reportable.
- Keep 2023–24 sealed OOS and 2025–26 protected historical holdout closed unless separately authorized.

## Per-race pre-off provenance
- Privately retain immutable original official entry/runner list, prediction digest, WIN/PLACE quote bytes, source publication time, independently recorded receipt time, scheduled off time, and collection environment. Preserve timezone and clock synchronization evidence.
- A nonempty, well-formed quote is only **indicative**. Verify contemporaneous lawful access, actual market availability, stake constraints, potential latency, suspension and quote-to-bet execution feasibility. A final dividend cannot substitute for a pre-off quote.
- If independent receipt evidence or lawful rights are missing, mark that race/selection **UNVERIFIABLE_PRICE**; keep it in the denominator. Never assign an invented price or claim tradability.

## Settlement and statistical reporting
- Reconcile every preregistered selection to official outcomes, dead heats, scratches, cancellations and refunds. Calculate stakes, refunds, gross dividends, transaction/other costs and net P&L explicitly. Separate unobservable paper trades from executed trades.
- Report complete-case coverage alongside full-denominator outcomes, missing-price and unknown-settlement counts, and conservative sensitivity bounds. Do not treat missing observations as zero-risk or drop them from the primary audit.
- Use race-day clustered uncertainty intervals (and sequentially valid inference if interim looks are allowed) with effective sample size, dates, selection count and confidence method. **GO** requires a prespecified positive lower confidence bound for *net* return, sufficient independent future observations, verified tradability, and no material data integrity failures.
- **HOLD** if evidence is incomplete but collection is lawful and viable; **NO-GO** if positive EV is not established; recommend ending the project if lawful independent pre-off prices cannot be obtained at reasonable cost.

## Operational guardrails
No provider SDK calls, scraping, new workflow trigger, paid service, real bets, publication, deployment, main merge, runner configuration changes, or raw private NAR material are authorized by this document. PC2 race IDs, horse names, private ZIPs, salts, individual settlements, and secret paths must remain off public GitHub, Actions logs and artifacts.

## Price-availability feasibility preflight (prospective; not an ROI experiment)
Before initiating any return-evaluation cohort, run a separately timestamped, **outcome-blind** collection-feasibility pilot on the next three eligible scheduled race days. Freeze the three dates and the complete eligible-race denominator before the first day's off times; do not replace failed or empty days after seeing outcomes. This pilot tests whether lawful, independently timestamped **nonempty** pre-off WIN/PLACE quotes can be observed; it does **not** select bets, estimate EV, or authorize live wagers.

For each frozen day, privately retain source/rights evidence, capture attempt and receipt timestamps, source publication timestamps, official scheduled off times, source-file digests, quote counts, market coverage, and a sanitized machine identity attestation. Report only aggregate counts, dates, rights status and non-reversible evidence digests that cannot reveal private race identifiers or data. Empty ZIPs count as **zero available prices**, not as successful coverage. A workflow PASS, valid ZIP, or post-race dividend never counts as a verified pre-off quote.

**Feasibility STOP:** if none of the three frozen days yields a lawfully usable, independently timestamped nonempty pre-off quote, mark the price-evidence path `NO-GO / RESEARCH_PAUSE` and recommend ending or suspending profitability research rather than tuning thresholds or running further synthetic-only CI cycles. If some quotes exist but market coverage, receipt independence, rights, or tradability remain incomplete, mark `HOLD` and document the exact blocker; do not promote to EV testing. The pilot's results may inform infrastructure feasibility only, never model/market selection or the future ROI cohort. Any later feasibility pilot requires a new preregistration, and prior failed days remain reportable.
