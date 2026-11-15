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

## 2026-11-15 operational redesign: future-race per-off price feasibility

Code implemented in Draft PR #142; NO new licensed odds were fetched as part
of this redesign. The former collector rejected an entire day after its
earliest race came within ten minutes of off. The new validator admits
later events if, for EACH race individually, both source publication
time and observed receipt time precede scheduled off by >10 minutes.
Already-started/late races have their odds BLANKED before selected price
evidence is produced, even if the official daily ZIP includes post-off
records. All original races and attempted tickets remain in the
full-day denominator and appear as missing prices; no profitable
subgroup may be selected after results are known.

The pre-existing PC2 workflow was unsafe for reuse: it hardcoded
2026-11-10, 59 races, and 641 entrants. The replacement is manual-only
workflow_dispatch, never push-triggered, and uses private frozen day
counts dynamically instead of asserting 59/641. It requires explicit
true attestations for (a) permission covering official daily WIN/PLACE
download, private retention and bounded retrieval, and (b) a
pre-event GitHub-hosted blinded full-roster commitment receipt.
These assertions alone do not independently prove consent or receipt;
they must be supported by existing source evidence. The obsolete
November 10 results replay workflow is also manual-only, so new code
edits do not waste PC2 time rerunning an expired retrospective job.

The official NAR site terms at
https://www.keiba.go.jp/terms.html require prior permission for
unauthorized reproduction/reposting, and ordinary public availability
does not automatically establish the full scope of private
automated collection. The already-reported NAR user permission needs
verification for the **specific** live daily odds download, locally
stored research source records, download frequency and only
privacy-safe aggregate reporting. Store permission documents privately
with provenance and dates; do not upload them to GitHub.

### Actionable go/hold/no-go sequence

1. **RIGHTS_HOLD** until the odds-specific provider permission scope
   has been verified. Do not run additional provider requests just to
   change the CI status.
2. **PRICE_AVAILABILITY_HOLD** until a real, nonempty official WIN or
   PLACE intermediate price has been recorded before that race's
   off cutoff with independent receipt time. A valid empty ZIP counts
   zero observed prices, not success or a profitability failure.
3. When both gates pass, externally register exactly 3 future eligible
   days and complete race denominators before race results. Keep
   source/received/off timestamps and every failed/missing market.
4. On 3 truly attempted frozen dates with 0 lawful usable prices,
   recommend NO-GO / RESEARCH_PAUSE rather than spending repeated
   cycles optimizing synthetic tests or already-known outcomes.
   If feasible, start a separate prespecified future after-cost
   economic evaluation with cluster-aware confidence intervals.

Never turn end-of-race dividends into pre-off executable odds.
No gambling orders, paid provider, expired JRA-VAN, historical
sealed OOS reading, main merge, or publication of private odds,
horse/race IDs or salted raw NAR data is authorized here.

### Falsifiable regression guarantees
- Later event quote after first off: accepted only when individually
  timely before that event.
- Closed race with valid price rows: all selected prices withheld;
  denominator unchanged and missing prices counted.
- All events too close or done: HOLD; never accept hindsight.
- At most 6 official ZIPs/day with a 150-second minimum spacing,
  local D-drive only; no automatic workflow push acquisition.
- All CI fixtures are fictional and are not live EV results.
