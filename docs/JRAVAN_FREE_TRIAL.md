# JRA-VAN Data Lab free-trial path

Last reviewed: 2026-09-26.

## Why this path is now preferred

JRA-VAN states that Data Lab has a one-month free trial beginning on the day
JV-Link is installed. Paid registration is not required merely to use the trial
functionality.

This allows HorseRacingPredictions to test a formal JRA data route without
violating FREE-FIRST.

The project still does not purchase a subscription automatically.

## Architecture

Windows PC:

    JV-Link free trial
      -> JVDTLab.JVLink COM
      -> jravan_export_raw.py
      -> local data/jravan/race_raw.jsonl
      -> record-format normalization (next stage)
      -> Current History Intake
      -> Champion Forward Paper pipeline

GitHub-hosted Linux runners do not connect to JV-Link.

## Requirements on the Windows PC

1. Install the current JRA-VAN JV-Link.
2. Install the project's normal Python environment.
3. Install the Windows-only dependency:

       pip install -r requirements-jravan.txt

4. Open JV-Link settings once:

       python scripts/jravan_export_raw.py --open-settings

5. Run a small raw-record smoke:

       python scripts/jravan_export_raw.py --from-time 20210801000000 --option 4 --record-types RA,SE --max-records 1000

The exporter always calls JVOpen with dataspec RACE.
RA and SE are record IDs inside RACE; they are not valid JVOpen dataspec
values.

## Full acquisition

After the smoke confirms RA/SE records:

    python scripts/jravan_export_raw.py --from-time 20210801000000 --option 4

Raw output and downloaded JV-Data stay under ignored local data directories.
They must not be committed or redistributed.

The summary artifact records:

- JVOpen read/download counts
- last-file timestamp
- record-type counts
- SHA-256 of the local JSONL
- redistribution=false

## Important distinction

JVOpen from_time is a data provision timestamp, not the race date.
Therefore raw records must still be parsed and filtered by their actual race
date before they can extend the canonical history.

## Next implementation stage

Once a real free-trial raw sample has been captured, use the current SDK's
JV-Data Excel/PDF specification to implement and verify RA/SE fixed-width
parsing. Do not guess byte positions from old unofficial examples.
