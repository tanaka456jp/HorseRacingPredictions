# NAR pre-off odds: source specification and prospective evidence gate (2026-11-22)

## Official source (verified)
NAR's data download manual (updated 2026-05-18):
https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf

- **Daily** odds ZIP/CSV is updated approximately every two minutes and **can include interim odds** for races held that day.
- **Monthly** odds ZIP/CSV is updated approximately daily overnight and contains **only confirmed/final odds**. Never use monthly odds as pre-off observations.
- The download is made available via buttons on the official race-information page; a ZIP contains CSV.
- Availability and actual quote coverage must be checked from each real snapshot; the published update cadence does **not** guarantee prices are present at any particular observation time.
- NAR's FAQ says odds shown on its web pages are the values at the time the page is accessed and may change: https://www.keiba.go.jp/qa.html

## Actual PC2 finding (read-only aggregate)
PC2 manual audit run https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/44976414396:
- 59 preregistered frozen races, two provenance snapshots, 118 selected race-snapshot rows.
- Source CSV audit totals: market_rows=0, win_rows=0, place_rows=0 in both snapshots.
- 0 valid selected WIN prices or popularity rankings; 0 pre-off usable quotes.
- This establishes missing source rows in these **two captures only**; it does not establish whether the cause is pre-sales timing, a provider data gap, a download anomaly, or another source-specific condition.
- Run's deliberate HOLD/failure is not a verified model-performance result.

## Next prospective protocol (no unauthorized provider requests)
1. Obtain an explicit rights checkpoint for the particular capture mechanism; existing telephone permission for personal use and attributed publication must not be expanded into unrestricted automated polling.
2. Freeze all selections and denominator **before** seeing any odds; preserve commitment and independent timestamp witness.
3. For a future race day, capture the official **daily**, not monthly, odds once at an authorized observation time. Preserve original ZIP and capture/source times locally on PC2. No historical file may be relabeled as pre-off.
4. Count official raw market/WIN/PLACE rows, per-race selected WIN prices/popularity, and pre-off cutoff eligibility separately. Zero rows => source-coverage HOLD; do not silently discard missing races.
5. After races, use independently sourced official settlements; compare preregistered A (all top1 picks) against B (same picks only when verified pre-off popularity >1). Use actual official payouts and include stake, missingness, timing, sample size and uncertainty. Neither interim nor final odds is an executable price guarantee.
6. Publish only aggregate statistics; never upload private raw odds, horse/race-level source records, salts, or ZIP files.

## Stop conditions
No pre-off quote, missing independent witness, absent official settlement, uncertain usage rights, or too-small OOS sample => **HOLD**, not positive-EV proof. No real-money betting.
