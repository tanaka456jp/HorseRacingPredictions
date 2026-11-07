# 2017-11 NAR official monthly ZIP: private finish-status triage (2026-11-07)

**Scope:** aggregate-only analysis of ONE operator-downloaded month on PC2
`DESKTOP-MVV1FD4`. No source CSV, race/horse identities, file paths, or
derived individual race details are uploaded. All examples in tests are fictional.

## Evidence (PC2, not fictional tests)

- Original source ZIP: operator-authorized `201711_*_race.zip`, read-only.
- Baseline PC2: [Run 42253479986](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42253479986).
- Aggregate finish histograms: [Run 42255247406](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42255247406).
- Ranking, headcount and payout reconciliation:
  [Run 42256361474](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42256361474).
- Updated PC2 official-result integration (993 accepted / 103 unresolved):
  [Run 42258871532](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42258871532).
- Official NAR fields, 2017 historic-data caveat and **multiple payback rows on dead heats**:
  https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
- Official NAR labels: 取消, 除外, 中止, 取止, 不成 and numeric 降:
  https://www.keiba.go.jp/Howtoread/theracecard.html

| Fixed aggregation | Count |
| --- | ---: |
| Source denominator (races in the three official members) | 1,228 |
| Predeclared Obihiro/banei out of flat scope | 132 |
| Flat-source races in study scope | 1,096 |
| Payout-verified flat results, including justified rank ties and multirow tickets | 993 |
| Flat races currently requiring adjudication | 103 |
| Of the original 107: blank-finish races, still unresolved | 103 |
| Of the original 107: verified complete rank ties now accepted | 3 |
| Of the original 107: verified distinct multi-row payout now accepted | 1 |

### Blank-finish diagnostics

- **11,469** flat horselist records: **11,355** numeric ranks and **114**
  blank ranks. No named nonnumeric finish marker was observed.
- Blanks affect **103** flat races (93 with one blank; 9 with two;
  1 with three).
- On **all 103** races, racelist declared field equals total horselist rows,
  **not** the numeric-rank-only count. This does *not* establish whether a
  particular blank represents a scratch, late exclusion, failure to finish,
  disqualification, or missing historical data.
- **102** affected races have a contiguous, unique sequence among known
  numeric ranks; **1** also has a tied/incomplete numerical ranking.
- **1** blank-finish row still has a time field; **35** have a popularity
  field. These are diagnostics only: popularity is prohibited as a model
  feature and an available time field does not establish settlement status.

### Dead heats and multirow returns

- Numeric-rank duplication occurs in **5** flat races in total,
  including **1** of the blank-finish races.
- **1** race has **2+ distinct** published payback rows; **no** race has an
  exact duplicate payback row.
- NAR explicitly says that a dead heat may produce two or more payout rows
  per race. Duplicate rank is not itself proof of corrupt data. Neither
  picking the first payback row nor inventing an equal payout is acceptable.

## Implementation decision and fail-closed criteria

The 66-column headered 2017-11 racelist is supported without shifting
used columns. The parser recognizes official textual statuses, blank
statuses, demotion markers and competition-style dead heats. It **never**
converts an unspecified finish to last place, a loss, or a 100-yen refund.
Distinct payback rows are merged only when their actual win/place payout
values do not conflict and all winners and placers are accounted for.
Exact duplicate rows, contradictory yen for the same ticket and missing
paid winners still fail closed. In no case are ticket returns guessed or
summed across identical winning tickets. Every race remains in the 1,228-race denominator.

Current strict validator requires all final rank/settlement semantics to be
known. The initial result was 989 accepted / 107 unresolved; after validating
complete competition-rank sequences and uniting only consistent official
win/place payout values across distinct rows, **993 accepted, 132 prespecified
out of scope, 103 in-scope unresolved** is the current honest result. These
103 races remain in the denominator and prevent training or ROI on only the
profitable-looking subset. Unknown finish statuses are explicitly marked
`NAR_OFFICIAL_BLANK_FINISH_STATUS_UNRESOLVED`.


To remove this HOLD safely, implement explicit per-horse settlement
status/refund provenance and complete dead-heat ticket payouts, with tests
for every official case. If historical ZIPs omit that provenance, resolve
against independently permitted official results **on PC2**, never
manufacture missing statuses; keep any remaining unknown tickets with
explicitly bounded economic outcomes rather than excluding their races.
Do not open the 2023-24 sealed OOS labels or 2025-26 final holdout.

**Profitability status:** no genuine frozen pre-race prediction, actual
ticket-by-ticket cost-adjusted ROI, race-day bootstrap interval or positive
out-of-sample EV has been measured from this month. Synthetic CI success
establishes software behavior only, not model profitability.


## 2026-11-07 official margin-status discovery (separate interpretation gate)

**Important source-level finding:** The official 36-column horselist supplies
special finish conditions in field **No. 34 `着差`** (zero-based index 33)
when field No. 32 `着順` (index 31) is blank. The 114 blanks
are **not** unclassifiable from the supplied 2017-11 ZIP: an aggregate-only,
read-only PC2 probe found fixed official condition words in all 114 rows.

[PC2 status-field evidence Run #42321966524](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42321966524):
- 出走取消: **52 horse rows**, before-sale unoffered tickets, **not** 100-yen refunds.
- 競走除外: **27 rows**, relevant sold tickets refundable.
- 競走中止: **34 rows**, started and not eligible for a ticket refund.
- 失格: **1 row**, flagged **DISQUALIFIED_REVIEW**, with no invented ticket return.
- Unknown/other exception text in other fields: **0 rows**.

Official descriptions: https://www.keiba.go.jp/beginner/step2.html
CSV layout: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf

The new `nar_official_exception_audit.py` is a **separate,
status-aware result interpretation**, not an endorsement to train, bet or
calculate realized ROI with retrospectively changed tickets.
On the same original 1,228 races the aggregate
[PC2 Run #42322938779](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42322938779)
reported:

| Result gate | Count |
| --- | ---: |
| Source races | 1,228 |
| Venue-predeclared banei out of flat scope | 132 |
| Flat races including exception-status cases | 1,096 |
| Status-aware flat races with internally consistent published win/place returns | **1,095** |
| Single status-aware inconsistent race | **1** |
| Remaining mismatch category | `NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS` |

The anomalous race includes the lone 失格-status row. The additional
fixed-category PC2 probe [Run #42323190517](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42323190517)
confirmed that **a published winning payout is attached to the very horse
whose archived final status is 失格**, while the numeric-ranked winner lacks
a corresponding published winning ticket. This is a verified disagreement
between two official CSV fields, not proof of when or why the
adjudication occurred. Do not alter ranks or actual payouts to conceal it.
Never recode the race's historical ranks to fit payout numbers, nor recode
published payouts to fit ranks. A local independently permissible primary
official final result and pari-mutuel settlement record is needed to reconcile
the discrepancy.

**Two clearly distinct readouts are deliberately retained:**

- The existing **strict production/training intake** stays 993 accepted /
  103 unresolved (plus 132 predeclared banei), because the original
  `NarCompleteRace` / CatBoost chronological / frozen-wager APIs only
  support completely ranked participant rosters. They cannot treat a
  non-offered 取消 ticket as a refunded or losing ticket.
- The new **post-result interpretation audit** provides 1,095 internally
  reconciled flat races and 1 conflicting race, all still represented within
  the 1,228-race source denominator. It returns a private, read-only
  in-memory per-horse status with no evidence of contemporaneous pre-off
  availability.

A future end-to-end economic evaluator needs an independently frozen
**purchased-ticket ledger** (offered, placed, refunded, settled, void),
not just final-result CSV ranks. Until that and the remaining inconsistent
win payout are verified, the 1,095 cases are **not** an approved 1,095-race
profit sample. 2023-24 OOS and 2025-26 protected holdout remain sealed.
There is no actual out-of-sample realized ROI or positive expected-value
demonstration here.


## Chronological outcome-label and historical-form preflight

The status-aware interpretation is now connected to a **separate,
non-authorizing** supervised-label audit:
`nar_status_aware_training_labels.py`.
Labels are post-event targets, NEVER pre-off model features.

- Finished: labeled from **official published 100-yen returns**.
- DNF (中止): counts as a genuine prior start and zero for win/place targets;
  a fictional numeric finishing position must NOT be invented.
- Scratch (取消): before-sale, no ticket was offered; no target and no
  historical start.
- Excluded (除外): purchased tickets are refund-eligible; no win/place
  target and no historical start. Receipt purchase is **not** inferred.
- Disqualified (失格): start counts, outcome target is unresolved and
  requires separate official adjudication. Real 2017-11 disqualification
  is on the sole quarantined race, not the reconciled subset.

[PC2 Run #42325094194](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42325094194)
verified the actual **201711** aggregate:

| Category | Source-derived count |
| --- | ---: |
| Original races (including banei) | 1,228 |
| Flat in-scope races | 1,096 |
| Strict original fully-ranked settlement races | 993 |
| New status-aware payout-consistent races | **1,095** |
| Status-aware races quarantined for contradictory DQ win payout | **1** |
| Horse entries among the 1,095 reconciled flat races | **11,455** |
| Finished with numeric rank | 11,342 |
| Did-not-finish starter with a *valid losing* label | 34 |
| **Labeled win/place outcomes** | **11,376** |
| Pre-sale scratched / no purchase option | 52 |
| Late excluded / refund-eligible option | 27 |
| Unknown labels included as zero losses | **0** |

The historical-form projector
`nar_status_aware_prior_day.py` computes prior starts, wins,
top-three finishes, observed-rank mean and days since last start using
**only results before the current date**. Historic top-three form is
determined by rank, **not** by the place payout threshold (place
payouts cover only top two in 5-7-runner races). DNF increments starts
but never adds a made-up rank to the mean.

[PC2 Run #42325539111](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42325539111)
verified that 11,376 post-event target rows can be *projected* from
the 1,095 reconciled flat races with 11,342 observed numeric ranks.
Because **one flat race remains unresolved**, the projector
releases **zero training rows**. This is expected fail-closed behavior,
not model accuracy or a real-money profitability test.

Official NAR semantics:
- https://www.keiba.go.jp/beginner/step2.html
- https://www.keiba.go.jp/beginner/step6.html

**Neither** a contemporary pre-off roster, genuine purchased-ticket
ledger, 72 fully authenticated training months, independent locked OOS
nor positive expected value has been established. A clean code CI
does not override the private real-data HOLD.


## 2026-11-07 training-month availability and historic-form coverage

**PC2-only evidence, no manual guess and no licensed ZIP transfer:**

[Run #42329558192](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42329558192)
executed existing filename-only, bounded private folder inventory *after*
the expected HOLD in the single 2017-11 ZIP stage. The two fixed
allowlisted PC2 private D folders reported respectively:

- Candidate folder #1: ABSENT; 0 / 72 historical training months.
- Candidate folder #2: 1 / 72 historical training months;
  **71 missing**, no duplicates and no unexpected training ZIPs.
- No archive content was opened during the inventory. File names, paths,
  horse/race details, personal source data and 2023+ sealed OOS ZIPs
  were not exported.

The remaining data requirement is primarily **71 additional 2017-2022
monthly race ZIPs** (plus separate locked OOS provenance), not
simply remediating one 2017-11 DQ payment discrepancy.

The pre-existing PC2 private dashboard script was also improved so
its 72 month-specific operator links point to the **selected year AND
month**, rather than a year-only page that can default to the wrong
month. The old hardcoded, unsubstantiated 'three old CSV' hint was removed.

[Run #42329729197](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42329729197)
confirmed the established offline validator and PC2 dashboard both
completed successfully. Its ACL-protected output is local to PC2 at:

`D:\Development\HorseRacingPredictions-PrivateReview\nar-training-72-month-manual-acquisition.html`

Official monthly calendar and source documentation:
https://www.keiba.go.jp/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop
https://www.keiba.go.jp/terms.html

Only the operator may obtain material within the actual NAR permission
scope; no new autonomous bulk scraping or downloaded archives are
introduced by this milestone. Official site terms restrict unlicensed
copying/republication. An operator-permitted *personal research* archive
does not independently grant permission to publish race source data.

### Real 2017-11 prior-day feature coverage

[PC2 Run #42330190355](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42330190355)
confirmed aggregate-only history coverage for the **11,376** labeled
runner targets projected from the 1,095 reconciled races. There were:

| Pre-target-day feature availability | Runner rows |
| --- | ---: |
| At least one earlier November start available to the one-month builder | **4,585** |
| No earlier result *in this only available month* | **6,791** |
| Earlier observed numeric finish | 4,582 |
| Earlier observed win | 416 |
| Earlier observed finish within top three | 1,361 |

The 6,791/11,376 (59.7%) lacking history are a **truncation of the
available training archive**, not genuine first-time racing horses.
Consequently, attempting to train a history-driven model on only this
month would impose artificial cold-start behavior on most cases.
Even those with earlier records in November are missing January-October
and still have incomplete long-term form.

No 201711 training targets were released (zero), because the one
unreconciled disqualification/paid-winner conflict remains and the
chosen training window is not populated. Source year and private
identifiers were not published.

### Research-only paper tickets (new code)

`nar_status_aware_paper_ticket_ledger.py` can reconcile
*synthetic/preregistered in-memory* frozen score selections with a
**fully** status- and payout-validated train-period month. The module
distinguishes:

- pre-sale scratch: ticket was **not offered**, zero stake incurred;
- late exclusion: hypothetical 100-yen stake is returned;
- race started but not finished: losing ticket (no refund);
- disqualification: ticket settlement **unresolved**, never guessed;
- finished: exactly the official recorded win/place yen, including
  5-7-runner and 4-or-fewer-runner no-place-sale rules.

The module rejects source-month payout contradictions and all 2023+
protected evaluation input. Forecast timestamps are only validated
syntactically and **do not prove** independent real pre-off issuance.
Its paper ledger has **no observed purchase receipt, real ROI, positive
EV, live betting authorization or new real-money evaluation**. The
unresolved 2017-11 month cannot be passed to this ledger.

Project decision stays **HOLD for actual profitability**, independent
holdout and publication authorization. Data acquisition/provenance and
fully verified future-time predictions are the gating work.

### Broader four-root metadata crosscheck

The independent, bounded PC2 D-root inventory
[Run #42330495687](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42330495687)
completed SUCCESS and confirms the primary 1-of-72 availability result:

| Predeclared D-root ID | Recognized 2017-2022 months | Inspection |
| --- | ---: | --- |
| 1 | 1 | Bounded metadata scan |
| 2 | 0 | Bounded metadata scan |
| 3 | 0 | Directory absent |
| 4 | 0 | Directory absent |

No source bytes, exact file names, sensitive paths, holdout content,
newly downloaded data or training work were involved. No alternative
collection of the missing 71 monthly archives was found within these
four predeclared D-root scopes. This is **not** a claim about every
possible disk or cloud source; it explicitly bounds the inspected area.

For evidence-based model development, the next critical dependency
is acquiring and independently confirming permitted 2017-2022 monthly
official race ZIPs. Publication/commercial rights and independent
pre-off forecast timestamps remain separate gating requirements.


## Future prospective score commitments (no outcome access)

New in-memory source: `nar_forward_preoff_commitment.py`, with
`tests/test_nar_forward_preoff_commitment.py`.

Prospective date scope starts **2026-11-07** and deliberately refuses
all 2025+ historical protected holdout or retrospectively supplied
old races. It requires a *complete, predeclared flat-race manifest*,
one immutable score/roster for every race, one source-model SHA256 and
frozen fit-through day for the entire batch. The model fit cutoff
must be before the **forecast generation day in Japan**. All event
and observation timestamps must be timezone-aware and ordered.

The canonical byte stream contains the complete manifest, private
horse/race roster, all score values, precomputed top-three and
outsider picks, prediction/scheduled-post clocks and source-model
fingerprint. A separately held unpredictable private salt (minimum
32 bytes, generated securely for actual use) protects the SHA256
commitment against trivial guessing. Reordered JSON maps yield the
same digest; changed scores/model/roster/clock/selection or missing
races do not. The source identities and scores never appear in the
public `NarPrivateForecastCommitment` repr or PC2 Actions logs.

**Separation of actual proof:** A locally minted digest is only a
*content integrity* check. It has NO independent timestamp.
For a real prospective bet/forecast audit, a future independently
dated GitHub Actions/notebook/witness record must attest the
salted digest **before race off**, and the private source snapshot
and random salt must be preserved immutably. Simply backdating
`generated_at_utc` does not establish pre-off evidence. Authentic
pre-off public racecard availability and official payout provenance
still require independent verification.

[PC2 Windows synthetic-only smoke #42341327653](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42341327653):
SUCCESS; changed score rejected; 2 entirely fictional future races;
0 real licensed source rows, 0 protected OOS reads, 0 provider requests,
0 actual EV conclusions.

[CI #42341332532](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42341332532):
949 passed, 33 skipped after the 2026-11-07 freeze-contract tests.
No real horse scores or historical data is checked into GitHub.

The latest official NAR data-download manual includes a 2026-09-16
revision note; it lists downloadable race results from **1998-01**,
but historical odds downloads only from **2026-03**:
https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
This constrains retrospective market-informed studies and reinforces
the need to capture *prospective* pre-off odds/snapshots separately.
https://www.keiba.go.jp/terms.html applies to all sources.

**No 2023-24 OOS or 2025-26 protected final holdout opened,
no real model fitted and no positive net expected value established.**


## GitHub-hosted blinded digest receipt preflight (2026-11-07 follow-up)

The external-witness pipeline is now coded but **not deployed for
production input**; Draft PR #142 is intentionally unmerged.

Files:
- `src/horse_racing_predictions/nar_forward_hosted_witness.py`
  validates an exact `workflow_dispatch` input envelope and
  structurally matches a later received public digest with the full
  privately preserved forecast snapshot, *including the actual
  earliest race off time*, count and original private salt.
- `scripts/anchor_nar_gh_hosted_receipt.py` reads GitHub's own
  `GITHUB_EVENT_PATH` JSON, rejects untrusted repositories, local
  PC runners, non-`main` refs and reruns, and emits **only** a
  strict public allowlist receipt.
- `.github/workflows/nar-prospective-hosted-receipt.yml` runs
  Python on **GitHub-hosted Ubuntu**, not a PC② clock, with
  read-only permissions and no race ZIP or betting-account data.
  No winner scores, runners, private salt, raw manifests, official
  results, odds or payment details are transmitted. It enforces a
  minimum five-minute host-clock margin before earliest scheduled off.
- `tests/test_nar_forward_hosted_witness.py` covers malformed digests,
  retrospective races, non-`main` refs, forged repo, reruns,
  early/late clocks, private digest tampering, false first-off timing,
  mismatch in registered race count, leaked source text, fabricated
  rights/timestamp flags and an invented real-money claim.

**GitHub limitation:** the `workflow_dispatch` event **requires the
workflow file to be present on the repository's default branch**:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch
Until an explicitly reviewed deployment to `main`, the PR branch
executes only the safe *fictional contract test on push*. Production
digest reception on `main` is **not yet active**.

A legitimate future receipt requires, in this order:

1. Preserve a complete, timestamped private prospective race manifest,
   racecard source evidence, model SHA, scores, all forecast clocks and
   securely randomized private salt. Predict every predeclared race
   BEFORE opening its outcome.
2. Compute the salted complete-snapshot hash offline using
   `seal_nar_prospective_batch`. Send **only the 64-character digest**,
   earliest-off UTC, JST race date, race count, and the clearly
   identified fictional/prospective mode to the hosted workflow.
3. The hosted job records a bounded, typed digest receipt. A
   `workflow_dispatch` run cannot be rerun to manufacture new early
   proof: only `GITHUB_RUN_ATTEMPT=1` can pass.
4. A future independent reviewer must retrieve the GitHub
   Actions run's **server-created timestamp and event/input evidence**
   directly from GitHub, cross-check the exact digest and workflow
   source SHA, and retain the evidence before log retention expires.
5. Separately verify the originally available roster, *actual official*
   race start time, data rights and payouts. Locally comparing
   self-supplied timestamps/receipts is **never** independent proof.
6. Only after sufficient genuine, immutable prospective forecasts,
   full denominators, independent race-day bootstrap and cost-adjusted
   matched-benchmark analysis can net positive EV even be assessed.

The two kinds of current tests (synthetic GitHub-hosted contract and
PC② Windows fictional digest smoke) verify software functioning only.
A salted digest alone and a GitHub-hosted **runner wall clock** alone
are not an independent immutable cryptographic timestamp. The
`NarForwardPrivateReceiptBinding` therefore always leaves external
proof, official provenance, actual wagers, ROI and positive-EV
authorizations **false**, even when the private hash and receipt match.

The **71 missing training months**, the single 2017-11 official
disqualification/payout discrepancy and absent independent live
forecast/payout provenance still prevent any positive-EV conclusion.


### PC2 integration receipt-binding proof

The private source-free, *fictional only* cross-environment smoke
`scripts/smoke_nar_gh_receipt_binding_fictional.py` is connected to the
existing PC② workflow, rather than accessing any live NAR data.
[Windows PC② Run #42365879724](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42365879724)
completed **SUCCESS** for both steps:

- Existing forward private-snapshot salted-hash consistency.
- New hosted-receipt/private-snapshot binding: exactly 2 fictional
  future races; original hash matched, a changed score was rejected,
  and a forged *later earliest-off time* was rejected.

The Windows runner neither made an actual GitHub dispatch, nor
validated GitHub server `created_at`, nor read a single real NAR
horse record. The standalone hosted contract smoke is
[Run #42365672637](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42365672637)
SUCCESS. The common CI for that code was 979 passed / 33 skipped,
[Run #42365677648](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42365677648).
Actual prospective pre-race proof and real cost-adjusted OOS EV
remain **NOT demonstrated**.


## 2026-11-07 PC2 parallel 72-month preflight: status-aware denominator

A **new private 2017–2022 training-folder diagnostic** computes two
**explicitly separate** aggregate monthly result interpretations over the
SAME licensed, operator-provided local ZIP bytes:

1. The previously established **rank-only strict** official normalizer
   remains the unchanged production training/ROI gate.
2. The *additional, post-event only* `audit_nar_official_exceptions`
   recognizes NAR official margin-status labels for pre-sale scratches,
   ticket-refunded exclusions, DNF and disqualification.
   Status-aware results **do not become released training targets**,
   inferred live tickets or forward-looking features.

The diagnostic is implemented in
`src/horse_racing_predictions/nar_training_preflight.py` and
`scripts/diagnose_nar_training_months_local.py`. Its source ZIP
directory must be expressly permission-attested and contain only
2017–2022 historical training ZIPs. It has no external requests, no
file modifications, no 2023–2024 independent OOS opening and no
2025–2026 protected holdout opening.

[PC2 Win Run #42367627705](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42367627705)
**SUCCESS** and aggregate-only:

| Complete monthly source categories | Rank-only strict | Official-status post-event |
| --- | ---: | ---: |
| 2017-11 flat races individually reconciled | 993 | **1,095** |
| In-scope flat races requiring review | 103 | **1** |
| Predeclared banei out of scope | 132 | 132 |
| Whole month ready for model training | No | **No** |
| Model fit / actual OOS ROI / positive EV | None | **None** |

All **1,228** original races remain in the correct denominator;
exactly **1,096** are predeclared in-scope flat races.
The additional status-aware check resolves **102 of the 103**
formerly unclassifiable flat races, without reinterpreting the
remaining **one** disqualified/winning payout contradiction.
The integrity interpretation coverage for flat races is
**1,095/1,096 = 99.91%**, not model accuracy or realized betting ROI.

[PC2 training ZIP inventory from same run](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42367627705)
still reports **1/72 present, 71/72 absent**. No amount of relabeling
the one downloaded month can substitute for missing training years,
authentic historical pre-race availability or independent forward OOS
predictions. The study remains HOLD, and it would be wrong to report
the accepted 1,095 historical results as a profitable pre-registered
out-of-sample betting strategy.

[Main CI #42367631376](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42367631376)
passed **982 tests (33 skipped, one unrelated warning)**, including
new synthetic-only monthly-status contrast and 72-month scenarios.

The initial PC2 audit
[Run #42367530704](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42367530704)
produced identical correct aggregates but the workflow inherited the
diagnostic CLI's **intentional nonzero exit 3** when 71 months were
missing, so GitHub marked the workflow as failed. The workflow
subsequently normalized only that expected diagnostic-HOLD exit, not
source errors or failed counts, and rerun
[#42367627705](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42367627705)
now correctly reports SUCCESS for the *audit*, while the
*training-readiness status* remains HOLD. No missing ZIP was created
or copied.
