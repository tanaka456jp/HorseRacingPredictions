# Economic EV gate — pre-deadline decision checkpoint (2026-10-24 JST)

Scope: JRA and NAR, research-only Draft PR #141. This is a **pre-deadline** checkpoint, not a completed profitability study, an authorization to collect, or a declaration that the strategy has negative expected value. Deadline used in the existing research brief: 2026-10-24 02:31 JST. No protected final holdout, PC2 D archive, JRA-VAN RACE -301, paid feed, real bet, or LiveBroker is used here.

## Decision rule (locked to actual executable net returns)

Economic GO requires *all* of the following, for each independent market segment rather than pooled JRA/NAR performance:

1. **Rights & lawful free data:** affirmative rights for research, automated/manual retrieval as applicable, ML, retention and permitted processing, with provenance and revocation conditions. A downloadable ZIP/CSV is not permission.
2. **Pre-purchase odds:** contemporaneous observation and first-received timestamps, provenance, bet-type/runner identity, quote and cutoff. Historical/monthly final odds are *not* purchase quotes.
3. **Execution:** available betting channel/meeting/bet type, cutoff, executable quote, non-fill, odds movement, capacity, bankroll and all relevant costs; paper orders must be timestamped prospectively.
4. **Independent time-forward OOS:** frozen model/policy and thresholds, leakage-free independent forward evaluation, verified official settlements, no access to sealed 2025–2026 final holdout without separately approved independent protocol.
5. **Market-relative net performance:** actually eligible paper sample count, net ROI, market-paired excess profit, race- and day-cluster uncertainty (including downside), and SNS-on versus SNS-off *incremental* net EV if SNS is used. Accuracy or synthetic test passes are not substitutes.

## Evidence inventory at this checkpoint

| Item | JRA | NAR |
| --- | --- | --- |
| Free licensed research data route | Not established | Not established; official ZIP/CSV availability is not authorization |
| Authorized pre-cutoff quote and independent first-seen evidence | Not established | Not established; 2026 intermediate quotes overlap protected final holdout |
| Executable price / bet-type/channel/cutoff/non-fill/capacity | Not established | Not established; channel availability varies by venue and bet type |
| Independently qualified Forward Paper settlements | Unverified count | Unverified count |
| Measured net ROI / market-paired excess profit | **Unmeasured** | **Unmeasured** |
| Race/day-cluster uncertainty | **Unmeasured** | **Unmeasured** |
| SNS-on/off incremental net EV | **Unmeasured** | **Unmeasured** |
| Economic GO | **BLOCKED** | **BLOCKED** |

NAR must be segmented by venue, racing format, channel and bet type; Obihiro ban'ei is a separate racing mechanism. Never join JRA and NAR horses merely by name. The NAR same-day ZIP may include intermediate odds, but the monthly ZIP contains final odds and cannot establish a prior executable quote.

Existing Paper settlement, odds snapshot, model identity and record-timing checks in `residual_paper_evidence.py` improve internal consistency only. They do **not** establish licensed acquisition, official payout provenance, quote receipt authenticity, actual order acceptance, execution cost, or positive net EV. Even an internally consistent synthetic positive bootstrap remains economically ineligible.

## Rights evidence and blocking actions

- NAR official terms: https://www.keiba.go.jp/terms.html — restrictions on unapproved reproduction and abnormal access. Official format guide: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf. General contact and rights inquiry procedure: `docs/NAR_JRA_FREE_QUOTE_RIGHTS_REQUEST_GATE_20261023.md`. No written permission is recorded.
- JRA/JRA-VAN usage rights: https://jra-van.jp/info/rule.html. No demonstrated authorized free continuous pre-purchase quote route.
- No NAR ZIP/CSV, copyrighted SNS post, or protected holdout data may be copied into GitHub or Actions. Do not connect a scheduler before permissions are independently resolved.

## Pre-committed end-of-week recommendation

At 2026-10-24 02:31 JST, if no documented lawful free executable pre-purchase quote supply path **and** no independent market-excess positive net EV evidence have materialized, recommend **freeze further feature development / consider retirement**. This is an economic feasibility decision, **not** a proof that EV is negative. Retain repository and Draft PR #141 unchanged, do not merge, delete, disable schedules or access sealed holdout automatically. A later restart requires a newly documented rights/holdout protocol and prospective validation plan approved separately.

**Current disposition (pre-deadline): MEASUREMENT_BLOCKED; NO ECONOMIC GO.** No claim of measured net ROI or positive EV.
