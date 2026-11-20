"""Conservative odds-free feature policy for Friday BEFORE race-day data.

A successful projection is a research option, NOT proof that actual Friday
race-entry assignments or model feature availability were independently
verified. Publishing stays blocked until source and schedule attestations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

from .odds_free_training import OddsFreeResearchSample
from .odds_free_chronological_eval import _validate_research_features

# Valid before Friday post publication only with independent, timely entry
# evidence: do not assume announced Friday weather, horse weights, field size,
# barrier number, relative post, or observed track conditions in advance.
_FRIDAY_CURRENT = frozenset({
    "distance_m", "age", "racecourse", "surface", "sex",
    "race_class", "graded_race",
})
_FRIDAY_PRIOR_HISTORY = (
    "horse_past_", "horse_recent_", "horse_days_since_",
    "jockey_past_", "jockey_days_since_",
    "trainer_past_", "trainer_days_since_",
    "horse_surface_past_", "horse_surface_days_since_",
    "horse_course_past_", "horse_course_days_since_",
    "horse_distance_past_", "horse_distance_days_since_",
    "jockey_course_past_", "jockey_course_days_since_",
    "trainer_course_past_", "trainer_course_days_since_",
)
# In addition to ordinary market/label bans, guard against poisoned
# synthetic feature names trying to smuggle post-event observations.
_FORBIDDEN_NAME = re.compile(
    r"future|post[_-]?race|same[_-]?day|today|forecast_actual|"
    r"weather|track_condition|horse_weight|horseweight|"
    r"finish_position|finish_time|payout|odds|popularity|"
    r"corner_[1-4](?!_past)|馬体重|馬場状態|天候|オッズ|払戻",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class FridayFeatureReceipt:
    research_only: bool
    original_feature_count: int
    friday_feature_count: int
    excluded_features: tuple[str, ...]
    friday_roster_independently_verified: bool = False
    live_current_week_source_rights_verified: bool = False
    target_race_final_results_used: bool = False
    publication_authorized: bool = False
    positive_expected_value_demonstrated: bool = False


def project_friday_research_features(
    sample: OddsFreeResearchSample,
) -> tuple[OddsFreeResearchSample, FridayFeatureReceipt]:
    """Select exclusively conservative pre-race features for Friday models.

    Caller still has to freeze and verify the actual input values available
    at the intended Friday publication timestamp. No auto-post permission.
    """
    if not isinstance(sample, OddsFreeResearchSample):
        raise ValueError("STRICT_NONMARKET_RESEARCH_SAMPLE_REQUIRED")
    _validate_research_features(sample.features)
    if sample.frame.columns.duplicated().any():
        raise ValueError("DUPLICATE_RAW_RESEARCH_COLUMNS")
    try:
        cutoff = date.fromisoformat(sample.cutoff)
    except (TypeError, ValueError) as exc:
        raise ValueError("STRICT_PRE2025_SAMPLE_REQUIRED") from exc
    if cutoff.isoformat() != sample.cutoff or cutoff >= date(2025, 1, 1):
        raise ValueError("PROTECTED_FINAL_HOLDOUT_FORBIDDEN")
    selected: list[str] = []
    excluded: list[str] = []
    for name in sample.features:
        approved = (
            not _FORBIDDEN_NAME.search(name)
            and (name in _FRIDAY_CURRENT
                 or name.startswith(_FRIDAY_PRIOR_HISTORY))
        )
        if approved:
            selected.append(name)
        else:
            excluded.append(name)
    if not selected:
        raise ValueError("FRIDAY_PROJECTION_NO_SAFE_FEATURES")
    # Keep targets and historical raw columns solely for strict fit/validate.
    # CatBoost receives *only* projected feature_columns. Source inputs
    # (including historic outcomes) are never part of the feature allowlist.
    projected = OddsFreeResearchSample(
        frame=sample.frame.copy(deep=True),
        features=tuple(selected),
        race_count=sample.race_count,
        runner_count=sample.runner_count,
        cutoff=sample.cutoff,
        market_columns_excluded=sample.market_columns_excluded,
    )
    return projected, FridayFeatureReceipt(
        research_only=True,
        original_feature_count=len(sample.features),
        friday_feature_count=len(selected),
        excluded_features=tuple(excluded),
    )
