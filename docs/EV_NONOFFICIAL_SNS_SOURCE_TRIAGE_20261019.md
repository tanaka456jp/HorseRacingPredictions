# Non-official/SNS signal feasibility — executable-EV-first research

Status: **source discovery and rights review ONLY**; 2026-10-19 JST.
Linked to `docs/EV_VIABILITY_GO_NO_GO_20261019.md`.
**No feed has been authorized for automated acquisition, bulk retention,
training or wagering. No posts were collected during this review.**

## Economic hypothesis and the reason to test it

A public pre-race observation could add information not already incorporated
in the corresponding **purchase-available** pari-mutuel odds. For example:

- Timely independent information about going/rain, transport, last-minute
  condition, paddock movement, scratches, equipment, or a jockey/trainer
  comment.
- The opposite signal: social popularity/crowding may move odds enough
  to **erase** any advantage. An apparently correct prediction may still
  yield negative net EV if public odds already reflect the news.
- Unofficial statements are **unverified assertions**, not validated horse
  facts. Rumours, copied posts, duplicate source amplification, edited
  posts, misleading tipsters and outcome-selected anecdotes are hazards.

**Research null:** adding a legally sourced pre-decision signal does not
increase *cost-adjusted executable* performance over an otherwise frozen
market+base-model comparator on identical eligible race opportunities.
Prediction accuracy alone is not the primary endpoint.

## Candidate source triage (not approval for downloading)

| Candidate | What is technically/publicly available | Key permission/evidence gap | Decision |
| --- | --- | --- | --- |
| Bluesky / atproto public feeds | Documented unauthenticated reads via public AppView plus official rate-limit rules. Potential source discovery for pre-race observations. | Confirm actual post/author content rights, legal automated collection, research/ML processing, duration of retention and deletion handling; accessibility is **not** a licence to copy/train. Check there are enough Japanese JRA pre-race posts and genuine observed-time snapshots. | **REVIEW RIGHTS FIRST**; no collection |
| X / social posts and trainer/journalist accounts | Potential near-real-time public observations and official account reposts. | Current API consumption costs/tiers and rights for continuous reads, machine processing and storage are not established as zero-cost. Browser visibility != authorized harvesting. | **BLOCKED** until confirmed free explicit rights |
| Reddit / racing communities | Potential discussion, but limited direct relevance to Japanese JRA before cutoff. | Reddit's May 2026 developer policy says Reddit For Researchers is its authorized research avenue, and model training requires explicit consent. General-purpose OAuth free API quota does **not** grant these research rights. | **NOT APPROVED** without separate authorization |
| Independent blogs, local eyewitness websites, public RSS | May provide paddock and track observations; site-specific permitted feeds may be easier to review. | Site-specific permission for automatic fetch, storage, analysis and machine-learning, publication/correction times and copyright. Need source-by-source review, not generic scraping. | **CANDIDATE** only when rights confirmed |
| Public nonofficial weather and transit reports | May supply condition changes independently of betting chatter. | Accessible public feeds != blanket permission for collection or feature retention; utility depends on location/event and actual cutoff time. | **CANDIDATE** subject to lawful free feed and prospective evidence |

Official policy references checked 2026-10-19:

- Bluesky public API and rate-limit documentation:
  https://docs.bsky.app/docs/api/app-bsky-feed-get-feed ,
  https://bsky.network/docs/rate-limits/ ,
  https://bsky.social/about/support/tos
- Reddit Developer Platform & Accessing Reddit Data (May 28, 2026):
  https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data
- Reddit Data API Terms (revised July 20, 2026):
  https://redditinc.com/policies/data-api-terms
- JRA's official SNS guideline warns that user-generated posts are not
  guaranteed accurate by JRA and directs readers to official race details:
  https://jra.jp/SNS/guide.html

This source review does **not** infer author permission or blanket model
training rights. Any new licence/cost review must inspect then-current terms
and platform-specific terms before a feed is enabled.

## Mandatory point-in-time ingestion proof (only after source rights approval)

For *each* legally permitted minimum-necessary observation, separately audit:

1. Source, lawful rights evidence/version, API/RSS endpoint permission,
   acquisition fee **JPY 0**, retrieval caps and retention/deletion policy.
2. Source claim `published_at`, our immutable `first_seen_at` timestamp,
   edit/deletion snapshots (as permitted), data arrival lag and capture hash.
   A claimed historical publish timestamp **never** substitutes for actual
   first observation; earliest availability is no earlier than first_seen.
3. Event and horse/race match confidence and whether the source is genuinely
   independent rather than reposting the same rumour; reject ambiguous IDs.
4. A frozen pre-race `decision_at` with `first_seen_at <= decision_at <
   purchase_cutoff_at < scheduled_post_at`; quote must independently prove
   purchase-channel access, rights and freshness. Do not backdate old posts,
   scrape retrospective webpages, or use settlement/result features.
5. Unknown/missing/late/stale/removed messages stay accounted for as
   **unavailable evidence**, not silently imputed into successful cases.
   Unverified false facts are not adopted as absolute events.
6. Do not upload raw post text, poster IDs, race-level provider data, private
   logs, personal data or credentials to GitHub/CI. Obey source-specific
   deletion requests and retention policies in the local approved store.

The protected **2025–2026 final holdout is NOT available for feature
selection or training**. An independently approved prospective cohort would
require a new precommitted and non-overlapping plan; this task does not
authorize reusing the existing final holdout as SNS data.

## Fixed economic comparison, with stop conditions

- Freeze hypotheses, sources, candidate features, baseline, comparator,
  sample criteria and correction for multiple candidate tests **before**
  looking at real outcomes. Never retune Phase 12/13 2023/24 one-shot
  protocols or existing Forward Paper thresholds.
- Evaluate **identical eligible races, before the same purchase deadline**:
  base+market *without SNS* vs base+market *with permitted SNS*. Log no-bet
  opportunities, nonfills, stale/missing posts, market movement, all costs,
  actual available prices and resulting net economic returns.
- Use independent days/races for clustered uncertainty and require positive
  **net** economic delta vs market plus positive absolute net return after
  realistic adverse price/fill stress. Avoid overclaiming a nominal 95%
  interval after multiple source/feature searches.
- Reject the SNS input if rights/cost/timeproof fail, coverage is too sparse,
  economic net benefit is absent, or any claimed improvement disappears
  when contemporaneous market odds and price deterioration are included.
- **Do not extend the one-week deadline merely because a new social feed
  exists.** An unapproved source is not evidence of a feasible strategy.

## Today's decision

`SOURCE_DISCOVERY_ONLY / MEASUREMENT_BLOCKED`.

A technically public SNS API is a possible future research lead, **not**
a fix for the existing RACE `JVOpen -301` gap or lack of lawful free,
timestamped pre-purchase market quotes. No extra historical 2025/26 data
may be opened to compensate for missing source provenance. Champion v7
historical research ROI of -1.90% is not an SNS effectiveness estimate.
At the existing one-week economic Go/No-Go deadline, a project without
verified no-cost rights and genuine forward executable-EV evidence remains
a **NO-GO recommendation candidate**; preserve artifacts for human review.

## Independent JMA XML weather-feed scope review (2026-10-19 JST)

**Source status: CONDITIONAL PUBLIC-WEATHER CANDIDATE, not an approved
racing/odds feed and not evidence of incremental betting EV.** This is
a read-only official-policy review; no Atom feed or racing data was collected.

- JMA expressly offers public PULL-type disaster-weather XML Atom feeds for
  automated processing, without registration. Its ordinary website content
  is subject to Public Data Terms v1.0 absent special rights notices;
  attribution and identification of processing are required. Check each
  product's specific notes and meteorological-law limits before any feature
  collection. Sources:
  https://xml.kishou.go.jp/xmlpull.html
  https://www.jma.go.jp/jma/kishou/info/coment.html
- The high-frequency feed is **updated each minute**, but only guarantees
  listing of at least the latest **10 minutes of incoming messages**.
  The long-term feed updates **hourly** and lists several days. Publication
  time, actual first-seen time and decision time must remain distinct.
  Outages/delays are expressly possible. JMA says it blocks IPs causing
  **10 GB or more downloads per day**; no repeated/bulk downloads.
- The published message list (as of 2026-08-06) contains prefectural
  weather forecasts, regional time-series forecasts, warnings, and heavy
  rain alerts, among other *disaster-weather bulletins*. It does **not**
  establish a live, racecourse-specific precipitation/going observation or
  direct race/horse ID linkage. No claim of such granularity is allowed.
  Source: https://xml.kishou.go.jp/xmllist.pdf
- Operational value remains speculative: regional weather alerts can be
  stale, geographically coarse, already reflected in market prices, or
  uninformative for actual track going. Any future prospective test must
  record source-product identity, rights/version, original bulletin time,
  immutable local first-seen time, affected area mapping, decision cutoff,
  missingness and market-matched economic delta. No retrospective first-seen
  reconstruction is permissible.
- **Economic priority unchanged:** the legal no-cost real race/outcome path
  and independently timestamped purchase-available odds remain blocked.
  A lawful weather feature alone cannot pass the five executable-EV gates.
  Do not activate collection, amend frozen OOS/Paper thresholds, access
  protected holdout or extend the one-week economic deadline.
