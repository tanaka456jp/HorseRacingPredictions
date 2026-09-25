# Live Odds Provider Policy

Last reviewed: 2026-09-26.

## FREE-FIRST state

The project does not currently activate a paid live-data provider.

Supported now:

- in-memory snapshots for tests
- user-supplied/manual CSV snapshots
- any future free provider that can prove lawful access and pre-race timestamps

Reserved but disabled:

- JRA-VAN Data Lab / JV-Link

JRA-VAN Data Lab is a formal source for historical and real-time racing data,
including race-day odds, but it is a paid service. The project keeps an adapter
boundary for it while the paid-data gate remains closed.

## Why manual CSV exists

The manual CSV provider allows forward paper-trading validation without
scraping an unclear public endpoint and without paying for data before the
model has demonstrated value.

Each row must include:

- race_id
- horse_id
- horse_name
- decimal_odds
- observed_at with timezone
- scheduled_post_time with timezone

Optional:

- source
- source_reference

The same timestamp checks and immutable evidence rules apply regardless of
provider.

## Paid-data gate

A paid provider may be implemented only after forward paper trading establishes
stable evidence that the system is worth advancing. After implementation, the
paid source itself must demonstrate reproducible incremental value exceeding
its full cost.
