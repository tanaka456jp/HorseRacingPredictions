# Pre-decision exotic-odds source and schema evidence gates (2026-10-10)

Status: **NO SOURCE APPROVED**. Research/documentation only. No network acquisition, historical result read, live bet, or EV approval.

## Source evidence and limits

| Candidate | Source-backed technical finding | Still missing | Decision |
| --- | --- | --- | --- |
| JRA public odds pages | The official JRA site offers odds navigation. | Explicit automated retrieval, derivative ML use, retention permission; per-combination source observation time; replayable purchase-time snapshot; race mapping. | BLOCK automated collection |
| JRA-VAN JV-Link realtime (JVRTOpen) | JRA-VAN staff (2026-08-25) states realtime data availability is **one week**, not a pre-2025 historical archive. Official FAQ confirms JVRTOpen for realtime data. | Free ongoing access, ML/reuse rights, provenance and availability at decision time. DataLab membership is not assumed free. | BLOCK acquisition; historical backfill unsuitable |
| Jv Odds Visualizer | Listed as freeware on JRA-VAN DataLab site; software claims it can capture 8 bet-type quote trajectories, including trio/trifecta, **on days recorded**. | Underlying DataLab access rights/cost, source-side timestamp fidelity, combination export, race mapping, retention and ML permissions. Freeware application does **not** imply free odds data. | BLOCK acquisition |
| Local/manual snapshots | Prospective research design could preserve manually recorded evidence. | Independent legal provenance, pre-decision timestamp, immutable source capture, full combination IDs, clock verification. | BLOCK EV until independently reviewed |
| Final payouts/results | Post-event returns are available in many places. | They are not a purchasable pre-decision price. | PROHIBITED as prebet odds |

Primary references:
- https://www.jra.go.jp/use/
- https://developer.jra-van.jp/t/topic/979/2
- https://jra-van.jp/dlb/sdv/faq.html
- https://jra-van.jp/dlb/sft/lib/jv_odds_visualizer.html
- https://www.jra.go.jp/

**Interpretation:** the freeware recorder is an architectural example, not an authorized free data source. Do not install, subscribe, activate trial, scrape, or call provider endpoints without verified terms and authorization.

## Strict schema gap discovered on PR #141

The quote inspector in `src/horse_racing_predictions/exotic_prebet_odds_contract.py` blocks six named post-event keys but currently accepts arbitrary additional keys, such as `winning_combination`, `dividend`, `final_return`, `finish_order`, or `metadata`. These can reach `human_review_required`. Both `approved_for_ev` and `approved_for_acquisition` nevertheless remain **false**, so this is a **future-proofing / data-minimization** issue, not evidence of live EV authorization.

**Required change before extending consumers:** use an explicit allowlist of the existing 11 quote fields; reject every unrecognized field, including unknown nested metadata. Preserve the six explicit forbidden-field checks, unchanged quote ordering, and the review-only approval flags. Synthetic regression suite: 12 unknown-field rejections plus one valid-review-only case. Prior isolated local patch evidence: 49 PASS (36 existing synthetic contract checks + 13 new checks). These tests are not part of GitHub CI.

On 2026-10-10 the existing-file update was attempted twice on PR #141 with a freshly read branch HEAD and blob SHA. Both writes were refused by tool safety checks. No alternate write path, direct-main update, or force push was used. This documentation does not assert the runtime bug is fixed.

## Preconditions for future strict-OOS EV work

1. Independent **approved** free pre-2025 development source, demonstrably not filtered from combined/current_history.csv; license and lineage verified outside self-asserted metadata.
2. Legitimately obtained trio/trifecta per-combination quote snapshots with observed/captured/decision/post timestamps, source evidence, race and combination IDs, refresh cadence and retention rights. Reconcile changed start times and missing/zero/unavailable prices.
3. Freeze conditional longshot + partner-pair selection, calibration and stake rules before any untouched OOS evaluation. Never tune on 2023/2024 annual results or access the 2025–2026 final independent holdout.
4. No final payouts as purchase-time odds; no changes to Forward Paper parameters; no live wagering.

Next cycle: re-read PR head and quote-contract blob SHA; safely retry the same minimal allowlist change and add its synthetic regression tests **only if** the guarded write path permits. Keep Phase 11 Draft and unmerged pending independent source provenance.
