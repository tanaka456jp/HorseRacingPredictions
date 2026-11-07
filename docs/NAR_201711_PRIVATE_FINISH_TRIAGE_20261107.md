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
| Remaining mismatch category | `NAR_WIN_PAYOUT_BOTH_MISSING_AND_UNEXPECTED` |

The anomalous race includes the lone 失格-status row (deduced solely from
aggregate subtraction; no identity disclosed). Published winning-ticket
horse numbers both omit a numeric-rank-first runner **and** include a
different number. It may involve an official disqualification or subsequent
results amendment; this hypothesis has **not** been established as its cause.
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
