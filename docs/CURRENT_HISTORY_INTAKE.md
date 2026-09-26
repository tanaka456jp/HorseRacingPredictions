# Current History Intake

## Why this exists

The approved free historical research source ends on 2021-07-31.

As of 2026-09-26, JRA publishes current race results on its official website,
but this project does not ship an automated JRA/netkeiba page scraper. No
official free CSV/API suitable as the project's canonical current feed has been
approved.

JRA-VAN Data Lab is the formal historical/real-time data route, but it is paid
and remains disabled under FREE-FIRST.

Therefore recent history is accepted only through an explicit supplemental
input with provenance metadata.

## Fail-closed checks

Before a supplemental CSV can be merged into the current history, the intake
layer verifies:

- source is explicitly approved for modeling
- supplemental dates begin after the base history
- gaps over 14 days are blocked unless explicitly acknowledged
- no duplicate race/horse keys
- no overlap with the base history
- every result row has a valid positive finish position
- every row has valid win odds greater than 1.0
- one race ID maps to one race date
- every race contains exactly one winner

If any required check fails, the report and source manifest are still written,
but the merged history CSV is not created.

## Provenance

The merged output records source metadata on supplemental rows:

- _source_name
- _source_kind
- _source_reference
- _source_acquired_at

Raw supplemental data remains outside Git by default because data/ is ignored.

## Example

    python scripts/prepare_current_history.py       --base data/raw/19860105-20210731_race_result.csv       --supplement data/manual/recent_history.csv       --source-name "User supplied current history"       --source-kind user_supplied       --source-reference "local export 2026-09-26"       --rights-note "User confirms lawful use for private research."       --approved-for-modeling

Successful output:

- data/curated/current_history.csv
- artifacts/current_history_manifest.json
- artifacts/current_history_report.json

A large time gap should not be silently overridden. Use --allow-gap only when
the missing period is understood and intentionally accepted; stale/incomplete
history can materially distort recent-form features.
