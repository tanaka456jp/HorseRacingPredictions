from dataclasses import dataclass

CURRENT_RACE_OUTCOME_COLUMNS = {
    "finish_position",
    "finish_time",
    "margin",
    "last_3f",
    "corner_position_1",
    "corner_position_2",
    "corner_position_3",
    "corner_position_4",
    "prize_money",
    "payout",
}

MARKET_COLUMNS_REQUIRING_ASOF = {
    "win_odds",
    "win_popularity",
    "place_odds",
}

SAFE_HISTORY_PREFIXES = ("past_", "lag_", "rolling_", "career_")

@dataclass(frozen=True)
class LeakageAuditResult:
    safe: bool
    forbidden: tuple[str, ...]
    asof_required: tuple[str, ...]

def audit_model_features(feature_columns: list[str]) -> LeakageAuditResult:
    forbidden = []
    asof_required = []

    for column in feature_columns:
        lowered = column.lower()
        if lowered.startswith(SAFE_HISTORY_PREFIXES):
            continue
        if lowered in CURRENT_RACE_OUTCOME_COLUMNS:
            forbidden.append(column)
        elif lowered in MARKET_COLUMNS_REQUIRING_ASOF:
            asof_required.append(column)

    return LeakageAuditResult(
        safe=not forbidden and not asof_required,
        forbidden=tuple(sorted(forbidden)),
        asof_required=tuple(sorted(asof_required)),
    )

def assert_leakage_safe(feature_columns: list[str]) -> None:
    result = audit_model_features(feature_columns)
    if result.forbidden:
        raise ValueError(f"post-race leakage features: {list(result.forbidden)}")
    if result.asof_required:
        raise ValueError(
            "market features require an explicit pre-race as-of snapshot: "
            f"{list(result.asof_required)}"
        )
