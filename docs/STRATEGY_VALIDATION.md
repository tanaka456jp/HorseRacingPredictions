# Forward Strategy Validation

## Purpose

Do not choose an EV threshold by looking at the same OOS folds used to report
the result.

HorseRacingPredictions treats **no bet** as a valid strategy outcome.

## Forward rule selection

For target fold N:

1. use only earlier OOS folds 1..N-1,
2. evaluate a small predeclared set of EV thresholds,
3. require a minimum number of prior bets,
4. select a threshold only if prior flat-bet ROI is positive,
5. otherwise abstain for fold N,
6. apply the chosen rule to fold N without using fold N outcomes,
7. move forward and repeat.

This remains historical research because final historical odds are used.
It is nevertheless stricter than choosing a threshold from the complete OOS
sample and then reporting that same sample.

## Production gate

A strategy cannot be labeled profitable until it also passes forward paper
trading with timestamped pre-race odds and then small-capital live validation.

Post-hoc segment discovery, historical final odds and estimated odds are never
sufficient by themselves.
