"""Strict Friday-before-Sunday-draw research feature gate.

Reuses a single conservative source-time policy, not two drifting lists.
No official roster/rights evidence or note publication is implied.
"""
from __future__ import annotations

from .odds_free_training import OddsFreeResearchSample
from .odds_free_chronological_eval import _validate_research_features
from .friday_feature_projection import (
    _FRIDAY_CURRENT, _FRIDAY_PRIOR_HISTORY, _FORBIDDEN_NAME,
    project_friday_research_features,
)


def assert_friday_predraw_feature_list(features: tuple[str, ...]) -> None:
    _validate_research_features(features)
    if any(
        _FORBIDDEN_NAME.search(name)
        or not (name in _FRIDAY_CURRENT
                or name.startswith(_FRIDAY_PRIOR_HISTORY))
        for name in features
    ):
        raise ValueError(
            "Friday model uses draw/day-of-race or unverified source-time information"
        )


def select_friday_predraw_research_features(
    sample: OddsFreeResearchSample,
) -> OddsFreeResearchSample:
    """Project genuinely prior-race/static features before CatBoost fitting."""
    projected, _receipt = project_friday_research_features(sample)
    assert_friday_predraw_feature_list(projected.features)
    return projected
