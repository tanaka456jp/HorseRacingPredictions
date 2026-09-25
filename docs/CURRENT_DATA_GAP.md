# Current Data Gap

Last reviewed: 2026-09-26.

## Status

The approved free historical research source currently ends on 2021-07-31.

There is therefore an unresolved current-data gap from 2021-08 onward.

## Sources not approved as canonical inputs

Recent public GitHub projects were found that collect 2024-2026 JRA/netkeiba
race data. Most do so by scraping public web pages.

These projects may be useful as implementation references, but their existence
does not establish that the underlying race data can be automatically acquired,
redistributed or used as this public repository's canonical data source.

Accordingly they are **not approved** for automatic ingestion.

## Formal current-data path

JRA-VAN Data Lab / JV-Link is the formal provider path identified for:

- historical race data
- race-day data
- real-time/速報 odds
- time-series odds

It is paid and therefore remains disabled under FREE-FIRST.

As reviewed on 2026-09-26, JRA-VAN also provides a 64-bit JV-Link SDK and a
Python development guide. This makes it a technically viable future provider
if the paid-data gate is eventually passed.

## Current operating policy

Until an approved free current-data source is identified:

1. historical model research may use the approved external Kaggle input,
2. forward Paper Trading may ingest user-supplied/manual timestamped CSV
   snapshots,
3. no netkeiba/JRA public-page scraper is shipped,
4. no JRA-VAN subscription is purchased,
5. production-profit claims remain prohibited.

## Paid-data gate

JRA-VAN implementation can be reconsidered only after the free research and
forward Paper Trading system demonstrates enough value to justify the cost.
The paid source must then prove incremental predictive/economic value in a
separate comparison.
