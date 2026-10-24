# End-of-week economic feasibility verdict — 2026-10-24 JST

Scope: JRA and NAR, research-only Draft PR #141. Deadline defined by the existing research protocol: 2026-10-24 02:31 JST. This checkpoint is a **decision on demonstrated evidence and supply feasibility**, not proof of negative EV. It does not authorize data acquisition or model evaluation.

## Decision

**ECONOMIC NO-GO / MEASUREMENT BLOCKED. Recommend freezing further feature development and considering retirement of this research project unless the user explicitly approves a new, rights-cleared independent protocol.**

The five conjunctive gates are not satisfied in either JRA or NAR:

| Gate | JRA | NAR |
| --- | --- | --- |
| 1. Licensed, free, usable real data | BLOCKED: sustainable research rights/route not established | BLOCKED: official download availability is not ML, retention or automation permission |
| 2. Authorized contemporaneous pre-purchase odds | BLOCKED: no eligible verified quote sample established | BLOCKED: same-day intermediate quotes not authorized/validated; monthly final odds ineligible |
| 3. Executable channel/price/cutoff, odds changes, non-fill, cost, bankroll | NOT DEMONSTRATED | NOT DEMONSTRATED |
| 4. Independent time-forward OOS / Forward Paper, official settlements and market controls | NOT DEMONSTRATED | NOT DEMONSTRATED |
| 5. Positive *net* ROI and paired market excess with race/day clustered uncertainty | UNMEASURED | UNMEASURED |

Eligible pre-purchase quote count and independently qualified Forward Paper settlement count: **unverified**, not asserted zero. Actual net ROI, market-relative excess profit, race/day clustered intervals and SNS-on versus SNS-off incremental net EV: **unmeasured** in both markets. Synthetic test results and CI successes are not economic evidence.

## Market segmentation and execution constraints

JRA and NAR must never be pooled to claim profitability. NAR venue partitions: Monbetsu, Morioka, Mizusawa, Urawa, Funabashi, Oi, Kawasaki, Kanazawa, Kasamatsu, Nagoya, Sonoda, Himeji, Kochi and Saga; Obihiro ban'ei is a distinct racing mechanism. Partition further by meeting format, wager type (win/place, wide, quinella, trio, trifecta, etc.) and available betting channel. A quote cannot be called executable without eligibility, actual observed/received timestamp, pre-cutoff order time, channel opening/closing, capacity, non-fill and price-change assumptions. NAR final monthly odds must never be substituted for a pre-race quote. No horse identity join by name alone.

SNS/blog/trackside inputs remain unadopted until lawful access, first_seen_at point-in-time evidence and an independent SNS-off comparison demonstrate *incremental net* economic value.

## Blockers and preservation

- NAR terms: https://www.keiba.go.jp/terms.html ; official format guide: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf . Written permission for automated acquisition, research/ML, retention, external processing and redistribution is not evidenced. Do not start acquisition or schedule polling.
- JRA/JRA-VAN rights: https://jra-van.jp/info/rule.html . Do not retry RACE -301 before rights clearance.
- 2025–2026 final holdout (including 2026 NAR odds), PC2 D archive, private credentials, paid sources, real wagers, LiveBroker and Phase12/13 one-shot evaluation remain prohibited.
- Leave repository, main, Draft PR #141, existing schedules and all runner services unchanged. Do not auto-merge, auto-promote Paper, or delete the project.

## Reopening criteria

Only reconsider the freeze recommendation after independently documented lawful free supply rights, pre-purchase executable quote provenance, prospective paper execution/settlement, frozen OOS design and market-excess net ROI with clustered uncertainty are all available. A new protocol involving protected holdout requires separate explicit approval. No positive EV claim is warranted now.
