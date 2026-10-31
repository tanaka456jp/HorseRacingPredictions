# JRA-VAN trial expired — alternative source development plan (2026-10-29)

**Status: IMPLEMENTED SOURCE INTAKE / NO REAL-DATA BACKTEST.** Scope: Draft PR #142, private research. The user reports that the JRA-VAN free trial has ended and further JRA-VAN download is unavailable. **Zero new JRA-VAN calls or paid subscriptions.** The existing source-byte runner refusal, holdout and publication prohibitions remain in force.

## Confirmed candidate paths; rights are independent

| Source | Availability | What is *not* authorized merely by availability | Current decision |
| --- | --- | --- | --- |
| [JRA official historic results FAQ](https://www.jra.go.jp/faq/pop02/1_6.html) | Race results searchable from 1986; official result PDF from 2002 | Unrestricted bulk scraping, copying, machine-learning reuse, redistributing its pages or race sheets | MANUAL RIGHTS REVIEW; no automated fetch |
| [JRA official website use notice](https://jra.jp/use/) | Official site and rights notice | Reuse of protected site articles/media beyond permitted conditions | PROVIDER TERMS REVIEW |
| [NAR official local racing portal terms](https://www.keiba.go.jp/terms.html) | Local racing results / information | Unlicensed reproduction or automated database extraction | NAR RIGHTS REVIEW; no automated fetch |
| [JBIS-Search terms §8](https://www.jbis.or.jp/terms/) | Browsable JRA/NAR historical racing records | Terms limit information to personal use, require as-is use and explicitly prohibit commercial activity or its preparation even if free; not a general ML/database extraction licence | **EXCLUDE** from this potentially commercialisable research unless separately licensed in writing |
| Third-party CSV/API or open dataset | Possible alternative independent source | Assuming the publisher's GitHub/MIT/Kaggle *code* license covers third-party race records | ACCEPT ONLY WITH UPSTREAM PROVENANCE AND RESEARCH PERMISSION |
| Independently compiled, legally obtained personal observations | Local data owner controls own entries | Assuming source-specific contractual conditions disappear when transcribed | SOURCE TERMS REVIEW |
| PC②'s archived JV-Link data | Metadata inventory only; 5.71 GB / 1 CSV+7 JSONL | New subscription-free access, indefinite post-trial retention, using the previously denied source-byte runner workflow | EXISTING QUARANTINE AND AUTHORIZATION REQUIRED |

The earlier JRA-VAN support reply supports external AI input **for personal use**, subject to care and opt-out when available; it does not independently settle any third-party source's rights or license-expiry terms. Do not use the expired trial as a substitute for independently valid provider rights.

## New source-neutral entrypoint — no scraping

New files:
- `src/horse_racing_predictions/alternative_source_intake.py`: **read-only** local audit and privacy-safe aggregate report for a nominated race-history or official-settlement CSV plus a separate operator-held rights manifest. No network functions, no credential access, no data movement or model fitting.
- `scripts/inspect_alternative_source_local.py`: **human-operated local-only** CLI; sanitized aggregate status. Not wired into GitHub Actions or the blocked PC② runner pathway.
- `tests/test_alternative_source_intake.py`: fabricated-only tests for provenance, license expiry, actual-data hash, separation of payouts and labels, protected-period rows, parent staging markers and known old JV-Link routes.

### Required private manifest (schemaVersion=1)

A local, **untracked** JSON file next to a distinct, already legally obtained CSV:

```json
{
  "schema_version": 1,
  "kind": "history",
  "provider_id": "example-authorized-provider",
  "source_category": "rightsholder_licensed",
  "rights_holder": "Example Rights Holder",
  "acquisition_method": "operator-provided licensed file",
  "rights_evidence_ref": "private-local-evidence-id",
  "rights_scope": "private_noncommercial_research",
  "local_ml_permitted": true,
  "retention_permitted": true,
  "contract_valid_through": "2027-12-31",
  "source_sha256": "<operator-computed SHA-256 of the exact local CSV>"
}
```

This example is **not evidence** of a real provider contract. Use `source_category` = `own_observations`, `rightsholder_licensed` or `verified_open_data` only when supported. The literal `perpetual` term is allowed only for operator-attested verified open data; this program still makes no legal rights declaration. Expired rights and missing ML/retention permission are rejected.

For `history`, the local CSV requires fields convertible to `race_id, race_date, horse_name, finish_position`, with at most 2024-12-31 race dates and strict full-file audit. Independent pre-race Friday availability must be established **before** training; history records containing results do not show the earlier entry snapshot.

For `settlement`, require a separately sourced CSV with `race_id,race_date,horse_name,win_return_per_100_yen,place_return_per_100_yen`. Official payout per 100 JPY should be normalized locally. Zero for losing combinations, nonnegative decimal integers for winners; race/horse keys unique. Having a payout file does not validate official settlement, refunds or special outcomes; those must receive additional evidence checks before calculating actual ROI. Never send payouts into model-feature fitting.

### Manual-only invocation example (only AFTER lawful CSV acquisition)

```powershell
$env:PYTHONPATH = "src"
py -3 scripts/inspect_alternative_source_local.py `
  --source-csv "D:\HorseRacingPredictions\licensed-sources\approved-candidate-2020.csv" `
  --private-rights-manifest "D:\HorseRacingPredictions\private-rights\candidate-history.json" `
  --kind history
```

Illustrative paths: **no files were created there by this PR**. Do not use unknown-source JRA-VAN archive paths or protected holdouts here. An operator must precompute `source_sha256` locally and independently. Never commit the private manifest.

The report deliberately says `PRIVATE_OPERATOR_REVIEW_ONLY_NOT_TRAINING_APPROVAL`: providing a manifest containing `true` is **not a verified legal permission**. Dataset-specific independent review, complete race/payout coverage, pre-Friday feature-timing validation, and a separate authorized approved-for-fit decision still stand between intake and historical model fitting.

## 2026-10-29 independent history+settlement pairing gate

`src/horse_racing_predictions/paired_source_readiness.py` now compares **two separately manifested, operator-supplied local CSVs** after both passed complete per-source admission. The pairing reads complete sorted race/horse records without uploading them and checks strict race/date/horse identity match, complete 5–18-starter standard-rank coverage, normal JRA win/place payout consistency (5–7 starters: 2 places; 8+: 3), duplicate/missing rows, and nonnegative full 100-JPY return semantics. It rejects races with dead heats, cancellations, refunds, coupled starters or incomplete/ambiguous payouts, which require a separate audited settlement protocol.

This test is purely **STRUCTURAL_MATCH_ONLY_RIGHTS_AND_FRIDAY_EVIDENCE_PENDING**: a successful match is **not** a verified official source, immutable Friday-available prediction, legal right to use the records, or a real ROI result. It never attempts to read PC②'s previously disallowed archive, perform web scraping or enable note publishing.

Source-market constraint: odds, popularity, betting prices and settled payouts are kept OUT of the Friday model feature pipeline. The settlement file is only for post-forecast, actual-payoff validation. The frozen 2017–2024 study calendar and sealed 2025–2026 holdout stay unchanged. JRA's own race history and annual PDF site constitute promising discoverable source *information*, not a permission to bulk-download: [official FAQ](https://www.jra.go.jp/faq/pop02/1_6.html), [JRA website use notice](https://www.jra.go.jp/use/). We have **not** acquired or parsed those files.

## 2026-10-29 discovery: NAR's own documented historical CSV download

Priority has changed. The highest-potential **non-JRA-VAN** source is now the official NAR monthly download facility, not unlicensed JRA HTML scraping.

- [Official NAR download manual, updated May 2026](https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf): operator-downloadable ZIP of `racelist`, `horselist`, `payback`; **race data available from January 1998**, but historical omissions are explicitly possible. Betting odds only from March 2026, which does **not** prevent after-the-race payout ROI research if the older payback records are complete.
- [NAR monthly calendar and download UI](https://www.keiba.go.jp/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop)
- [NAR terms](https://www.keiba.go.jp/terms.html) prohibit nonconsensual copying/republication and warn about abnormal request frequency; [FAQ on commercial secondary use](https://www.keiba.go.jp/qa.html) says permission or a data provision contract is required for commercial downstream use.
- [Official NAR inquiry form](https://l-horse.net/anquete/goikengoyoubou), which notes that individualized replies are not guaranteed. Ask **explicitly** whether the offered user-downloadable historical ZIPs may be retained and processed for local, private, non-commercial model training/backtesting. No assumed answer.
- [NAR separate preregistration](NAR_OFFICIAL_CSV_SEPARATE_STUDY_20261029.md) protects a distinct NAR study from contamination with JRA and maintains 2017–2024 conditional chronological folds.
- `nar_official_zip_probe.py` and `scripts/inspect_nar_monthly_zip_local.py` add an **offline-only directory-structure checker** for a legal operator-provided monthly archive. It does not decompress/read the CSV records, and a matching ZIP **does not attest to source authenticity or license**.

Important: the NAR `horselist` contains both entries and **post-event finishes/popularity**. A historical *post-event* monthly ZIP cannot on its own prove a saved pre-event forecast. An actual prospective snapshot is a separate, necessary input. NAR rules for odd race categories, ties, refunds and place payments must be verified independently; do not blindly reuse JRA payout assumptions or claim an NAR backtest based on metadata-only checks.

## Research prioritization / decision threshold

1. **Do not spend on JRA-VAN, JRDB or other paid APIs.** First confirm NAR's official user-downloadable CSV ZIPs may be retained and parsed for this specific non-public research use, and if so verify actual multi-year completeness and pre-event source history in an operator-authorized session. Continue investigating JRA independently; never merge NAR into the frozen JRA primary study.
2. No automatic collection from a third-party site until its authorization for the exact collection method (including automated access and frequency) is independently established.
3. When lawful data exist, run a separate permitted, operator-authorized offline intake and a distinct training approval. The existing frozen JRA window remains **2017–2021 training, 2022 model selection, 2023–2024 independent evaluation**, with 2025–2026 sealed.
4. Keep winner and outsider models independent, use no odds/popularity in prediction, and add official payouts **only after** a frozen pre-race prediction. Assess same-day block bootstrap ROI and fixed benchmarks using the pre-registered gate.
5. If there is no licensed source with the required years/features/payouts, **report NO_GO_SOURCE** and assess whether to redesign or discontinue; synthetic tests are not evidence of profitability.

**Current outcome: source-neutral local adapter + synthetic CI only.** No real alternative source has been downloaded or trained; no claim of expected value improvement or data publication rights.
