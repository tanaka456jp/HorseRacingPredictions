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


## 2026-11-19 implementation: no-network permission preflight, then research

### What was blocking progress?
The user's earlier report that NAR authorized *some* data use does not
include the verbatim grant or confirmation that it specifically covers
the official daily **WIN/PLACE intermediate-odds ZIP**, bounded automated
polling, retaining the downloaded source locally, training/analysis,
and sharing only nonidentifying aggregate results. The public
[NAR terms](https://www.keiba.go.jp/terms.html) retain prior permission
requirements for reproducing/republishing. The official
[NAR FAQ](https://www.keiba.go.jp/qa.html) forbids commercial reuse or
modified republication of race information. Public web availability
is NOT a substitute for the documented scope of the individual grant.

Instead of repeatedly running synthetic CI or making unauthorized
requests, a new PRIVATE offline preflight blocks the real capture
function before its first `urlopen` if scope-specific documentary
evidence has not been stored on PC②. This is **not** a digital signature,
legal opinion, independent NAR authentication, or an assertion that the
user has or lacks rights; it is a fail-closed workflow checkpoint.

### Private PC② setup (only after the actual grant expressly covers it)

1. Keep the authentic NAR response/eml/text/PDF on
   `D:\\Development\\HorseRacingPredictions-PrivateReview\\nar-prospective-captures\\`.
   Make a private copy named
   `nar_odds_permission_YYYYMMDD_PRIVATE.eml` (or .txt/.pdf; YYYYMMDD
   is the evidence date). The original is retained unchanged.
   No evidence document, original filename or message text is uploaded.
2. Review the actual wording, especially permission for **bounded
   automated download**, **private immutable retention**, **private
   predictive research**, **internal model training**, and **only
   nonidentifying aggregate reporting**. If the grant omits any item,
   leave that item `false` and the capture stays blocked. Explicitly
   stated access rate limitations must be reflected; never exceed
   official permitted frequency. This is only a template, not a
   declaration that any permission has been issued.
3. Calculate a SHA256 of the private evidence *on PC②* with
   PowerShell `Get-FileHash -Algorithm SHA256`; keep the digest inside
   the private JSON alongside the evidence, NEVER in public CI logs.
4. Create local-only
   `nar_official_daily_odds_rights_PRIVATE.json` in the same folder,
   with the following complete key schema. The values `false`, fake
   dates and placeholders intentionally **do not authorize a fetch**:

```json
{
  "schema": "NAR.PC2.OfficialDailyOddsRights.v1",
  "provider": "NAR",
  "endpoint": "https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload?type=daily",
  "permission_evidence_file": "nar_odds_permission_YYYYMMDD_PRIVATE.eml",
  "permission_evidence_sha256": "<SHA256_OF_PRIVATE_EVIDENCE_FILE>",
  "issued_on": "YYYY-MM-DD",
  "valid_until": null,
  "private_scope_reviewed_by_user": false,
  "permit_bounded_automated_download": false,
  "permit_private_immutable_retention": false,
  "permit_private_predictive_research": false,
  "permit_internal_model_training": false,
  "permit_nonidentifying_aggregate_reporting": false,
  "max_downloads_per_day": 1,
  "min_seconds_between_downloads": 1800
}
```

`valid_until: null` means **only** that the original grant explicitly
has no expiry. It may not be assumed from silence; where an expiry
exists, record its date. If the source permission is unclear, obtain
clarification rather than setting a `true` field.

5. The new file `scripts/nar_private_odds_rights_gate.py` checks
   exact source URL, evidence file name and SHA256, date scope,
   all five use rights and actual user review, bounded maximum
   download count (1–6/day), and minimum spacing (>=150 seconds).
   The original capture script respects the stricter of the developer
   guard and the documented limits. Any missing/altered/expired
   evidence causes a static private HOLD **before a provider fetch**.
   These checks prevent accidental collection, but cannot establish
   that an unverified document is a genuine authorization.
6. Even after this checkpoint succeeds, the separate **independent
   pre-event forecast digest receipt** and race-window guards still
   apply. The manual-only GitHub workflow cannot be run from a push;
   two explicit workflow inputs must be true, and a new real
   prospective observation will be reported as indicative only,
   NEVER as executable odds or positive EV.

### Research decision
**As of this update, actual odds-specific scope and independent
future pre-off prices are still UNVERIFIED.** Research is
`RIGHTS_HOLD / PRICE_FEASIBILITY_HOLD / POSITIVE_EV_NOT_PROVEN`.
Neither the prior 2022 negative ROI nor the -38.81% career-form
2026-11-10 paper result changed. Do not enable live collection
until permission and external pre-off forecast receipt are documented.
