"""Friday before-draw training feature gate for Sunday JRA forecasts.

JRA's ordinary Sunday horse numbers are assigned Saturday morning, after
Friday publication. Such fields must not be guessed, forward-filled from
results, or treated as known Friday. All research stays offline and private.
"""
from __future__ import annotations

from dataclasses import replace

from .odds_free_training import OddsFreeResearchSample
from .odds_free_chronological_eval import _validate_research_features

# Undecided at ordinary Friday issue time, including course condition and
# race-day horse weights. Retain only actual known entrants and prior-race
# form. Changing this list requires new rigorous source-time audit.
_FRIDAY_UNAVAILABLE_CURRENT_FEATURES = frozenset({
    "post_position", "relative_post_position",
    "horse_weight", "horse_weight_delta", "horse_weight_vs_race_mean",
    "weather", "track_condition",
})


def assert_friday_predraw_feature_list(features: tuple[str, ...]) -> None:
    _validate_research_features(features)
    forbidden = _FRIDAY_UNAVAILABLE_CURRENT_FEATURES & set(features)
    if forbidden:
        raise ValueError("Friday model uses draw/day-of-race information")


def select_friday_predraw_research_features(
    sample: OddsFreeResearchSample,
) -> OddsFreeResearchSample:
    """Remove Friday-unknown current features before any model fitting."""
    if not isinstance(sample, OddsFreeResearchSample):
        raise ValueError("approved odds-free research sample required")
    filtered = tuple(
        f for f in sample.features
        if f not in _FRIDAY_UNAVAILABLE_CURRENT_FEATURES
    )
    assert_friday_predraw_feature_list(filtered)
    return replace(sample, features=filtered)
