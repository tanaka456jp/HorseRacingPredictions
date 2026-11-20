# NAR forward interim-odds reuse audit — 2026-11-11 (research only)

## Immutable observed baseline
- 2022 exploratory all-race WIN+PLACE paper ROI: -24.4076%, **NO-GO**.
- 2026-11-10 59-race / 641-runner career-form comparator: 11,800 JPY stake, 7,220 JPY official after-event returns, -38.8136% paper ROI. No pre-off quotes were captured; not buyable ROI or positive EV evidence.
- Protected 2023–24 OOS and 2025–26 historical holdout remain sealed. Do not tune policy on the observed 2022 or 2026-11-10 outcomes.

## Falsifiable operational hypothesis
The existing private odds capture script is date-relative, but the reviewed workflow
`.github/workflows/nar-pc2-official-daily-interim-odds.yml` currently validates
**exactly 59 races and 641 runners** and emits the literal
`raceDay = '2026-11-10'`. On a future race day with a different calendar,
this may reject a valid private capture; if counts coincidentally match, the
public aggregate receipt can carry the wrong date. Therefore the workflow
is **NOT approved for generic future-day reuse as-is**.

## Next implementation and acceptance (before any real run)
1. Bind the workflow's aggregate race day to the private audit's
   `source_day_jst`, not a fixed date; require it equals the JST date of
   `observed_at_utc` and the previously frozen forecast day. Reject any
   missing, unparsable or mismatched date.
2. Bind registered race/horse counts to the *previously committed* immutable
   pre-event full-day forecast manifest. Do **not** accept counts merely
   because they are internally consistent with a newly obtained ZIP.
   Require `missing_win + priced_win = frozen_races` and the analogous
   PLACE identity; require `planned_ticket_count = 2*frozen_races`.
3. Keep private ZIP, names, race IDs, individual quotes, payouts, salts,
   source digests and model scores off public logs/artifacts. Only emit
   sanitized day, aggregate counts, timestamp, missingness and HOLD reason.
4. Test fictional future days with 1, 2 and 59 races; wrong-day, wrong
   manifest, stale quote, late capture, missing price, empty quote, bad
   timestamp and public-output redaction must fail closed.
5. Before running a PC2 workflow, verify current PR head, ongoing Actions,
   authorized public source terms, protected data separation, and exact
   Windows host. Do not alter existing 2026-11-10 private originals.
6. **No workflow or capture-script edits in this documentation-only commit.**
   No push-triggered PC2 odds acquisition should be induced by this file.

## Prospective statistical decision
Pre-register all future race days and intended WIN/PLACE tickets before
results, independently timestamp forecasts and observed quotes, preserve
missing/unoffered/refunded/unknown outcomes in the original denominator,
and use conservative day-clustered uncertainty with multiple-testing
adjustment and full costs. A positive paper point estimate is insufficient:
GO requires an independent forward lower confidence bound above zero,
multiple venues/days, valid price timing and sensitivity to missingness.
No executable price or actual purchase is established by interim quotes.
If lawful independent prices cannot be obtained, retain NO-GO and
consider ending the research rather than repeatedly optimizing history.

This document records a testable blocker, **not** completion of the
implementation, PC2 validation, or positive-EV proof.
