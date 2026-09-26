# Input templates

Three empty CSV templates are included under `templates/`.

## current_history_template.csv

Use for approved/user-supplied completed race history that extends the canonical
history beyond 2021-07-31.

Key requirements:

- one row per starter/result
- `race_id` and `horse_name` must be unique within the file
- `finish_position` must be positive
- exactly one winner per race
- `win_odds` must be greater than 1.0
- dates must begin after the base history
- source provenance is supplied separately through the Current History Intake CLI

## future_entries_template.csv

Use for a not-yet-run race.

Do not enter target-race result fields such as:

- finish_position
- last_3f
- corner passing positions
- target-race win odds

Current odds are deliberately kept out of the probability model and joined
after inference.

## odds_snapshots_template.csv

Use for timestamped pre-race market quotes.

Required timestamps must include a timezone offset, for example:

    2026-09-26T14:20:00+09:00

Each quote must be observed before `scheduled_post_time`.

## Recommended flow

1. Fill `current_history_template.csv` from an approved/user-supplied source.
2. Run `scripts/prepare_current_history.py`.
3. Fill `future_entries_template.csv`.
4. Fill `odds_snapshots_template.csv` with pre-race quotes.
5. Run `scripts/run_forward_paper.py`.

A stale history gap greater than 14 days is blocked by default.
