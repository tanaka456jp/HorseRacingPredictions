# Pre-2025 historical RA/SE multishard staging — research only

Updated 2026-10-27. Scope: Draft PR #142. None of the commands below has
been run against PC②'s real 5.71GB archive, because the additional
host-guarded workflow that would read source bytes was refused.

## Verified technical prerequisites

- [PC2 filesystem inventory #40328165693](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/40328165693):
  exactly **1 CSV, 7 JSONL, 5,712,754,497 bytes**, under the two shallow
  levels scanned in `D:\JRA-VAN\Data Lab\archive\pre2025`.
  No row dates, schema, licence or completeness verified by that inventory.
- [PC2 JV-Link current-week archive #40327376426](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/40327376426):
  2026 private RA72+SE935. **Separate quarantine**:
  `D:\HorseRacingPredictions\jravan-private-quarantine`.
  **Never** use for the 2017–2024 research fitting.

## Offline converter (fictional-test stage)

`src/horse_racing_predictions/pre2025_research_assembler.py` plus
`scripts/stage_pre2025_research_local.py` provide a local-only conversion
routine. Explicit JSONL shard list (no implicit recursive filesystem discovery)
plus a **new** local output directory are mandatory.

Before creating output: fully scan **all** nominated JSONL files using the
2024-12-31 cutoff, verify each RA/SE fixed-length structure and calendar
date, reject any later holdout date or protected path; reject oversized
sources, missing RA/SE, invalid symlinks, insufficient scratch space.

During conversion: read again with bounded line length, recompute each
source SHA-256 and reject any alteration after preflight, recheck each
race's year. SQLite staging on the private local disk collapses revised
race/horse records by data division and name. Only complete 4–18-runner
JRA races with exactly one winner and valid finished positions are emitted
as `research_<year>.csv`. Every output CSV is capped below the existing
400MB strict trainer's limit.

A research-only output directory contains:
- `private_staging.sqlite` (sensitive source-derived local data)
- `research_<year>.csv` (market columns excluded, sensitive *local* data)
- `private_research_manifest.json` (local source hashes, year/yearly counts)
- `REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING` **required**
  (`INCOMPLETE_DO_NOT_USE` on failure)

**No GitHub Actions task executes the converter.** The local CLI is a
future operator-only path, and source rights must be reviewed separately.
If approval is subsequently granted, the approved research CSV must be
transferred through a separately reviewed provenance step; do not rename
or remove the staging marker to silently authorize training.

The strict dual CatBoost trainer **and** strict outsider evaluator invoke
`audit_pre2025_training_csv`; it now explicitly rejects the above
staging marker and protected/quarantine directories. Therefore successful
conversion and model training are separate operations.

## Operator-only illustrative invocation (NOT executed)

After rights verification and only in an authorized private session,
with known exact local source file paths:

```powershell
$env:PYTHONPATH = "src"
py -3 scripts/stage_pre2025_research_local.py `
  --source-jsonl "D:\JRA-VAN\Data Lab\archive\pre2025\<confirmed-RA-source>.jsonl" `
  --source-jsonl "D:\JRA-VAN\Data Lab\archive\pre2025\<confirmed-SE-source>.jsonl" `
  --destination "D:\HorseRacingPredictions\research-staging\<new-private-directory>" `
  --private-research-only
```

Paths above are illustrative: neither the 7 real filenames nor their
provenance have been examined; do not paste these placeholders as commands.
No subscription, bulk JRA-VAN historical option3/4 download, note
publication, raw redistribution, destructive source migration or
autonomous self-hosted read is authorized.

## Acceptance gates before any real backtest

1. **Rightsholder/contract and permitted local use** separately confirmed.
   Kaggle metadata alone cannot override JRA-VAN/netkeiba rights.
2. Real inputs scanned with an expressly permitted execution path, with
   complete chronology and SHA-256 receipts, not a 256KiB prefix sample.
3. Source quality checked for field completeness/duplicate updates across
   shards; year files and train/validation windows declared beforehand.
4. Train the win model and separate outsider model on only pre-2025 data.
   Preserve final 2025–26 holdout untouched until a separately authorized
   final evaluation; no result data enters Friday features.
5. Validate time-ordered top3/outsider generalization and actual betting
   expected-value on independently permissible **historical prices**.
   Predicted ranking accuracy alone does **not** establish profitable EV.
6. Note publication also requires separately verified article/source rights,
   original predictions and live official rosters; keep the magazine inactive
   in the meantime.

**Result of synthetic CI is software readiness only**, not real training,
positive EV, verified rights, or authority to post.
