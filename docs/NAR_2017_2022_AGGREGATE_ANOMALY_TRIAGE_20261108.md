# NAR 2017–2022 full-training-source anomalies — PC2 read-only research

**2026-11-08, Draft PR #142.** Real NAR private original ZIP data was read
only from the user's approved PC② D: local research folder. None of
the source CSV, individual race/horse identities, underlying payout
amounts, unknown text strings, credentials or ZIPs were posted to GitHub.

## Full predeclared 72-month denominator

[NAR official source ZIP acquisition #42376764634](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42376764634)
had 72/72 original ZIPs present (zero missing). No protected 2023–24
independent OOS or 2025–26 final holdout contents were opened.

[Read-only PC2 source triage #42428719595](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42428719595)
completed SUCCESS with these **genuine historical** counts:

| Category | Exact total |
| --- | ---: |
| Original 2017–2022 race rows | 89,654 |
| Predeclared banei/Obihiro non-flat races | 10,223 |
| In-scope flat races, **full denominator** | **79,431** |
| Strict rank-only validated flat races | 69,484 |
| Strict rank-only unresolved flat races | 9,947 |
| Official-status-aware reconciled flat results (post-event only) | **78,580** |
| Official-status-aware unresolved flat results | **851** |
| Months with zero status-aware anomalies | 17/72 |
| Model training rows actually released | **0** |
| Real expected value / OOS profit evidence | **NONE** |

Math: 79,431 = 78,580 + 851 = 69,484 + 9,947.
No 851 unresolved races were selectively omitted or silently given
zero-value/non-offered/refunded bets.

### Official-status-aware anomaly reasons (851 total)

| Fixed audit code | Count |
| --- | ---: |
| NAR_BLANK_WITHOUT_OFFICIAL_STATUS | **752** |
| NAR_STATUS_AWARE_COVERAGE_MISMATCH | 53 |
| NAR_STATUS_AWARE_PLACE_PAYOUT_MISMATCH | 39 |
| NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS | 3 |
| NAR_DECLARED_STARTERS_INVALID | 2 |
| NAR_STATUS_AWARE_FIELD_SIZE_INVALID | 1 |
| NAR_WIN_PAYOUT_BOTH_MISSING_AND_UNEXPECTED | 1 |

All original training-month identifiers remain present; these are
data/settlement *provenance* discrepancies, NOT 851 proven predictions
that lost money.

### Years with unresolved in-scope flat race outcomes

| Year | All flat races | Status-aware unresolved |
| --- | ---: | ---: |
| 2017 | 13,152 | 81 |
| 2018 | 13,207 | 178 |
| 2019 | 13,203 | 94 |
| 2020 | 13,346 | 141 |
| 2021 | 12,983 | 219 |
| 2022 | 13,540 | 138 |

## Critical source evidence: 752 is NOT 752 fully empty rows

The initial generic reason name `NAR_BLANK_WITHOUT_OFFICIAL_STATUS`
can mean either a truly empty finish/exception field or an
*unrecognized nonempty* official-source value. **Do not equate the
error name to a missing raw source cell.**

[PC2 #42429270859](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42429270859)
**SUCCESS**, using source values only within PC2 memory:

- **750 distinct flat races:** at least one nonempty, *currently
  unsupported* value in the NAR `horselist` official margin field
  beside a blank rank.
- **2 flat races:** known canceled/non-established marker, whose
  own refund/ticket chronology still requires independent proof.
- **0 of these 752 races** fall into the exclusively both-fields-empty
  diagnostic categories under the current parser.

[PC2 lexical-family-only #42429813614](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42429813614)
**SUCCESS**: across those 750 races, **7,559 individual horse
records** have a nonempty unknown text value. Every such value falls
in the **3-to-5-character unknown text family**, not in any of
the fixed classification candidates for ordinary numeric margins,
simple punctuation, NFKC-independent known status abbreviations,
scratch, DNF or disqualification.

**Scientific consequence:** ~10 unknown horse rows per unknown flat
race suggests a *race-level source issue* deserves study, but neither
repeated text nor an absent numeric rank proves official
cancellation or refund. The code **must not** infer that these
were completed races or non-offered bets.

The source specification distinguishes No.32 `着順` from No.34
`着差`, but it does not assign a historical return to every
unrecognized margin text:
https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf .
Its historical-source caveat warns that past records may be absent.

## Conservative settlement decision policy

The [Horse Racing Act enforcement regulation, Art. 7](
https://laws.e-gov.go.jp/law/329M50010000055) defines the place
ticket cutoff by the **number of intended runners when ticket sales
start**, not an improvised postrace headcount. A result/payout
mismatch therefore needs contemporaneous eligibility and official
ticket-refund evidence, not a post hoc favorite cutoff.

Only a separately verified race-level cancellation/void record
can authorize a cancellation policy; a present but unrecognized
character string, blank rank or missing payback is never enough.
Do not fill unknown values with zeros, worst finishes or 100-yen
refunds, and never selectively remove rows to inflate ROI.

Private source is **not** released for public note or GitHub publication.
No historical protected OOS was opened. No authentic pre-off
prospective forecasts, actual purchases, true after-cost realized ROI
or statistical positive expected value have been established.

Follow-up: PC2 is computing whether these 750 cases have *any*
nonempty final-rank cells and whether official win payback cells are
present. It also computes within-month counts of distinct unknown
values without exporting source text; any further resolution must be
based on that evidence, not on assumptions.
