# NAR official CSV feasibility — pre-registered separate study (2026-10-29)

**STATUS: OFFICIAL DOWNLOAD FORMAT LOCATED / RIGHTS FOR ML UNCONFIRMED / NO REAL SOURCE DOWNLOADED / NO MODEL TRAINED / NO EV MEASURED.**

This is an independent **NAR-focused alternative** to the JRA research plan. It does NOT change JRA's frozen 2017–2024 folds, enable JV-Link after trial, mix JRA data into NAR fitting, or unlock the 2025–2026 protected holdout. All rights questions are source-specific. The code here is offline-only and must not use the previously denied PC② archive-read workflow.

## New primary candidate: NAR's own CSV download UI

Official NAR website provides **direct user-initiated ZIP downloads containing CSV files**:
- [NAR download manual, updated 2026-05-21](https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf)
- [NAR monthly calendar/download page](https://www.keiba.go.jp/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop)
- [NAR website terms](https://www.keiba.go.jp/terms.html)
- [NAR secondary-use FAQ](https://www.keiba.go.jp/qa.html)

The manual states race data from **January 1998 onward**; odds are available only from **March 2026 onward**. Monthly `YYYYMM_(timestamp)_race.zip` archives contain three CSVs:
- `YYYYMM_racelist.csv`: race metadata, distance, weather, surface and other race-level fields.
- `YYYYMM_horselist.csv`: entries and histories **plus final finish position, final time, popularity**. **This is a mixed pre-/post-race export: these columns must never be used as pre-event inputs for the same race.**
- `YYYYMM_payback.csv`: official win and place outcomes. In unusual results, there may be **more than one payback record for a race** (manual's dead-heat note). Do not silently drop, aggregate or normalize that case as a standard race.

The monthly ZIPs are updated daily. In particular, an archive downloaded after the result is finalized **does not independently prove which attributes were actually available before the target event**. Freeze timestamps/availability and snapshot provenance have to be established separately. No manual or data download here grants a license for publication or commercial resale.

NAR terms prohibit reproduction/reposting without permission and warn that unusually frequent/bad requests may be blocked. The FAQ disallows commercial secondary use and instructs parties to request a separate data-supply contract. **Operator clicking the official download button is an available user feature, but AI reprocessing, automated bulk retrieval and any later monetization require separate terms review; no automatic provider requests are implemented.**

## NAR-specific study pre-registration, before seeing any actual outcomes

- Scope: **NAR thoroughbred flat racing only**, explicitly exclude `ばんえい競馬`, mixed JRA-only events or other noncomparable competitions until separate rules/rights/coverage are reviewed.
- Proposed years: 2017–2021 training, 2022 selection, 2023–2024 locked out-of-sample; 2025–2026 remain sealed/no fitting/tuning. Years are **conditional on actual NAR coverage**; no retrospective fold changing to chase ROI.
- Prediction time: independently verified historical **pre-off/published** snapshot; no final weight, final roster, race-day weather, post-off statistics, final odds or payout leaked into inputs. *Do not call this a Friday forecast*; most local racing occurs on other weekdays.
- Candidate strategy: independent win model rank-1 and independent outsider-place model, no market odds/popularity in selection. Virtual 100JPY each, except races with unverified win/place settlement rule, scratches, coupled horses or dead-heats (count and explicitly reject, do not drop invisibly).
- Label and payout evidence: require all starters and real final official payout. Do not infer payout from odds and do not merge merely by name or row index. Use track/date/race/horse-number composite IDs; horse names are presentation labels only.
- Locked race dates: exclude future holdout and any ineligible dataset; preserve an attempt/exclusion ledger and fixed nonmarket baseline on the same dates.
- Minimum screening: 60 OOS racing days / 500 eligible settled races; 95% date-block bootstrap on cost-adjusted ROI, lower bound > 0 and positive matched benchmark improvement for a **research positive-EV candidate**. No publication or real betting even if a historical backtest is positive; forward out-of-sample freeze still required.
- Costs and repeat evaluations must be accounted for; synthetics do not demonstrate economic performance. A missing historic pre-event timestamp/entry snapshot means **NO_GO_FRIDAY_OR_PRE_EVENT** for that historical race, not a license to reconstruct it from post-event results.

## Implemented 2026-10-29 adapter and exact limitations

`src/horse_racing_predictions/nar_official_zip_probe.py` (tested with fictional ZIPs) checks only the **ZIP directory metadata** of an explicitly nominated local monthly race archive, including: official-scheme filename, 1998–2024 window, exactly 3 flat internal CSV names, same month, no traversal, duplicate member, encryption or file-size bomb. It reads **no race CSV content**, makes **zero network requests**, does not unzip files to disk, acquire rights, train models or touch the PC② JRA archive.

The output says `NAR_OFFICIAL_FORMAT_CANDIDATE_RIGHTS_AND_ROWS_UNVERIFIED`. An archive with a valid name is **not proof of official origin**. The source contract, provenance, private local file hash, full schema and record quality, settlements, snapshot chronology and source-specific evaluation must still be separately established.

Before implementing a live reader or executing the operator-only CLI, separately confirm NAR permits user-downloaded ZIPs to be parsed/retained for personal ML research and whether any later commercial/derivative service would require a contract. **No automated download/scrape until express authorization.** No NAR input can be routed through the previously refused JRA-VAN Windows archive content-read workflow.

## Explicit source strategy decision

The older [JRA primary protocol](REAL_DATA_EV_PREREGISTRATION_20261027.md) remains frozen. **NAR is the top alternative supplier candidate** because the operator-facing CSVs, 1998+ history, per-race returns and documented schema exist. Do not claim that the "1998 onward" statement proves complete every-race historical entries or payouts. If actual records or pre-event snapshots cannot be validated without rights concerns, report `NO_GO_SOURCE` instead of creating repeated synthetic-only model upgrades.

Current rights gate remains `NAR_PRIVATE_ML_RIGHTS_PENDING` and actual real-data profitability is `EV_NOT_DEMONSTRATED`.
