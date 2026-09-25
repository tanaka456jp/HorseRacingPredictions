# Free Data Sources

## Historical prototype source

### JRA日本中央競馬会 Horse Racing Dataset — Kaggle

- URL: https://www.kaggle.com/datasets/takamotoki/jra-horse-racing-dataset
- Coverage stated by the dataset: 1986-01-05 through 2021-07-31
- Includes: race results, win odds, lap times and corner passing orders
- Kaggle license metadata: CC BY 4.0
- Provenance stated by dataset author: scraped from netkeiba

## Repository policy

The raw Kaggle files are **not committed or redistributed** in this public repository.

Reasons:

1. The dataset page carries CC BY 4.0 metadata.
2. The dataset author also states that the source was netkeiba.
3. netkeiba's own guidance limits reuse of its data outside private use.
4. Therefore the repository treats this source only as an externally acquired historical research input until provenance/reuse questions are satisfactorily resolved.

The project stores only:

- adapters
- schemas
- tests
- source metadata
- derived model code

Raw race data must live outside Git.

## Live / current data

No automated scraper of netkeiba is part of the project.

A future live provider must satisfy all of the following:

- lawful/authorized acquisition
- documented terms
- stable pre-race timestamps
- reproducible snapshot semantics
- no paid fee until the project's paid-data gate is passed

## Modeling rule

Historical race-result fields such as finish position, current-race last-3F, corner positions and payout are never model inputs for that race.

Market odds may be used as a benchmark or for EV settlement. If used as a model feature, they require a timestamped pre-race as-of snapshot.
