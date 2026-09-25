# Paper Trading Evidence Boundary

## Goal

A paper-trading result is useful only when the system can prove what was known
before the race started.

The project therefore stores the exact odds observation linked to every paper
prediction.

## Required timestamps

Every odds snapshot has:

- observed_at
- scheduled_post_time
- source
- source_reference

Every linked prediction has:

- predicted_at
- model_version
- exact decimal odds used by that prediction

All timestamps must be timezone-aware.

## Hard validation rules

The system rejects a paper prediction when:

- the odds were observed at or after scheduled post time,
- prediction time is earlier than odds observation time,
- prediction time is at or after scheduled post time,
- race or horse identifiers differ,
- prediction odds do not exactly match the linked snapshot.

## Immutability

For the same race, horse, observation timestamp and source, a previously stored
snapshot cannot later be replaced with different odds or metadata.

Repeated storage of the identical snapshot is idempotent.

## Interpretation

This creates the evidence boundary needed for future forward paper trading.
It does not make historical final-odds backtests equivalent to live evidence,
and it does not enable real-money execution.
