# Phase 11 cycle 45: free pre-purchase exotic-odds route triage (2026-10-10)

**Disposition: BLOCK all acquisition, backfill, EV evaluation and staking.** This is a read-only source-rights and execution-time audit; no racing records, final payouts, or final 2025–2026 holdout were accessed.

## New candidate comparison

| Candidate | Directly evidenced | Missing evidence / risk | Decision |
| --- | --- | --- | --- |
| Team-Nave KeiBa-ODDS-API (GAMBLE-OS) | Vendor describes 3連複 and 3連単 real-time/history odds, while warning of gaps/delays; GAMBLE-OS advertised at **¥14,300 per month** for personal use. | Not free. Vendor notes commercial use needs separate contract. Snapshot timestamp, combination-to-race mapping and ML retention rights have not been independently verified. | **EXCLUDE: paid** |
| KeibaAI-developer/keiba-data-interface | MIT-licensed connector code documents JRA/netkeiba scraping for **win/place odds**, and a JRA-VAN-backed database provider. The README lists trifecta/trio **payout** fields separately from win/place odds. | No demonstrated timestamped pre-purchase trio/trifecta quote API; open-source code license does not license provider data or scraping, ML or retention rights. | **BLOCK** |
| Open PMU API (French racing) | Public API documents race arrivals/results. | Wrong jurisdiction/identity for JRA races; no purchase-time trio/trifecta odds evidence or rights approval. | **NOT APPLICABLE** |
| Local historical odds files | User-owned files could theoretically include timestamped pre-purchase snapshots. | Must establish original acquisition and retention permission, capture timestamp and integrity, exact race/combination identity, actual pre-cutoff purchase availability, and independent pre-2025 provenance. | **BLOCK until independently reviewed** |

Sources checked (accessed 2026-10-10):
- https://www.team-nave.com/system/jp/products/kboddsapi/ (vendor price and coverage; paid)
- https://www.team-nave.com/system/jp/products/kboddsapi/help_attention.html (vendor historical limitations; may be intermittently unavailable)
- https://github.com/KeibaAI-developer/keiba-data-interface (open-source connector scope)
- https://github.com/open-pmu-api/open-pmu-api (results API only)

## Reproducible synthetic-only code status

The uncommitted `exotic_prebet_execution_triage.py` and `test_exotic_prebet_execution_triage.py` from cycle 44 were rechecked against local copies of the **current PR source/quote validation implementations**. The 42 synthetic tests passed locally. This is **not** a GitHub CI result and no provider authorization is implied. The attempted source-file creation was rejected twice by write safety checks after refreshing the branch head; do not bypass the check or claim it is merged.

PR #141 remains Draft. Continue it; do not create a competing PR. Next attempt should first confirm the current head and whether either target file has been added by another writer. If safe write remains unavailable, continue read-only rights/provenance review and synthetic tests.

## Strict OOS entry criteria

1. A **separately approved, free, legally usable pre-2025 development snapshot**, with immutable provenance; never filter `combined/current_history.csv` as a replacement.
2. Provider-authorized, retained, immutable **pre-purchase** trio/trifecta quote history with UTC capture, exact race and ordered/unordered combination keys, refresh interval and purchase-channel-specific cutoff evidence.
3. Freeze training data, feature code, calibration, bet selection and evaluation protocol **before** opening any independent evaluation period. No tuning on 2023/2024 evaluation outcomes.
4. Research-only EV = predecision probability × genuinely available pre-purchase decimal odds; final payout or settled odds are never substituted.
5. 2025–2026 final independent holdout remains sealed. Forward Paper residual v12 and all risk settings remain unchanged. No live betting, paid services or automated acquisition.

No free, lawful, time-stamped exotic odds source is approved at this checkpoint.
