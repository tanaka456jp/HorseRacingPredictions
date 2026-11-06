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
- Official NAR fields, 2017 historic-data caveat and **multiple payback rows on dead heats**:
  https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
- Official NAR labels: 取消, 除外, 中止, 取止, 不成 and numeric 降:
  https://www.keiba.go.jp/Howtoread/theracecard.html

| Fixed aggregation | Count |
| --- | ---: |
| Source denominator (races in the three official members) | 1,228 |
| Predeclared Obihiro/banei out of flat scope | 132 |
| Flat-source races in study scope | 1,096 |
| Strictly complete results + one-row win/place settlement | 989 |
| Flat races currently requiring adjudication | 107 |
| Of the 107: blank-finish races | 103 |
| Of the 107: rank-tie races without multi-row payout | 3 |
| Of the 107: distinct multi-row payout | 1 |

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
Distinct payback rows are identified as an official multirow settlement case,
not silently deduplicated. Every race remains in the 1,228-race denominator.

Current strict validator requires all final rank/settlement semantics to be
known. Thus **989 strict acceptances, 132 prespecified out of scope and 107
in-scope unresolved** is an accurate remaining HOLD, not a reason to train
on the 989 successful races alone. The error labels now distinguish
`NAR_OFFICIAL_BLANK_FINISH_STATUS_UNRESOLVED`,
`NAR_DEAD_HEAT_PAYOUT_SETTLEMENT_UNRESOLVED`, and
`NAR_OFFICIAL_MULTIROW_PAYOUT_SETTLEMENT_UNRESOLVED`.

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
