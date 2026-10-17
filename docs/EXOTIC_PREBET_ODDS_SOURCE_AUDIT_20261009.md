# Prospective exotic-odds evidence audit (2026-10-09)

Status: **NO SOURCE APPROVED**. This is a research specification, not permission to scrape, an odds feed, a positive-EV finding, or an authorization to place wagers.

## Current evidence

| Candidate | Observed fact | Unresolved condition | Decision |
| --- | --- | --- | --- |
| JRA official public site | Official site links to odds; JRA overseas race guidance explicitly lists trio (3連複) and trifecta (3連単). | No verified automated collection/reuse permission, per-combination pre-decision timestamp, update frequency, reproducible archive, or immutable historical snapshots. | BLOCKED for automated acquisition |
| Existing manual snapshot CSV | Repository supports manually provided, timezone-aware win-odds snapshots. | No verified 3-combination schema, lawful provenance, or source-side observation time for exotic odds. | Design only |
| JRA-VAN / JV-Link free trial | Existing repository documents a trial-based win-odds input (0B31). | Exotic combination coverage, source rights, trial expiry and snapshot frequency not confirmed. No paid conversion allowed. | DO NOT ENABLE |
| Historical result/payout pages | Race outcomes and final returns may be visible after the event. | Not evidence of a price available at decision time. | PROHIBITED as pre-race odds |

Primary official references:
- https://www.jra.go.jp/ (odds navigation)
- https://www.jra.go.jp/keiba/overseas/rule/ (trio and trifecta wager types)
- https://www.jra.go.jp/news/202503/033103.html (official announcement of odds publication)
- Existing local policy: docs/LIVE_ODDS_PROVIDERS.md and docs/CURRENT_DATA_GAP.md

## Evidence contract for a future lawful source

A quote must identify race_id, bet_type (trio unordered / trifecta ordered), three distinct horse numbers, quoted decimal odds, source name/reference, source-observed timestamp, locally captured timestamp, decision timestamp, and scheduled start, all with explicit timezones. Require observed <= captured <= decision < scheduled start. The start can change: later verification is required.

Prohibit final payouts, result fields, post-race final odds, unverifiable backfilled observations, and any use of the 2025-2026 final holdout. Store immutable acquisition evidence and document terms, permissions, combination mapping, refresh cadence, retention rules, and clock synchronization **before** connecting any data.

The pure function in src/horse_racing_predictions/exotic_prebet_odds_contract.py checks only structural assertions and always returns approved_for_ev=false and approved_for_acquisition=false. A passed structural check must not be interpreted as proof of a lawful or actually purchasable quote.

## Strict OOS research protocol (not activated)

First acquire an independently approved pre-2025 development source and legally obtained prospective quote history. Freeze feature definitions, time cutoff, selection policy and calibration using only permissible earlier development windows. Evaluate untouched later prospective paper observations only after freezing. Pair a pre-decision combination probability with an actual pre-decision executable quote, then assess EV=p*decimal_odds and realized returns with uncertainty and execution friction. Never use final payout as pre-decision odds. Do not tune on the 2023/2024 annual results or access the 2025-2026 final independent holdout.

No changes to Forward Paper settings or live purchase systems are authorized by this audit.
