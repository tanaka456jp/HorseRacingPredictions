# Paper Trading Session

The Paper Trading session connects four steps without enabling live execution:

1. freeze a timestamped pre-race odds snapshot,
2. record the model prediction linked to that exact snapshot,
3. evaluate the EV/risk rule,
4. record a PaperBroker bet only when the decision is selected.

## Selection-bias protection

Every evaluated prediction is stored, including no-bet decisions.

Only positive-stake PaperBroker orders appear in the bets table. Each recorded
paper bet is linked back to the prediction ID whose immutable pre-race evidence
was already stored.

This allows later analysis of:

- selected bets,
- rejected/no-bet candidates,
- exact quote used,
- model version,
- decision time,
- paper order reference.

LiveBroker remains disabled.
