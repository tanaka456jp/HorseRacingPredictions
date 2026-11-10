# NAR real prospective pre-off full-roster baseline — 2026-11-10

**Research-only evidence; NOT positive betting expected value.**
Draft PR #142, feature branch only. No merge or actual stakes.
**All 2023–2024 sealed OOS and 2025–2026 protected historical holdout remain untouched.**
This 2026-11-10 data is newly captured prospective *event-day* material, not a
read of historical protected test targets.

## Background: prior betting strategy rejected

PC② private official historical NAR 2017–2021 fit / 2022 exploratory
model-selection study [Run #42630314405](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42630314405)
verified a fixed hypothetical ¥100 WIN + ¥100 PLACE in each of 13,402
retrospectively evaluable races. Historical stake ¥2,680,400;
official gross return ¥2,026,180; net **-¥654,220**; ROI **-24.4076%**.
Whole-racing-day 2022 descriptive bootstrap 95% ROI band
[-26.4668%, -22.1488%]. Gate:
`REJECT_UNCONDITIONAL_2022_POLICY`.
This **cannot** establish real-world prospective returns, since no advance
roster/prediction, independently witnessed preoff price, actual bet, full
operating cost audit or sealed OOS was available. Do NOT mine the same 2022
period repeatedly until the outcome appears profitable.

## Actual official source and reproducible controls

[Official NAR data download PDF manual](https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf)
states daily downloadable race and odds ZIP files update approximately every
two minutes, daily odds may contain *interim* prices, and monthly odds supply
only final/settled prices. Actual fields include `全成績` in
`YYYYMMDD_horselist.csv` and `着順`, `タイム`,
`上がり3F` which may contain **after-event** information.
Never select on those future fields.
[Official NAR FAQ](https://www.keiba.go.jp/qa.html) and
[usage terms](https://www.keiba.go.jp/terms.html) must be respected,
especially redistribution and commercial re-use; no original NAR rows,
ZIPs, horses, race keys or machine paths are published to GitHub.

1. [2026-11-10 PC② original real DAILY race ZIP capture, SUCCESS, #42664266326](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42664266326):
   **59 flat races, 641 registered horses**, earlier than the full
   day's first scheduled off, **2026-11-10 11:35 JST**. Records are saved
   only on PC② private D-drive under
   `D:\Development\HorseRacingPredictions-PrivateReview\nar-prospective-captures`.
   Only an allowlisted 59/641 aggregate appears in public logs. The original
   daily ZIP is accompanied by a private salted SHA256 provenance manifest.
   帯広ばんえい is excluded from flat-race evaluation by a predeclared rule.
   Strict read-only ZIP structural inspection verifies full race/horse roster,
   chronological window, and blank known post-result columns.
2. [2026-11-10 complete real full-roster prospective **historical-career-form
   comparator** freeze, SUCCESS, #42665793590](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42665793590):
   every one of the above **59 races / 641 horses** has private numerical
   frozen winner and top-three score. Winner score uses fixed
   `(career wins+1)/(career starts+10)`; podium score uses
   `(career 1st+2nd+3rd+1)/(career starts+10)`.
   One top WIN and one independently-scored fourth PLACE candidate are
   chosen without looking at any outcome or betting price.
   This is **NOT the 2017–2021 CatBoost model**; it is a prospective
   comparator with no 2022 payout optimization.
   The complete private snapshot, original observation/creation times,
   score and roster manifest, and random 32-byte **PRIVATE** salt are
   persisted on the PC② D drive and never attached to an Actions artifact.
3. The same workflow GitHub-hosted runner reported the **salted,
   privacy-preserving forecast digest only** at
   **2026-11-09 17:34:13Z = 2026-11-10 02:34:13 JST**,
   over 9 hours before scheduled first off.
   GitHub-hosted runner receipt schema:
   `NAR.GitHubHostedRealBlindedDigestReceipt.v1`. Digest
   `7ed594c19a03764aab963daae17233b23aad34c5f53acc94b29f34bbd8f47bdd`
   is public by design; salt, private source, score arrays and candidate
   identities are not. Neither a self-supplied off-time nor a local hash
   on its own proves an official race schedule or race occurrence.
4. [Read-only replay/immutability verification, SUCCESS, #42666625017](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42666625017):
   PC② re-reads the *same original* private ZIP and complete private
   snapshot, reconstructs all 59/641 scores using the original pre-off
   capture/freeze times and private salt, and rejects any changed snapshot
   or digest. The separately re-issued hosted digest remained identical
   to the original receipt. Replays neither overwrite the forecast nor
   re-download the source. Read-only capture rerun also
   [SUCCESS, #42666544815](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42666544815).
   A replay cannot be used to replace a prediction after knowing outcomes.

## Scientific and legal gates that remain OPEN / HOLD

- **No actual pre-off odds snapshots** have been independently captured,
  including WIN and PLACE odds. Source documentation provides them, but
  endpoint/rights/market-open/clock validation remains necessary.
  A final tote dividend or after-event odds is not a pre-off executable price.
- External GitHub timestamps and blinded digest receipt are real, but
  independent comparison of the full frozen private snapshot, full official
  advance calendar, and licensed source rights is still incomplete.
  Our local immutable replay is a useful anti-tamper check, not a neutral
  external audit of every horse or prediction.
- No settlement of actual 2026-11-10 races has occurred in this study.
  At a later *properly authorized* time, post-event payouts can be joined
  strictly AFTER checking the pre-off receipt, without cherry-picking
  missing/scratched/unoffered races.
- With no contemporaneously observed prices or actual stakes, no
  pre-off value-bet recommendation, after-cost empirical ROI, statistical
  positive expected value, live bet permission or public paid article
  authorization can be inferred.
- No source details, private salts, horses, odds, binary models,
  original ZIP bytes or protected holdout observations may be transferred
  to GitHub; only aggregate research metrics and blinded commitments.

**Next methodological step:** identify the officially published current-day
odds download link without inventing endpoints, make a bounded single
private request only when market is actually open and permissible, record
the source download time and entire price/selection coverage (including
missing/suspended prices), and later reconcile against official payouts
and any applicable fees under a predeclared all-races denominator.
The sample must be judged prospectively; do not use 2022 to choose
profitable-looking stake/filter rules. Never conflate simulated payout,
live paper forecast, and an actual verified purchased ticket.

## First genuine official interim-odds capture — still no market quote, 2026-11-10

Official NAR DAILY odds ZIP download:
`https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload?type=daily`
is confirmed by the official NAR download mechanism and ZIP response;
the downloaded source and private matching digest are stored **only**
under the same PC② D-drive private prospective capture directory as the
unchanged race forecast.

**Evidence 1:**
[PC② Action #42716217937](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42716217937)
**SUCCESS** for source download and immutable frozen forecast validation
at **2026-11-10 07:56 JST**, but the actual official file contained
**0 odds records**, **0 WIN records**, **0 PLACE records**. All **59**
frozen WIN candidates and all **59** frozen PLACE candidates are
therefore **missing contemporaneous market prices** at this time. It
would be incorrect to describe this as 118 observed prices, a tradable
event or a positive EV measurement. The source file was generated
2026-11-10 07:56:06 JST and privately received 07:56:29 JST.

**Evidence 2:**
[PC② Action #42716708851](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42716708851)
**SUCCESS** for a second separate NAR official ZIP, generated at
**07:58:06 JST** and received **08:00:04 JST**. It likewise contains
**0 market records**, retains the original 59/641 denominator and
correctly emits status
`PRIVATE_OFFICIAL_ZIP_CAPTURED_NO_QUOTED_PRICES_YET`, instead of
falsely claiming that usable betting quotations were received.

The official file timestamp and PC② request time are two different
attributes; neither is a guaranteed order execution timestamp or a
provider-certified quote-publication timestamp. Missing/unoffered quotes
remain **None**, never 0x odds, an assumed lost bet, or an excluded race.

Implementation:
`scripts/capture_nar_official_daily_odds_preoff_once.py`,
`tests/test_nar_official_daily_interim_odds.py`, and
`.github/workflows/nar-pc2-official-daily-interim-odds.yml`.
The parser recognizes WIN/PLACE rows with official race+horse numbers,
keeps full previously frozen 59-race coverage, preserves both low and
high bounds of PLACE odds if available, rejects stale/late/duplicate or
unfrozen identities, and publishes **only aggregate counts**.
One request per invocation, **at least 150 seconds between captures**,
maximum **six snapshots per day**, and **at least 10 minutes before
the earliest planned first off**. No raw NAR CSV, private salt, candidate
identifier, selected quote, or ZIP is transferred to GitHub.

**Financial status: HOLD.** No observed interim price exists in these
early snapshots, no actual bets were placed, and no 2026-11-10
settlement, executable order prices, positive net EV or independent
out-of-sample return has been validated.

Follow-up MUST be a new bounded quote capture only if the day's
source starts publishing real odds while the entire forecast schedule
is still safely before first off. If late, preserve these early empty
snapshots and label all 118 planned quotes missing; do not retroactively
turn post-off data into a pre-off market observation. Separate
prospective economic evidence will require independent quote timing,
later official outcome settlement, fees and a predeclared unscreened
denominator. None of this allows reselecting the two frozen tickets
using the market values.

## First complete real *prospectively frozen* paper settlement — 2026-11-10

**Now verified on the original 59-race denominator; no race selection after
results.** PC②
[real-data Run #42821912761](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42821912761),
SHA `a32627dfb0440923511566f07f2d36a301895c67`:
**SUCCESS**. The 2026-11-10 original pre-off private 59-race / 641-horse
forecast hash remains unchanged, after-date official NAR result ZIP and
private outcome audit remain on D, and protected historical OOS stays
unopened.

An initial deliberately conservative parser accepted only 52 of 59
races. All seven remaining races contained official **non-numeric
finishes**, not conveniently omittable loses: **2 中止 (started, no
refund), 1 除外 (refunded), 4 取消 (unoffered)**. We separately confirmed
these statuses against the official NAR
[explanation of starters and refunds](https://www.keiba.go.jp/beginner/step2.html)
before completing settlement logic. The update did not change any
race's pre-event selected candidates or their original scores.

The whole-day **predeclared 100-yen WIN + 100-yen PLACE paper scenario**,
with selected exceptional tickets settled by official status rules:

| Metric | Observed |
| --- | ---: |
| Pre-event frozen flat races | 59 |
| Official final race / payout record coverage | 59 / 59 |
| Whole-race outcome reconciliation | **59 PASS, 0 unresolved** |
| Hypothetical attempted tickets | 118 (2 per race) |
| Hypothetical offered-ticket stake | **11,800 yen** |
| Actual official after-event gross dividends on the selections | **7,220 yen** |
| **Hypothetical net P&L** | **-4,580 yen** |
| **Hypothetical return on stake** | **-38.8136%** |
| Original selected bets unoffered / refunded | 0 / 0 |
| Original selected bets losing after DNF | 1 |
| Real tickets or wagers actually purchased | 0 |
| Independent observed usable WIN/PLACE preoff quotes | **0** |
| Verified positive after-cost expected value | **NO** |

Because original licensed pre-off market snapshots at 07:56 and 08:00
contained ZERO odds rows, this computation uses **official final tote
returns** and must be labeled a *paper-settlement scenario*, NOT
a verifiable placed order, executable odds, a true cost-adjusted
prospective betting EV estimate, or independent statistical proof.
The single future day cannot establish positive/negative population EV.
NAR source data is never pushed, and the original sidecar audit is
immutable: subsequent status-aware interpretations are run in read-only
replay against the **same** original post-event ZIP.

**Joint scientific observation:** the first actual forward
career-form baseline day was substantially negative (-38.81%).
The *different* retrospective 2017–21-trained CatBoost 2022 win+place
policy was also negative (-24.41%) but its retrospective model should
not be represented as the 11/10 forward comparator. These are
distinct periods, model definitions, and evidence levels. Neither
demonstrates positive expectancy.
