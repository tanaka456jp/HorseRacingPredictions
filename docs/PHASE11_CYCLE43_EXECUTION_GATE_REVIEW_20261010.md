# Phase 11 cycle 43 — purchase-window gate review (2026-10-10)

Status: **RESEARCH ONLY / NO APPROVED FREE ODDS SOURCE / NO EV EVALUATION**.

## Verified repository baseline

- Existing Draft PR #141, branch `research/exotic-longshot-race-centered-phase11`.
- Latest reviewed CI: 37992110502 (success at PR head 7163f7d).
- Existing `exotic_prebet_odds_contract.py` and `exotic_odds_source_triage.py` reject unknown fields and never approve acquisition or EV.
- The proposed `exotic_prebet_execution_triage.py` and corresponding tests from cycle 42 are **not committed**. Source-file creation was rejected by write safety checks in this cycle as well. Do not describe the existing CI as covering them.

## Concrete integration gap and fail-closed rule

Source-rights triage and quote-shape triage are separate. A future executable-price review must *jointly* establish:

1. Exact provider identity and source-reference match between the quote and the independently reviewed rights record.
2. `observed_at <= captured_at <= decision_at < purchase_cutoff_at < scheduled_post_time`, with timezone-aware timestamps and an independently evidenced cutoff for the actual purchase channel.
3. Observed quote freshness against a documented update interval, without assuming that a quoted price was guaranteed executable.
4. Independent approval of zero-cost access, automated acquisition (if any), ML research, immutable capture and retention rights.
5. Exact race and trio/trifecta combination mapping; trio unordered, trifecta ordered. Never treat final payouts or settled odds as pre-purchase quotes.

All unverified conditions block use. Passing a synthetic metadata check must **never** authorize acquisition, EV evaluation, Paper staking or live betting.

**Regression issue in the local cycle-42 prototype:** if `source_evidence` is not a mapping, its unguarded `.get` call can raise `AttributeError` rather than returning `blocked`. Guard both mappings before accessing fields, and add `None`, list, and string source-evidence regression cases. Also validate cadence as a bounded positive integer before constructing `timedelta`.

## Free source review (no collection performed)

| Candidate | What is actually evidenced | What remains unverified | Decision |
| --- | --- | --- | --- |
| JRA public odds display | Current odds are publicly viewable; an independent technical tutorial describes accessing dynamic trifecta odds. | JRA permission for automated retrieval, model training, time-series storage; exact quote update clock and purchase-channel cutoff. A tutorial is not a license. | BLOCK |
| JRA-VAN DataLab | Official developer response says historical real-time feed availability is limited to one week. | Free access; historical backfill and relevant permissions. Product is paid. | EXCLUDE under zero-cost rule |
| Local/manual odds snapshots | Technically possible to timestamp and hash user-owned files without contacting any provider. | Original source rights, time-of-capture provenance, pre-purchase status, race/combination mapping, ML and retention permission. | BLOCK until individually approved |
| Final race results/payout files | Historical result and payout data exist. | They are not purchase-time quotes. | NEVER substitute |

References:
- https://www.jra.go.jp/
- https://developer.jra-van.jp/t/topic/979
- https://ken3memo.hatenablog.com/entry/2025/12/15/182142

## Next safe implementation steps

1. Continue PR #141; no parallel branch/PR. Retry the cycle-42 source/test files only after checking current PR head and target paths; on another refusal, do not bypass safety checks.
2. Add synthetic-only tests for invalid/non-mapping source input, stale quote, mismatched source IDs, malformed cutoff evidence, and decision/cutoff ordering. Keep all approvals hardcoded false.
3. Run normal CI and, if available, a *synthetic-only* self-hosted workflow; never launch a Phase 11 real-data workflow while provenance is missing.
4. Require independently approved, legally usable **pre-2025 development snapshot provenance** before any 2023/2024 evaluation or main merge. Never filter `combined/current_history.csv` as a substitute.
5. If legally usable timestamped prebet odds eventually become available, freeze training, selection policy and EV thresholds *before* any strictly isolated evaluation. Compute research-only `EV = p_predecision * executable_decimal_odds`; never tune on evaluation results.

No 2025–2026 final holdout, final payouts as prebet prices, paid data, Forward Paper changes, or live tickets are permitted.
