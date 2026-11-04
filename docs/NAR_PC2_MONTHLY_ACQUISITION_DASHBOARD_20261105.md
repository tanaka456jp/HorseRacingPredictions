# NAR 2017–2022 private, operator-assisted acquisition dashboard (2026-11-05)

**Status: OFFLINE FILENAME CHECKLIST ONLY — NOT AN ACQUISITION OR REAL-DATA ROI RESULT.**

## Verified official route

NAR's official [May 2026 data download manual](https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf) says monthly **race** ZIPs include `racelist`, `horselist` and `payback` CSV and are accessible by manually pressing **レース情報** on the [monthly race schedule](https://www.keiba.go.jp/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop). The historical race information period starts in 1998; historical monthly odds only start in March 2026, so **2017–2022 historical odds are not supplied in that official monthly download channel**. Historical data may be incomplete. This changes neither the data-use permission checks nor the absence of authentic historical pre-off racecard snapshots.

Do not confuse the NAR's [association monthly business statistics](https://www.keiba.go.jp/association/past_records.html) with the **monthly race-level ZIPs**.

NAR [site terms](https://www.keiba.go.jp/terms.html) apply, and the actual scope of the user's reported NAR permission remains **unverified by this software**. The workflow does not scrape or call the site; a human operator must confirm that acquisition and local usage are within the permission given. Do not automate downloading without separate verified authority. Never put JRA-VAN, JV-Link or 2023+ sealed holdout data in the private training landing.

## What this change actually does

Commit the following **source code only**, not any racing dataset:

- `scripts/create_pc2_nar_manual_acquisition_dashboard.ps1`: On **physical PC② DESKTOP-MVV1FD4** only, inspect immediate file **names and sizes only** inside `D:\Development\HorseRacingPredictions\nar-personal`. For each of the **72 months** (Jan 2017–Dec 2022), label missing, exactly one plausible official ZIP filename, duplicated ZIP name candidates or an invalid-size candidate. Do not open or decode a ZIP or CSV, search the wider disk, move/copy sources, or call any provider.
- `.github/workflows/nar-pc2-manual-monthly-acquisition-dashboard.yml`: Static PowerShell parse and forbidden-operation contract, then one self-hosted PC② run. Log **only aggregate counts**, never specific source file paths, filenames, race IDs or horse names.
- Write a local, self-contained HTML checklist to the private review folder, with one navigation link per month to the official **year** page (the operator selects the month there). Source files are downloaded **only if a human chooses**; HTML does not fetch anything.

The report resides outside the Git worktree and has restricted Windows ACL for the runner user, SYSTEM and local Administrators:

```text
D:\Development\HorseRacingPredictions-PrivateReview\nar-training-72-month-manual-acquisition.html
```

The source landing remains:

```text
D:\Development\HorseRacingPredictions\nar-personal
```

## Operator sequence, ONLY after permission is reviewed

1. On PC②, open the **local HTML checklist**, select the official-year page for a missing month, choose that month on the NAR page, and manually download **レース情報** rather than monthly odds.
2. Preserve the original NAR-generated filename `YYYYMM_(timestamp)_race.zip`. Store authorized 2017–2022 files in the private source landing, retaining a separate local record of their provenance and permission. Do not replace original downloads silently or add an archive from an unidentified provider.
3. To refresh the HTML manually on the physical PC②, run from an up-to-date clean checkout:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\create_pc2_nar_manual_acquisition_dashboard.ps1"
   ```
4. **A green/name-present month is not a fully valid month**. After independent rights/source review, use the existing `prepare_nar_private_training_manifest_local.py` for the 72-month filename inventory, then `diagnose_nar_training_months_local.py` for authorized **2017–2022 only** archive structure and completeness. No training or payouts should be inferred from the HTML page.

The three unrelated D-drive historical racing CSV filename hints remain **origin-unverified, untouched and ineligible**. None has been imported. NAR 2023–24 OOS remains unopened and 2025–26 protected holdout remains unopened.

## Why this matters

The project cannot quantify realized profitable or unprofitable racing strategy performance until it acquires independently permitted real historical entries and verified settlements and reconstructs honest **as-of** features without target information leakage. The actual NAR manual permits an operator to navigate to a race-level monthly ZIP; the offline private checklist removes the repetitive 72-month bookkeeping, **not** the separate manual download and rights verification gate.

Passing the simulated CI or completion of this checklist is never evidence of real positive expected value.
