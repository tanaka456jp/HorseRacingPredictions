# NAR pre-off odds: source specification and prospective evidence gate (2026-11-22)

## Official source (verified)
NAR's data download manual (check its current revision/FAQ before changing permissions):
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

## Empty-source timing diagnosis (added 2026-11-22)
The real PC2 source audit counts all CSV data rows before filtering by bet type, so a zero market-row count in a successfully parsed ZIP means no parsed data records, **not** merely a failed selection/horse-key match. The provenance audit also already stores pre-off-eligible race counts and minutes to the first scheduled off. The offline readiness audit now reports only aggregate counts of empty ZIP snapshots with future eligible races, and whether a zero-row capture occurred before or after the first scheduled off. These cannot alone explain *why* the source was empty; do not backfill or infer odds.

NAR's current online PDF text FAQ describes a 2-minute maximum acquisition rate, full snapshots (not deltas), and a limited programmatic download allowance for this download feature; website scraping outside that feature remains separate. Recheck the live source and existing rights gate before any automated fetch. No provider request is made by this audit.

## Near-off capture guard (2026-11-23)
The one-shot automatic source capture now rejects attempts when all frozen races are more than 35 minutes away or have 10 minutes or less remaining. It permits the existing private, rights-gated flow only if **at least one pre-registered race is 11–35 minutes from scheduled post**; the recommended manual launch is approximately 20–30 minutes before a target race. This reduces repetitive too-early zero-market snapshots without presuming an opening time. The bounds are an experiment-design choice, not an official NAR sales schedule. Existing source and forecast ZIP files stay immutable. No new provider request occurs from CI or this documentation update.

The live official manual displays a newer FAQ revision dated **2026-09-16** on its first page, while some body pages still carry **2026-05-18**. Do not represent the document as exclusively a May revision. Source: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
