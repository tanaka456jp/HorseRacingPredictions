# NAR telephone permission: private research versus automated retrieval

**Recorded 2026-11-19 — the original date of the telephone call was NOT
supplied.** This document transcribes the *user's report*, not an
authenticated written statement by NAR or legal advice.

## User-reported telephone answer

The user reports that NAR explained: NAR information may be used freely
for **personal use** or for **publishing information on a homepage when
the source is identified**, provided that the purpose is **not resale**.

This is specific authorization as reported by the user; do not erase it
and incorrectly assert that *all* personal use lacks NAR permission.
The site's [terms](https://www.keiba.go.jp/terms.html) generally restrict
unauthorized reproduction and redistribution, so the reported individual
permission is relevant. The [official daily CSV/ZIP documentation]
(https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf) describes an
actual daily odds ZIP download.

This reported answer reasonably supports continuing personal research
with the user's **manually acquired** NAR data, and preparation of
source-attributed *original derived* homepage research. It does not
establish that NAR authorized automated repeated polling of the odds
endpoint, a high-frequency automated feed, redistribution of raw NAR
ZIP/CSV records, resale, or claims of NAR endorsement. The exact
original conversation and call date were not supplied.

When preparing public articles use, for example:

> 出典：地方競馬全国協会「地方競馬情報サイト」
> （https://www.keiba.go.jp/）
>
> 予想・統計分析は独自に作成したものであり、NAR公式の予想ではありません。

No original NAR CSV, ZIP, complete horse/race-level extracts, private
training set, internal salts or source documents may be posted to
GitHub/note/homepage without a separate rights review.

## Implemented usable alternative: OFFLINE manual odds import

The previous odds collector
`scripts/capture_nar_official_daily_odds_preoff_once.py` performs a
real automated HTTP download. It deliberately retains the extra
`verify_private_odds_rights_checkpoint` requirement for that method;
a statement covering *personal information use* is not automatically
proof of permission for *automated polling*.

A separate offline-only tool has now been implemented:
`scripts/import_nar_manual_daily_odds_offline.py`.

1. Before any race, the current eligible full-race forecast must already
   have been frozen and its blinded digest received independently.
   The user must have legally and manually downloaded the published
   daily ZIP from the NAR site's official download button. The tool
   does **not** browse to or fetch the site.
2. Place that day's original unmodified
   `YYYYMMDD_UNIXTIMESTAMP_odds.zip` on the trusted **PC② private D:**
   drive in the `manual-odds-inbox` subfolder of
   `D:\\Development\\HorseRacingPredictions-PrivateReview\\nar-prospective-captures`.
   Preserve the original source. No uploaded cloud attachment is
   needed or desired.
3. From a PC② repository checkout on the development branch, run:

```powershell
$env:PYTHONPATH = (Resolve-Path .\\src).Path
python -B .\\scripts\\import_nar_manual_daily_odds_offline.py --private-capture-dir "D:\\Development\\HorseRacingPredictions-PrivateReview\\nar-prospective-captures"
```

4. The tool accepts **exactly one current-day manual file** in that
   inbox, verifies the original frozen full-roster data, checks the
   current receipt time against the ZIP's official source timestamp
   (freshness <=25 minutes), validates every still-future race
   individually against its off time (>10 minutes lead), blanks all
   no-longer-future WIN/PLACE prices, and preserves the complete
   preregistered denominator. Duplicate import is rejected.
5. It leaves the ZIP in the private inbox and writes a separate
   immutable private, salted audit sidecar. It outputs only safe
   aggregate counts. **No NAR HTTP request is performed**. The
   source hostname itself is only user-attested unless separately
   verified; the receipt is local and not independently hosted, so
   this remains indicative paper research and cannot establish actual
   execution or positive expected value.

The local validation requirements and deliberately inert, synthetic
fixture tests are recorded in
`tests/test_import_nar_manual_daily_odds_offline.py`. The filename
and full private data must NEVER be uploaded to a PR or Actions
artifact. For self-hosted runner execution, first confirm this
manual-only flow does not emit private paths or filenames.

## Distinct unresolved authorization

Before enabling *repeated automated odds downloads*, ask the provider
specifically whether the existing **personal-use** phone permission
includes repeated programmatic access to
`OddsDataDownload?type=daily`, a reasonable frequency cap and local
retention. If NAR does not explicitly allow it, keep the automated
collector disabled and use the manual-only source. An authenticated
provider response is preferable but no written document should be
falsely described as a mandatory condition for the separate,
user-reported personal manual download.

The three-day prospective **feasibility pilot** may begin only when
three future eligible days, all races and the intended timing have
been fixed *before* their outcomes; a private original forecast is
independently witnessed for each day, the user has supplied genuinely
pre-off nonempty manual market observations, and the source rights
are consistent with the provider's reply. An imported ZIP or
synthetic CI success is **not** a demonstrated positive expected value.

**Existing economic evidence remains negative:** 2022 retrospective
CatBoost exploration -24.4076% and a *different* 2026-11-10
prospectively frozen career-form benchmark -38.8136% paper ROI.
Both remain separate. No live bets were purchased.

## Full no-provider-request path: manual RACE -> frozen forecast -> manual ODDS

The manual odds reader requires a previously validated complete pre-off
race source and an immutable frozen forecast. It is **not** sufficient
to put an odds ZIP alone in the D-drive inbox. To avoid any programmatic
NAR provider requests in the entire provenance chain, an additional
offline race importer is now available:

`scripts/import_nar_manual_daily_race_offline.py`

1. On a future race day, well before that day's **earliest** off time,
   personally download the unmodified official
   `YYYYMMDD_UNIXTIMESTAMP_race.zip` from the NAR data-download page.
   Put it in the private
   `D:\\Development\\HorseRacingPredictions-PrivateReview\\nar-prospective-captures\\manual-race-inbox`
   folder on PC②. Do **not** upload it to this chat or GitHub.
2. With the repository's Draft PR #142 code checked out on PC②,
   set the private local directory and run the manual import and then
   the *already-existing* career-form freeze, before the first off:

```powershell
$env:PYTHONPATH = (Resolve-Path .\\src).Path
$private = "D:\\Development\\HorseRacingPredictions-PrivateReview\\nar-prospective-captures"
python -B .\\scripts\\import_nar_manual_daily_race_offline.py --private-capture-dir $private
python -B .\\scripts\\freeze_nar_official_daily_baseline.py --private-capture-dir $private
```

3. The importer accepts only one current-day ZIP from its dedicated
   inbox; validates all races, original entrant list, completion,
   absence of same-day outcome fields and at least 10 minutes
   before the earliest off; and creates the *same* immutable
   salted ZIP + private provenance format required by the existing
   forecast freezer. The existing source importer is reused
   without an HTTP request. A second overwrite or changed source
   is rejected.
4. The career-form freezer creates a complete private selection
   snapshot and a blinded salted digest. The digest must **also**
   receive independent pre-off witness evidence, for example from
   the repository's already-existing GitHub-hosted digest receipt
   workflow, before treating it as an independently registered
   prospective cohort. Running the local freezer alone does **not**
   give independent pre-off proof. Follow the existing separate
   hosted-receipt workflow; never publish a private salt or forecast.
5. After the original roster and full forecast have been frozen,
   *personally* download the official day's
   `YYYYMMDD_UNIXTIMESTAMP_odds.zip` while at least some races
   remain strictly >10 minutes ahead. Move it to the separate
   `manual-odds-inbox` folder on the same private D drive and run:

```powershell
python -B .\\scripts\\import_nar_manual_daily_odds_offline.py --private-capture-dir $private
```

6. Each stage preserves the originals and outputs only aggregate
   status. A price row for a closed/too-close race is blanked,
   **including if the ZIP still lists it**, while the original
   race/ticket denominator is retained. The manual acquisition
   remains user-attested; there is no independent verification that
   a particular file came directly from NAR unless later
   corroborated. The receipt timestamp is the code's actual local
   observation; original filesystem mtime is not accepted as proof
   of pre-off availability. A successful paper read is never proof
   of order execution or positive expected value.

The complete synthetic regression
`tests/test_import_nar_manual_daily_race_offline.py`
proves that the current manual race importer and pre-existing
forecast reconstruction are compatible **without NAR network
calls**. The companion manual odds tests verify strict day,
late/off and no-overwrite guards. Actual nonempty future prices
and the 3-day pilot remain uncollected until the user supplies
real future manual downloads.

**Important:** These instructions are for the user's reported
personal-use permission only. Do not use a scripted headless browser,
periodic HTTP client, scrape loop, or republish the original licensed
ZIPs based on an inference from the telephone statement.
