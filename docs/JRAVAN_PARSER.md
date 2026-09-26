# JRA-VAN RA/SE parser

The parser is based on the official JV-Data specification Ver.4.9.0.1.

It does not guess field offsets.

Key record sizes:

- RA (race detail): 1272 bytes including CR/LF
- SE (horse race detail): 555 bytes including CR/LF

Important official byte positions used:

RA:
- race key: year 12, month/day 16, course 20, meet 22, day 24, race 26
- grade code: 615
- race-condition codes: 623-637
- distance: 698
- track code: 706
- weather: 888
- turf condition: 889
- dirt condition: 890

SE:
- horse number: 29
- blood registration number: 31
- horse name: 41
- sex: 79
- age: 83
- trainer abbreviation: 91
- carried weight: 289
- jockey abbreviation: 307
- horse weight: 325
- weight-change sign/value: 328/329
- final finish position: 335
- corner positions: 352/354/356/358
- win odds: 360
- popularity: 364
- last 3F: 391

The parser operates on CP932 bytes even though the raw acquisition JSONL stores
decoded text. Each record is round-tripped back to CP932 before byte slicing.

## Conversion

After a free-trial raw export:

    python scripts/jravan_parse_history.py --input data/jravan/race_raw.jsonl

Outputs:

- data/jravan/current_history_supplement.csv
- artifacts/jravan_parse_report.json

By default:

- only JRA central course codes 01-10 are retained
- incomplete/non-starter rows without final finish and valid win odds are excluded
- multiple update stages are collapsed to the most final data division

The generated CSV uses the same canonical columns expected by Current History
Intake.

Next:

    python scripts/prepare_current_history.py --base data/raw/19860105-20210731_race_result.csv --supplement data/jravan/current_history_supplement.csv --source-name "JRA-VAN Data Lab free trial" --source-kind licensed_provider --source-reference "JV-Link local export" --rights-note "Acquired locally through the official JRA-VAN Data Lab free trial; raw redistribution disabled." --approved-for-modeling --allow-gap

The --allow-gap flag is required when extending the 2021 base because the gap
is intentionally large. The intake report preserves that warning instead of
silently hiding it.

Raw JV-Data and raw JSONL must remain local and must not be committed or
redistributed.
