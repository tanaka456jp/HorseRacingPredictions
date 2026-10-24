# Execution-channel and pari-mutuel settlement gate (2026-10-20)

Scope: Draft PR #141 research only. No live betting, source ingestion, protected 2025–2026 holdout access, model tuning, or Paper promotion. **This is an execution specification, not evidence of positive EV.**

## New independent official-rule check

For Japanese pari-mutuel bets, distinguish **ticket acceptance** from **payout price**. A displayed pre-cutoff odds quote is an indicative payout estimate, **not** a fixed-price fill. Even the official *final* odds can differ from the actual payout because of scratches or dead heats. The settled return must use actual declared payouts (and refunds), never the displayed quote as if guaranteed.

Official JRA rules: https://www.jra.go.jp/kouza/baken/index.html
Official JRA odds glossary: https://www.jra.go.jp/kouza/yougo/w406.html

For a paper opportunity, separate:
- `source_authorized`, `quote_first_seen_at`, `quote_age`, `decision_at`, `channel_cutoff_at`, `submitted_at` (paper simulation only).
- `channel`, `jurisdiction`, `venue`, `race_id`, `bet_type`, `ticket_id`, `stake`, `channel_available`, `accepted` (if independently evidenced), `rejection_reason`, `abstained`.
- `indicative_quote_odds` versus `declared_settlement_payout`, `refunded_stake`, `other_cost`, `net_profit`, `source_rights_receipt`.
- Ticket non-acceptance, unavailable market, abstention, accepted-but-losing ticket, and refund are different outcomes. Do not silently discard any opportunity or interpret an accepted ticket as an odds-locked transaction.
- For **counterfactual** paper trades without actual acceptance receipts, label acceptance and payout-execution assumptions as simulated; do not report them as observed fills.

## Channel-specific purchase cutoff and request capacity

The same race and bet type can be eligible under one purchase channel but not another. Freeze the **specified eligible channel** before comparing policies; do not retrospectively choose the most favorable channel.

| Purchase route | Official normal cutoff | Availability caveat |
| --- | --- | --- |
| JRA A-PAT internet, domestic JRA | Scheduled post minus 1 minute | https://www.jra.go.jp/dento/a/instructions/hatsubai/jra.html |
| JRA A-PAT push-button telephone, domestic JRA | Minus 5 minutes | Same official source; no NAR/overseas through push-button |
| JRA Direct, domestic JRA | Minus 2 minutes | No NAR/overseas; https://www.jra.go.jp/dento/direct/instructions/hatsubai.html |
| JRA on-site facilities | Minus 2 minutes | Facility rules; https://www.jra.go.jp/kouza/baken/index.html |
| JRA A-PAT/即PAT internet for NAR | Minus 2 minutes | Only designated NAR races/dates; A-PAT ordinarily cannot purchase weekday NAR; https://www.jra.go.jp/dento/a/instructions/hatsubai/nar-overseas.html |

Official JRA 即PAT purchase request limits (check applicability to each eligible channel before use):
- Maximum bets per *single internet application*: **255** except WIN5/NAR, which are **50**.
- Maximum application count per racing section: **900**.
- Maximum purchased bets per day: **9,000** across JRA/NAR/overseas combined.
- These are request-count constraints, not proof of liquidity, accepted ticket, quote execution, or profitability.
Source: https://www.jra.go.jp/dento/soku/instructions.html

## Gate implications

1. **JRA:** the legal free race/quote acquisition route is still unapproved; existing JVOpen -301 must not be retried without rights verification.
2. **NAR:** public official same-day ZIP/CSV and intermediate odds are technically documented, but automatic retrieval, retention and ML use rights remain unapproved; do not collect or schedule. 2026 odds overlap sealed holdout.
3. **Execution:** a paper order's theoretical eligibility requires verified channel membership, sales calendar, bet type, account limits, market availability, clock and submission latency. The payout is not fixed by the quote.
4. **Strict OOS:** do not touch sealed 2025–2026 final holdout or Phase 12/13 one-shot; future prospective cohort needs separately authorized protocol.
5. **Economic outcome:** actual approved prebet quotes, settled Forward Paper count, net ROI, paired market delta, day/race cluster CI and SNS incremental net EV are **UNVERIFIED**, not zero. No positive net EV claim.

No personal/account identifiers, provider raw race/odds files, copyrighted SNS posts, or secrets belong in GitHub/Actions. The one-week economic Go/No-Go deadline is unchanged.
