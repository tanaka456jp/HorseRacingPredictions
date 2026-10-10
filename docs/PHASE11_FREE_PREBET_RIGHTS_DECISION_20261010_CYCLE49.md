# Phase 11: prospective exotic-odds source-rights decision record (2026-10-10)

Research-only. No provider data downloaded, no race results inspected, no final holdout accessed, no purchases.

## New source-review finding

- JRA public site [usage notice](https://www.jra.go.jp/use/index.html) describes its covered domains, links, content rights, and website behavior. It **does not affirmatively grant** automated extraction, ML reuse, or retention of historical 3連複/3連単 odds. Its copyright discussion focuses on audiovisual/article works and is **not** a machine-readable odds-data license. Decision: **BLOCK** until separately verified.
- [JRA-VAN DataLab](https://jra-van.jp/dlb/) explicitly lists a ¥2,090 monthly fee. A software tool described as free to DataLab members is **not a free data source**. Decision: **EXCLUDE** without paid-service approval.
- The JRA official smartphone app is free to install/use, but this does not establish an API, automated-capture right, snapshot-retention right, or executable three-horse odds history. Decision: **BLOCK** pending explicit evidence.
- Existing local data cannot be approved merely because files exist. Each dataset needs independently verified source rights, original file hash, acquisition clock, exact bet-type/combination/race mapping, snapshot timestamp, quote refresh interval, and purchase-channel cutoff evidence. Decision: **BLOCK** until provenance review.

## Required per-source evidence before *any* real-data acquisition

| Gate | Evidence required | If absent |
|---|---|---|
| Cost | Entire capture/storage/ML path is free, not just client software | EXCLUDE |
| Rights | Explicit automated capture, research/ML use and immutable retention permission, with dated terms | BLOCK |
| Time | UTC observed and captured instants; capture strictly before decision and actual purchase cutoff | BLOCK |
| Market | Exact trio unordered / trifecta ordered horse numbers and stable race_id mapping | BLOCK |
| Execution | Verified channel-specific purchase cutoff and quote availability, not merely scheduled post time | BLOCK |
| Integrity | Immutable capture hash, source reference, revision/correction handling | BLOCK |
| Provenance | Independent approved pre-2025 development source; no filtering combined/current_history.csv | BLOCK |

Do not substitute final payouts, after-race odds, scraped snapshots without permission, or 2025–2026 final independent holdout.

## Research-only next step

Continue existing Draft PR #141. The source implementation at `src/horse_racing_predictions/exotic_prebet_execution_triage.py` is present, but dedicated `tests/test_exotic_prebet_execution_triage.py` has not yet been registered. Proposed synthetic regression covers cutoff ordering, stale observations, invalid cadence, mismatched source, prohibited payout fields, and unverified rights. Register it only after re-reading PR head and confirming file absence, then verify CI. If writes remain blocked, preserve tests offline and perform read-only source-rights review.

The source triage must **never** grant acquisition, EV, or paper-staking authorization on self-attested metadata alone. Phase 11 merge and historical evaluation remain blocked by missing independent approved pre-2025 development provenance. Forward Paper settings unchanged.
