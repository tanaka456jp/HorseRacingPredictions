# Synthetic payout/non-fill stress grid (research note)

Status: **synthetic-only methodology; NOT evidence of positive executable EV**.

The local candidate stress grid evaluates the same immutable, frozen, pre-2025
race universe at a bounded Cartesian product of payout haircuts and additional
adverse non-fill budgets. Every cell must revalidate complete race coverage,
chronology, stake caps, protocol freeze, settlement provenance, and identical
market-baseline race/cutoff identity. No observed race result may influence
an actual pre-race selection decision.

The non-fill stress deliberately removes the largest *realized* profitable
hypothetical fills; this is outcome-conditioned retrospective sensitivity, not
a forward-executable fill model, a calibrated non-fill probability, or a
statistical confidence interval. Haircuts applied to settled fictional payouts
are not executable pre-purchase odds or verified slippage bounds. Missing
purchases and abstentions remain in the eligible-race denominator, with zero
realized stake/net, and the frozen market baseline is held constant.

Required safety invariants: reject malformed, duplicate or unbounded grid
axes; reject any cell with invalid input provenance; ensure that more severe
payout or non-fill stress never increases net strategy profit; never infer
absolute profitability from outperforming a losing market baseline. All
results must keep `positive_executable_ev_proven=false` and
`paper_or_live_action_authorized=false` regardless of synthetic arithmetic.

No scraping, JRA-VAN retries or paid calls, actual odds collection, D-drive
source modifications, 2025-2026 final holdout access, live betting, or
Phase12/13 one-shot evaluation are part of this note. An independent official
free-rights review and timestamped purchase-available quote evidence remain
prerequisites for any real-world EV claim.

The separately produced local synthetic candidate and tests are **not**
integrated by this documentation-only commit. CI success for this document
cannot validate those uncommitted files.
