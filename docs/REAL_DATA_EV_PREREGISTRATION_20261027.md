# Pre-registered real-data EV study — 2026-10-27 (Draft PR #142)

**State: FROZEN PLAN / NOT EXECUTED.** This is a pre-registration before inspecting the contents or racing dates of the PC② historical archive. It is NOT a claim that the required years, legal permission, payout data, approved runner execution, or profitable performance exist.

## 0. Immutable safety boundaries

- Existing archive: `D:\JRA-VAN\Data Lab\archive\pre2025` (inventory only: 1 CSV, 7 JSONL, 5,712,754,497 bytes). Its record types, row dates and rights are **unknown**. Never infer RA/SE presence from size/filename.
- Separate 2026 JV-Link quarantine: `D:\HorseRacingPredictions\jravan-private-quarantine`. Never combine with pre-2025 fitting.
- Holdout 2025–2026 is sealed. No inspection for model fitting, threshold choices, selection, or post-hoc iteration. Final holdout analysis requires a separate explicit decision and protocol.
- The additional self-hosted archival *source-byte reading* workflow was rejected by a safety check. **Do not rename, repackage, dispatch indirectly, or recreate the rejected workflow**. The existing count-only metadata workflow does not read source bytes. Human-authorized, permitted local offline review is a separate future gate; none is initiated by this document.
- No JRA-VAN keys, filenames, source rows, horse names, race identities, derived private data or model binaries in public GitHub commits, CI logs or artifacts. No note posting and no real bets.
- JRA-VAN standard private-use permissions do **not** prove rights to reuse JV-Link material in public note publications. See [JRA-VAN terms §7](https://jra-van.jp/info/rule.html) and the [posting guideline FAQ (JV-Link data cannot be posted)](https://jra-van.jp/info/post_guide.html). Research use, commercial/model use, and publication use have separate evidence checks.
- Third-party historical bundles with an Apache/MIT badge but absent upstream lineage or rights are **not automatically licensed** for this research. A dataset author's license label does not by itself prove rights over underlying JRA/netkeiba/provider records.

## 1. Provenance & chronology admission (must complete before any real fit)

The operator first records **locally** the rightsholder, original acquisition channel, contract/version, intended use, permission basis and allowed data retention/derivatives. An independently reviewed source-rights decision must authorize the particular proposed research use. Absence or ambiguity = `NO_GO_RIGHTS`, not a permissive default.

With a reviewed **permitted local execution method**, and only after source-rights clearance, produce a local sanitized aggregate: input-type counts; RA/SE/other counts; full-file year histogram; invalid/unknown dates; duplicate/revised/conflicting records; eligible complete race counts; joined runner counts; source fingerprints kept private; all stages and checks. A 256 KiB prefix sample and file metadata cannot pass this gate. Require every input to be completely scanned; reject any post-2024 row anywhere, malformed fixed-width RA/SE, incomplete source scans and cross-shard conflicts. RA-only or SE-only archives cannot pass as training samples. Keep raw data and sensitive lineage private on PC②. Existing operator-only modules `pre2025_jsonl_chronology_audit.py` and `pre2025_research_assembler.py` remain **unexecuted on the real archive**.

Eligibility also needs independent pre-race timestamps/field availability: final same-race weight, weather, track, post position, final roster-derived ratios, and target-race results must not leak into Friday features. A reconstructed post-race file is NOT proof of what was available on each historical Friday.

Require official final result and **settlement/payout** provenance per race. RA+SE results alone cannot prove realized betting ROI; do not infer a payout from win odds or invent place prices. Handle late scratches, refunds, coupled entries, dead heats, incomplete payouts and short fields by independently justified exclusion, counting all exclusions.

## 2. Evaluation protocol frozen before actual archive dates are inspected

**Primary study**: JRA-only (course codes 01–10), with 2017-01-01 to 2024-12-31 historical candidates; eligibility conditional on actual independently verified coverage. Do not silently move folds to optimize observed results.

| Phase | Fixed calendar years | Intended use |
| --- | --- | --- |
| Development training | 2017–2021 | Race-day chronological feature history and fitting; no market feature or market-dependent row filtering |
| Model/hyperparameter selection | 2022 | Choose one winner CatBoost and one separately fitted outsider CatBoost, using only earlier available data |
| Locked out-of-sample pre-2025 assessment | 2023–2024 | Simulate forecast freeze on the appropriate prior Friday; no refit/tuning on these outcomes |
| Final sealed holdout | 2025–2026 | Do not open or use during this phase |

Any inability to establish sufficient real race coverage across **all** required windows is `NO_GO_COVERAGE`, not a license to shift dates after seeing results. A revised calendar protocol would require an explicitly labeled new pre-registration **before** examining result-dependent performance. Extend to local NAR only in a separate source-specific pre-registration with confirmed NAR data permission and coverage.

### One fixed candidate and stake rule

- At historical forecast cutoff, create and hash a frozen, complete-race **odds/popularity-free** prediction. One independently trained win model selects Top3; a **different target** outsider model selects the best remaining horse. No payout or race-result input enters selection. Document any cases without verified Friday-available roster/attributes as exclusions.
- Primary economic strategy for comparable races of 5+ actual starters: virtual 100 JPY win ticket on rank #1 and virtual 100 JPY place ticket on the independent outsider. No live purchase. Compare against fixed benchmarks (uniform eligible runner, non-market past-form baseline) with identical dates/exclusions.
- Official JRA payout per 100 JPY is joined **after** forecast freeze. For 5–7 starters, place payout applies through second; for 8+ through third. Actual payouts, not odds approximations, determine realized ROI.
- Record all target races (attempted, rejected, missing and accepted) to prevent selective omission and report coverage bias. No backfilled picks for races where a genuine pre-event prediction snapshot cannot be independently supported.
- No 2023–2024 retuning after seeing evaluation ROI; no selecting the best-performing subgroup, track, distance, week or wager type ex post.

## 3. Minimum quantitative evidence and decision

For model quality report race/day count, date coverage, Top1 accuracy, Top3 selection coverage, outsider podium/paid-place hit rate, winner log loss and Brier/calibration, and official-payout virtual ROI for each strategy and benchmark. No single success metric suffices.

For economic uncertainty, resample **whole race dates**, not individual races; present a pre-declared two-sided 95% block-bootstrap interval and a conservative cost/sensitivity analysis. A diagnostic interval based on fewer than 10 distinct racing dates must not be shown. Before any serious economic decision, require at least **60 distinct out-of-sample racing dates and 500 eligible settled races** plus clearly documented exclusions; these are screening requirements, not statistical guarantees. For the **research-only positive-EV candidate gate**, require point-estimate ROI > 0 **and** cost-adjusted lower 95% bound > 0 for the primary fixed strategy, plus positive improvement over the fixed benchmark on the same eligible races, after accounting for alternative models/selection attempts. Otherwise `EV_NOT_DEMONSTRATED`.

Even passing that gate is evidence of historical out-of-sample profitability, **not proof of future expected value**; forward prospective freeze and a separately authorized, untouched final holdout assessment remain necessary. No promotion to note publisher from a research result.

Stop or redesign rather than repeated synthetic-only iteration when rights, RA+SE chronology, actually available Friday predictors, and authorized historical payouts cannot be established. Reassess continuation after documented source feasibility rather than declaring success from a passing CI.

## 4. Exact next authorized handoff

1. Resolve archive **research** rights and the previously refused source-byte-read execution authorization; do not bypass the refusal.
2. Only after those conditions pass, execute a local bounded/full-file inspection that emits **aggregate private review evidence**. Record true RA/SE counts, eligible years and whether payout records exist. No source bytes to GitHub.
3. If and only if admitted, run the existing offline full-file converter/staging flow, retain its `REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING` marker, then independently approve modeling before lifting any training gate.
4. Execute the frozen chronological protocol once with legal pre-2025 records, independent outsider target and real payout history. Keep 2025–2026 sealed and Friday note magazine inactive until independent source and publisher evidence are supplied.

**Progress counter at freeze:** metadata inventory PASS; synthetic CI PASS; source-use rights UNKNOWN; full RA/SE archive scan NOT RUN; pre-2025 legally eligible rows UNKNOWN; real CatBoost fit NOT RUN; real payout ROI NOT CALCULATED; note publication BLOCKED.
