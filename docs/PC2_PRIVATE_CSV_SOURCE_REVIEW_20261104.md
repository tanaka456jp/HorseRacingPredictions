# PC② private CSV source-origin review — 2026-11-04

Status: **PRIVATE METADATA REVIEW CREATED / SOURCE ORIGIN NOT VERIFIED / NO REAL ECONOMIC EVIDENCE**.

## GitHub evidence (no private race records)

- Branch: `feature/weekly-odds-free-note-20261021`, Draft PR #142.
- [PC② private source review Run #41734460798](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/41734460798): both PowerShell static contract and physical Windows PC② job **SUCCESS**.
- Read-only scan matched three generic 2017–2022 racing CSV filename hints on D:, all >=500 KB. **0** were categorised as identifiable NAR-name hints; **0** as identifiable JRA/JV-Link name hints; all **3 are of unknown origin**. A generic filename does NOT establish the provider or the licence.
- PC② local-only review metadata was stored **outside the Git worktree**, with restricted Windows directory permissions. Only aggregate counts are logged to GitHub.
- No original CSV bytes read, uncompressed, uploaded, copied, modified, trained on or evaluated. No official monthly 2017–2022 NAR training ZIP located by the preceding bounded D scan (0/72 verified months). Neither result proves absence on other machines or excluded directories.

## On PC② only — inspect the private inventory

The following command **prints paths and filenames to the local PC② console only**. Never paste its raw output into GitHub issues, Actions logs, an AI service, or a public note without screening it.

```powershell
$root = 'D:\Development\HorseRacingPredictions-PrivateReview'
$reportFile = Get-ChildItem -LiteralPath $root -File -Filter 'candidate-metadata-only-*.json' |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $reportFile) { throw 'LOCAL_PRIVATE_REPORT_MISSING' }
$report = Get-Content -LiteralPath $reportFile.FullName -Raw | ConvertFrom-Json
$report.candidates |
    Select-Object fileName, path, sizeBytes, reviewCategory |
    Format-Table -AutoSize
```

A local operator must classify each original file by provider, original licence/contract, acquisition mode, year and record coverage, whether it was legally retained, and whether its **historical feature snapshots existed before each race's off-time**. Never treat labels, payouts, odds or finalized result fields as historical feature values. The review result remains private and is not a new model input.

## Research continuation gate

1. If any of these CSVs proves to be a valid, independently approved research source, use the existing **local-only provenance/rights manifest and source intake audit** first. Do not bypass a prior JRA-VAN archive-access refusal.
2. If none qualifies, use NAR's officially documented monthly race-data page only through the acquisition mode explicitly permitted by NAR. The user's reported grant is not an independently verified authorization for automated bulk download, external redistribution or commercialization.
3. Require a source-complete 2017–2021 training history, 2022 model-selection data and feature-as-of checks; do not assume a finalized post-race horse list proves a pre-off snapshot.
4. Keep 2023–2024 locked OOS unopened until a frozen independent candidate and benchmark, permitted source, correct complete field and official payouts are available. Enforce **500 races / 60 racing dates**, 95% whole-day paired intervals and acquisition/cost-adjusted realized ROI, and separately review any prospective forward evidence.
5. Do not auto-publish JRA Friday note predictions without verified Friday-available data and model/publication evidence.

**Positive expected value has NOT been scientifically demonstrated.** The CI's fictional CatBoost regressions certify code behavior, not historical or future profitability.
