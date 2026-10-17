# 2026-10-17–2026-10-24: purchase-time EV evidence week (research only)

**Scope:** Existing Draft PR #141. Main stays stable. Scheduled hourly for seven days. Commit
only guarded, testable, research-only improvements that do not require paid access.

## Economic research objective

Change the central question from “did the model rank winners slightly better?”
to: **could a frozen model have identified, before each actual purchase cutoff,
a permissible quote and a ticket whose eventual expected net value is positive,
under a defensible uncertainty interval and realistic executable-price stress?**

No historical finalized dividends, post-race odds, or ex-post selected races
may be substituted for purchase-time quotes. If any essential proof is
unavailable, report **not established**, not “positive EV”.

## Sequential milestones (run each cycle against latest GitHub reality)

| Order | Goal | Artifact / gate |
|---|---|---|
| 1 | Prebet quote/probability/provenance join by canonical race and combination | Fail-closed synthetic test suite, no result fields |
| 2 | Counterfactual price stress: lower probability bound, odds haircut, per-ticket fixed costs | Transparent per-unit break-even and conservative EV diagnostics |
| 3 | Race-cluster chronological OOS evaluation of calibration and net outcomes | No probability estimate calibrated on future rows; bootstrap with races, not correlated tickets |
| 4 | Evidence ledger: quote observed/captured, forecast frozen, decision, cutoff, replay hash, missing/changed odds | Paper-only immutable records; no modified quote retrofits |
| 5 | Compare fixed market/no-bet baseline, selection coverage, missed purchase windows and attempted vs matched quote ratio | Include ALL eligible opportunities; no survivorship / cherry-picking |
| 6 | Stress test worse prices, odds movement, fees, delayed capture, non-fill, liquidity, and quote TTL | Report losses and uncertainty; do not assume price execution |
| 7 | Produce explicit go/no-go readiness report based on independent quote rights, RACE provenance, calibration, and strict OOS forward evidence | No ROI/profit claims without evidence; prioritize blocked dependencies |

## New conservative arithmetic prototype

`audit_conservative_exotic_ev` uses the existing
`triage_exotic_prebet_execution` evidence boundaries and hypothetical
quote, forecast and fee inputs:

- Verify canonical 3連複 / 3連単 match, exact source evidence and strict quote
  temporal order; reject stale quotes or missed cutoffs.
- Verify predicted probability and **lower** bootstrap confidence bound,
  model freeze timestamp, SHA-256 provenance, validation through 2024 only,
  and at least 30 *self-reported* validation races.
- Reject a flat cost/price haircut specification missing or malformed.
- Under transparent hypothetical assumptions compute:

`adjusted_return = observed_decimal_odds * (1 - odds_haircut)`

`net_EV_per_stake = p * adjusted_return - 1 - flat_cost / stake`

`break_even_p = (1 + flat_cost / stake) / adjusted_return`

- Both mean and lower-bound estimates are **diagnostics only**. A claimed
  bootstrap method or hash is merely self-attested; the computation does not
  independently validate calibration. The haircut is NOT a guaranteed
  executable payout, especially for pari-mutuel pools. Never produce an
  executable bet, even when the lower-bound arithmetic is positive.
- Zero or negative lower-bound EV never becomes “positive” because the
  point estimate looks appealing.

## Hard blockages and prohibited actions

1. Prior official JRA-VAN RACE acquisition returned **JVOpen -301**. On the
   PC2 D-drive archive, RACE is absent and the bounded one-shot Phase 12/13
   evaluations remain untouched. Do not retry provider access or read usage keys
   before independent verification of lawful, zero-cost research entitlement.
2. Independently approved FREE, timestamped, retained pre-purchase 3連複/3連単
   quote sources have not yet been established. Self-reported rights are not
   executable-price proof. No paid data and no unauthorized scraping.
3. Never access the 2025–2026 sealed final holdout for model construction,
   research tuning, or synthetic diagnostics. Preserve immutable D-drive originals.
4. Never place a real bet, enable LiveBroker, or upgrade PaperBroker by default.
   No production EV approval can be conferred by a passing synthetic test.
5. Do not merge PR #141 into main without an explicit review of the large
   branch and approval boundaries.

## Reporting convention

For each hourly run: record new commit(s), CI run and result, actual evidence
produced, remaining blockers, and next incremental experiment. If a run
cannot proceed, report why instead of fabricating development, profit, or a
background execution that did not occur.
