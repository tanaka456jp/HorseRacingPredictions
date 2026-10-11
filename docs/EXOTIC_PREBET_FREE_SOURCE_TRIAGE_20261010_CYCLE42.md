# Phase 11 free prebet odds evidence triage — 2026-10-10

Status: **NO APPROVED FREE SOURCE; no odds acquired; no EV evaluation.**

1. JRA official website publishes current odds and historical race results. The historical-result FAQ confirms result records from 1986 onward, but **results and final payouts are not timestamped pre-purchase trio/trifecta odds**. The public odds display alone does not establish automated acquisition, ML use, or snapshot-retention rights.
   - https://www.jra.go.jp/
   - https://www.jra.go.jp/faq/pop02/1_6.html
2. JRA-VAN DataLab advertises real-time odds and time-series analysis, but its official published price is JPY 2,090 per month. It is **not an approved free source** under this project's constraints.
   - https://jravan.jp/dlb/
3. A local collector is not a free source merely because the software is free; underlying feed terms, acquisition, research, retention, and price must be verified independently.
4. A prospective candidate must provide a timestamped quote observed and captured before decision time, independently documented purchase-channel cutoff, immutable evidence, race_id, ordered trifecta or normalized trio combination ID, cadence, and explicit rights for automated acquisition/ML/retention. Until independently approved, **fail closed**.

Research-only integration-gate prototype: source/quote identity, decision < cutoff < scheduled post, and quote staleness relative to claimed refresh cadence. Local synthetic checks are not CI proof. Do not enable acquisition, EV, paper staking or live betting based on asserted metadata.

Do not read 2025–2026 final independent holdout, use combined/current_history.csv filtered to earlier years, change Forward Paper, or merge Phase 11 before independently approved free pre-2025 development provenance.
