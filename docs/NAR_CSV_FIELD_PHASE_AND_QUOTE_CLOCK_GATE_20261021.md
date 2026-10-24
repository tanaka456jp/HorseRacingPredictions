# NAR CSV field-phase and quote-clock audit (2026-10-21)

Status: **RESEARCH ONLY / MEASUREMENT_BLOCKED**. Draft PR #141; do not merge. This document is based **only on the official schema/manual and terms**, not on downloaded race, odds, or results rows. It is not an authorization to ingest data, train a model, or access the protected 2025–2026 final holdout.

Official manual (updated 2026-09-16): https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
Official terms: https://www.keiba.go.jp/terms.html

## Specific schema-level leakage and timing findings

The official manual enumerates the following *mixed-phase* columns. A CSV filename/type is **not** a feature-availability guarantee:

| File | Manual column positions | Classification at target-race decision time | Required action |
| --- | --- | --- | --- |
| `horselist.csv` | 32 着順, 33 タイム, 34 着差, 35 上がり3F | Target-race outcome (post-race) | **Never** include as prebet features; separate settlement/results store |
| `horselist.csv` | 36 人気 | Phase/quote clock ambiguous without verified decision-time evidence | **BLOCK** as prebet feature unless independently observed in time |
| `racelist.csv` | 34 上がり4F, 35 上がり3F, 36–50 ハロンタイム, 59–66 コーナー通過順 | Target-race outcome/in-running data | **Never** include as prebet features |
| `horselist.csv` | 18 騎手成績, 25–31 prior-record aggregates | Manual FAQ says aggregates use records before target-race post | Potentially eligible **only** with independent pre-decision receipt and feature-version evidence; a later file is not sufficient |
| `horselist.csv` | 23 馬体重, 24 馬体重増減 | Could be published close to race | Use only if first seen before frozen decision and cutoff |
| `odds.csv` | 1–10: venue, date, race, bet type, combination 1–3, odds, max odds, popularity | **No per-row quote creation/receipt timestamp in listed schema** | A ZIP filename Unix timestamp is not a verified row-level quote clock or client first receipt; **BLOCK executable-price proof** absent separate lawful immutable receipt evidence |
| `payback.csv` | settlement by bet type; manual says dead heat may produce multiple rows | Post-race only | Use exclusively for authorized settlement; never prebet price |

For each **authorized future** snapshot, evidence would need to preserve source/rights approval, race and market identity, actual first receipt time, source version, observed quote, fixed decision time, applicable channel cutoff, channel eligibility, order/acceptance assumption vs actual evidence, refund/settlement, costs, and stake cap. Quote refresh approximately every two minutes is *not* a maximum staleness bound. Neither final monthly odds nor a retrospectively fetched snapshot can certify an executable prebet price. Do not assume a fixed-odds fill in pari-mutuel betting.

**Cross-market:** Separate JRA, each NAR venue and bet type, and Obihiro ban'ei. Never join horses, jockeys, or trainers by name alone (the manual says no unique IDs). Holdout: no 2025–2026 rows may be acquired, read, tuned on, or retested without a separately approved protocol. NAR's published historical odds start in March 2026 and overlap this protected window.

## Economic decision and data-rights status

1. JRA: lawful, ongoing **free** prebet odds plus decision-time provenance not established; JV-Link RACE -301 must not be retried.
2. NAR: same-day intermediate ZIP/CSV is technically documented, but machine collection, retention, ML research rights, independent prebet quote clock and eligible forward cohort **not approved**. Terms forbid unapproved reproduction/republication and warn about abusive access. No automatic download or scheduler.
3. Execution: neither venue/channel/bet-type sale eligibility nor nonfill, stake, costs, indicative-to-declared-payout changes are evidenced by this schema.
4. OOS/Forward Paper: no independently authorized and frozen future evaluation cohort established; no final holdout access.
5. Market-beating **net ROI**: **UNMEASURED**; paired market excess and race/day clustered intervals **UNMEASURED**. Approved sample counts **UNVERIFIED**, not asserted zero.

Nonofficial/SNS candidates require their own lawful source rights, `published_at` and `first_seen_at` before decision, independent identity mapping and identical-market baseline comparison. SNS incremental net EV **UNMEASURED**; no automatic collection authorized.

**Decision: MEASUREMENT_BLOCKED / NO-GO candidate.** This is a fail-closed schema audit, not a positive-EV result or a reason to extend the one-week deadline. If no lawful free quote supply route and independently credible positive net ROI are established by the existing deadline, recommend freezing/retiring research; do not delete the repo, stop tasks, merge PR, place real bets, or promote Paper automatically.
