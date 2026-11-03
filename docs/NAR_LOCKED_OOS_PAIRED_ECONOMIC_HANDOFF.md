# NAR 2023–2024 locked OOS: paired economic research handoff

**Status: SOFTWARE PATH IMPLEMENTED / REAL-DATA STUDY NOT EXECUTED / POSITIVE EV UNDEMONSTRATED.**

This NAR-specific research track is **not** the Friday JRA article flow.
Local NAR races can occur on weekdays, so they use pre-off (not necessarily
Friday) independently frozen forecasts. The JRA 2023–2024 and NAR 2023–2024
research are **independent**. Results must never be pooled to improve a
preselected JRA rule after seeing held-out outcomes.

## Original data and rights

The NAR official [data download manual](https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf)
(2026-05-21) describes monthly ZIP archives with racelist, horselist and
payback CSV data. Historical records can contain gaps. The **finalized**
horselist includes both pre-event-looking attributes and *after-race*
columns such as finishing rank, final time and popularity. Its presence on
a finalized download **is not proof of an authentic pre-off snapshot**.

The [NAR secondary-use FAQ](https://www.keiba.go.jp/qa.html) says commercial
reuse and modified republication of race information are prohibited
without a separate arrangement. The operator reported NAR permission for
data use, but its written scope, acquisition rights, retention and possible
business use must still be matched to the exact proposed research. Do not
interpret an ordinary download button or user-provided JSON
`permissionConfirmed: true` as a rights grant.

No provider request, automated download, JRA-VAN trial renewal, previously
denied archive-read rerouting, GitHub raw-data upload or note posting occurs
in this implementation.

## Frozen analysis protocol

The separately pre-registered NAR flat-racing protocol still governs:

- Training: 2017–2021.
- Model selection: 2022.
- **Locked unseen assessment: 2023–2024** (one preselected candidate win
  and independent outsider model, versus a predeclared separate baseline).
- 2025–2026: unopened, not a source of design/tuning/threshold changes.
- 500 fully settled races and 60 distinct OOS racing dates **minimum** before
  displaying any numeric economic diagnostic.
- Track *all* in-scope races and the fraction with an eligible complete
  candidate/baseline/official-settlement match. Excluding ばんえい before
  outcomes does not conceal missing settlement in the flat-racing scope.
- Every race in the independently verified calendar must have both frozen
  candidate and baseline pre-off predictions and one official settlement,
  or a static, independently documented exclusion code.
- Candidate and baseline must have the **same race field, start time and
  pre-off prediction cutoff**, avoiding comparisons where one model sees
  later information than the other. Distinct model labels alone do not
  prove that baseline fitting was independently performed.
- Candidate and baseline get the **same 100 yen win on rank 1 + 100 yen
  outsider-place** positions per race. This is virtual evaluation only.
  The outsider must be distinct from the winner model's top 3.
- A fixed sensitivity cost of 0–100 yen *additional per race* can be
  applied equally to both research strategies. It is a scenario, not
  a claim that NAR charges such fees.
- Use a whole-racing-day *paired* 95% bootstrap for candidate
  cost-adjusted ROI and candidate-minus-benchmark ROI. Do not treat
  races on the same day as independent samples.
- **Even when both lower confidence bounds exceed zero**, reports keep
  `positive_expected_value_demonstrated = false`, rights and source
  provenance flags false, and betting/publication flags false. Independent
  history rights, authentic pre-off capture timestamps, sufficient real
  holdout outcomes, independent model lock and future forward evaluation
  are still required. Do not infer official payouts from odds.

The code paths are
`src/horse_racing_predictions/nar_locked_oos_economics.py` and
`scripts/evaluate_nar_locked_oos_local.py`, tested with fictional input.

## Explicit local data handoff (only after source and model review)

```powershell
python scripts/evaluate_nar_locked_oos_local.py `
  --reviewed-local-json "D:\ApprovedResearch\nar_2023_2024_reviewed.json" `
  --no-provider-access
```

This path is illustrative; no approved actual file has been located or
prepared by this change. The CLI accepts a **single absolute, actual,
non-symlinked local JSON file** of at most 22 MB; it never discovers
files, scans directories or opens any ZIP itself.

The top-level object must have exactly the following keys:
`schema`, `expected_races`, `candidate_forecasts`,
`benchmark_forecasts`, `settlements`, `documented_exclusions`,
`extra_cost_yen_per_race`.

- `schema`: `NARLockedOOSCandidate.v1`.
- `expected_races`: complete, independently verified NAR
  `NAR:YYYYMMDD:TRACK:01` → `YYYY-MM-DD` map for 2023–2024.
- `candidate_forecasts`, `benchmark_forecasts`: arrays of immutable
  `FrozenOddsFreeForecast` JSON objects; each includes race/day,
  timezone-aware `predicted_at_utc` and `post_time_utc`, fixed
  pre-2023 `model_fit_through_day`, one `model_ref` per series,
  complete win and outsider scores for *all* actual runners,
  and `odds_used_in_selection: false`.
- `settlements`: full independently reviewed `FinalRaceSettlement`
  results, finishing positions and actual per-100-yen win/place payout
  for every runner, zero for misses. Prefer the existing NAR
  strict normalizer and `to_nar_final_settlements`; do not infer
  payouts from prior win odds or popularity.
- `documented_exclusions`: exact race → one of the accepted static
  reasons. No selecting races based on measured losses.
- `extra_cost_yen_per_race`: fixed integer 0–100.

No user identifiers, real horse names, venue names, source paths or licensed
rows are written to a remote CI log: the CLI only prints aggregate counts,
static exclusion reason codes and optional diagnostic returns.

If the study lacks 500 matched races / 60 different dates, the CLI returns
code 2 **with no ROI values**. Error/corruption/unapproved content also
returns code 2 with a non-sensitive failure reason.

## Prioritized blockers

1. Confirm precise NAR source permission and local permitted acquisition mode.
2. Verify that 2017–2021 training records, 2022 selection records and
   independently authentic pre-event feature snapshots actually exist.
   Current post-race CSV alone is insufficient for an honest backtest.
3. Freeze and audit the actual independently trained NAR candidate and
   baseline on 2022 results without inspecting locked 2023–2024 outcomes.
4. Only then independently authorize the sealed OOS assessment and
   concatenate its complete race calendar, authentic forecasts and official
   settlements into the strictly validated *local* candidate handoff.
5. Review fixed costs, same-date correlation, source completeness, test
   attempts and final forward evidence before making any decision to
   continue, redesign or discontinue the strategy.

Passing synthetic CI checks proves arithmetic and safety guards only.
It does not show any improvement in real expected value.

## 2026-11-03 PC② evidence: training source is NOT locally ready

The dedicated self-hosted Windows PC② **DESKTOP-MVV1FD4** completed
[GitHub run #41553689089](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/41553689089)
using two **metadata-only** audits. The four named D-root candidates in
`inspect_pc2_nar_allowlisted_monthly_filenames.ps1` had **zero**
2017–2022 NAR monthly ZIP filenames matching the official candidate name
pattern. Both exact `nar-personal` source locations were absent; **0 of 72**
required training ZIP months were present. This audit does not imply no
archives exist anywhere on the PC or on other machines: it only looked
within the explicitly listed bounded locations and never read ZIP bytes.

To remove ambiguity for **future operator-permitted files**, the self-hosted
[private D setup #41554242564](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/41554242564)
created this **empty** landing on PC②:

```text
D:\Development\HorseRacingPredictions\nar-personal
```

The new directory received restricted Windows permissions for the PC②
runner account, SYSTEM and Administrators. The Git repository now ignores
`nar-personal/` to reduce accidental provider-data commits. No archive
content was read, no download attempted, and no data was copied or deleted.
The workflow is a one-time setup, **not an autonomous downloader**.

When **and only when** the NAR permission's acquisition/processing/retention
scope has been confirmed, operator-acquired original monthly ZIPs can be
placed in this folder under the exact official `YYYYMM_*_race.zip` names.
Do not place JRA-VAN files, protected 2023–2026 OOS files, credentials,
unapproved copies or other datasets in this training-only landing.

The next locally controlled step, after sources have been provided, is a
filenames-only private manifest inventory:

```powershell
python scripts/prepare_nar_private_training_manifest_local.py `
  --local-nar-training-zip-directory "D:\Development\HorseRacingPredictions\nar-personal" `
  --confirm-personal-private-nar-permission
```

That command does **not** read ZIP contents. After 72 months are present
and independently permitted, a separate explicit local content preflight
can be run:

```powershell
python scripts/diagnose_nar_training_months_local.py `
  --local-nar-training-zip-directory "D:\Development\HorseRacingPredictions\nar-personal" `
  --confirm-personal-private-nar-permission
```

**Current deployment conclusion: `NAR_REAL_TRAINING_NOT_READY_0_OF_72`.**
Continue general software safety improvements, but do not claim a real
CatBoost learning run, OOS positive EV, Friday JRA publication readiness
or successful NAR data acquisition. The user's earlier reported NAR
permission is preserved as user-reported context; this run did not inspect
the text of that grant.

## 2026-11-03 PC2 wider source-name audit (read-only)

The bounded filename-only source discovery added by commits 5069a4f, 3657f2c,
f5dcfda, and 27ca3c9 completed on physical PC2 DESKTOP-MVV1FD4.
[Latest PC2 run #41560547709](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/41560547709)
finished SUCCESS (PowerShell static check and PC2 execution).

- D: 8,273 directories and 79,560 entries visited; **zero** exact
  2017-2022 official monthly ZIP names, **zero of 72** distinct training months;
  three broad historical racing *filename hints*, all CSV and >=500 KB.
- Conventional PC2 user Downloads, Documents and Desktop: zero official monthly
  ZIPs and zero generic historical racing filename hints.
- The scan is bounded to depth 8 and skips sensitive directory names and
  reparse points; this is **not** proof of absence across all folders
  or on other machines.
- Each of the three CSV names is only a hint: original provider, rights,
  period coverage, race format, and usefulness for pre-event model features
  have **not been verified**. No content was read, no path/name uploaded,
  no provider was contacted, and no archive was modified.
- No real-data CatBoost fitting, real ROI, positive EV evidence, or JRA note
  publication followed. Protected holdout sources remain unopened.

Next priority: private, non-uploaded review of the origin and rights of the
three CSV hints; require explicit authorization before any source-content
inspection. Acquire proper NAR 2017-2022 original monthly data only through
a permitted operator method. Do not reroute JRA-VAN, post-race labels or
sealed 2023-2026 outcomes into pre-off features or training.
