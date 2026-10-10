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


## Cycle 50 update: official JRA-VAN free-trial route is a conditional candidate

Official evidence reviewed on 2026-10-10:

- JRA-VAN states that the Data Lab/JV-Link trial runs for one month from installation and that no charge occurs unless the user completes the purchase procedure:
  https://support.jra-van.jp/jravan/detail?category=2&id=431&site=SVKNEGBV
  https://jra-van.jp/dlb/dlrt_tar.html
- In the official JRA-VAN developer community, JRA-VAN staff answered that individual research use through the official SDK is acceptable under the individual Data Lab terms, while warning against excessive/unexpected access:
  https://developer.jra-van.jp/t/topic/964
- JRA-VAN staff also states that 3連複/3連単速報系 data are available through JVRTOpen and that the relevant速報提供 period is one week:
  https://developer.jra-van.jp/t/topic/979/2

Decision:

- **Do not classify Data Lab as categorically paid-only while a legitimate local free-trial entitlement is active.** A verified active trial can be a zero-cost candidate source under FREE-FIRST.
- **Do not read current realtime odds in this project now.** The current calendar is inside the protected 2025–2026 final independent holdout. A current JVRTOpen/O5/O6 probe would touch protected market data and is therefore forbidden even if the trial is free and the API use is otherwise permitted.
- **Do not use an unbounded historical acquisition call** if it can return any 2025–2026 records. Filtering protected rows after acquisition is not acceptable because the holdout would already have been read.
- A real Phase 11 / exotic-EV data read may proceed only if one of the following is independently established:
  1. a JV-Link request can be proven to have a hard provider-side end boundary no later than 2024-12-31 before any record is delivered; or
  2. an already-existing, independently acquired pre-2025 local archive has immutable provenance showing that it never contained post-2024 records.
- Trial expiry must fail closed. No workflow may initiate paid registration, paid renewal, or a paid Data Lab subscription automatically.

This changes the JRA-VAN route from **EXCLUDE AS PAID** to **CONDITIONAL FREE-TRIAL CANDIDATE, DATA READ STILL BLOCKED BY HOLDOUT BOUNDARY**.

## Immediate engineering consequence

The repository may implement metadata-only trial/provenance checks and synthetic O5/O6 parsing/EV contracts without touching real racing data. It must not trigger a current JVRTOpen odds read, and must not run a historical request whose server-side end boundary is unknown.

The dedicated synthetic execution-gate regression is now registered at
`tests/test_exotic_prebet_execution_triage.py`. It locks quote freshness,
purchase-cutoff ordering, source identity, rights gates, forbidden result fields,
and the rule that structurally valid self-attested evidence can never
automatically authorize acquisition, EV, or staking.


## Cycle 51 update: historical O5/O6 are not prebet execution evidence

Official JVData specification reviewed on 2026-10-10:

- JVData setup/RACE record O5 is **final trio odds (確定オッズ)** and O6 is
  **final trifecta odds (確定オッズ)**:
  https://jra-van.jp/dlb/sdv/sdk/JV-Data4901.pdf
- Realtime exotic odds are separate dataspecs:
  - `0B35`: trio速報 odds
  - `0B36`: trifecta速報 odds
  They are updated after betting opens and are provided for one week.
- The official multi-time historical "time-series odds" dataspecs are
  `0B41` for O1 (win/place/bracket) and `0B42` for O2 (quinella). The
  specification does not list trio/trifecta as historical multi-time series.
- JRA-VAN staff also confirmed that realtime速報 data are obtained with
  JVRTOpen and are unavailable after the one-week provision period:
  https://developer.jra-van.jp/t/topic/979

Decision:

1. **O5/O6 from bounded historical RACE/setup acquisition are forbidden as
   strict prebet EV inputs.** They may describe the final market only.
2. The bounded pre-2025 JV-Link path remains useful for independently rebuilding
   Phase 11 RA/SE development history without touching 2025-2026.
3. Genuine trio/trifecta prebet EV requires locally captured `0B35/0B36`
   snapshots with immutable observed/captured timestamps and verified purchase
   cutoff while the market is live.
4. Current 2025-2026 realtime collection remains prohibited because those years
   are the protected final independent holdout.
5. No historical final odds, final payouts, or post-race information may be
   relabeled as purchase-time evidence.

The repository now enforces this distinction in
`src/horse_racing_predictions/exotic_jvlink_odds_policy.py` and its regression
tests. Classification of a realtime datasource still **never authorizes EV or
staking** by itself.

## Provider-bounded Phase 11 history route

JVOpen accepts a bounded FromTime-ToTime range. The official validation tooling
describes separate FromTime and ToTime parameters, and the JRA-VAN developer
community contains working bounded setup examples. A documented JV-Link setup
quirk means ordinary `YYYY1231235959` can omit late-year files whose provider
timestamps use pseudo-hours/minutes. A reported working 2024 setup end is
`20249999999999`.

For Phase 11 the repository therefore accepts exactly the safe provider-year
sentinel `20249999999999` while rejecting every 2025+ bound. This is defense
in depth: no unbounded/current fallback is available in the Phase 11 acquisition
module. See:

- `src/horse_racing_predictions/phase11_jravan_bounded.py`
- `scripts/phase11_jravan_bounded_export.py`
- `.github/workflows/phase11-bounded-jravan-self-hosted.yml`

The workflow is manual-only and defaults to plan-only. An actual provider read
requires explicit execute, zero-cost-entitlement, and personal-research-rights
confirmations; raw JV-Data is never uploaded as a GitHub artifact.
