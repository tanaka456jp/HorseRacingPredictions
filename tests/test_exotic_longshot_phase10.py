from pathlib import Path

from horse_racing_predictions.exotic_longshot_phase10 import (
    ROLLING_RESIDUAL_OOF_YEARS,
    _period_passed,
)


def _passing_result() -> dict:
    return {
        "binary_log_loss_delta": -0.001,
        "brier_delta": -0.0001,
        "top1": {"hit_rate_delta": 0.01},
        "mrr": {"delta": 0.01},
        "paired_bootstrap_quality": {
            "binary_log_loss_improvement_support": 0.90,
            "brier_improvement_support": 0.85,
        },
        "paired_bootstrap_ranking": {
            "top1_hit_rate_improvement_support": 0.82,
            "mrr_improvement_support": 0.81,
        },
    }


def test_phase10_oof_years_add_2023_only_for_rolling_refit():
    assert ROLLING_RESIDUAL_OOF_YEARS == (
        2018,
        2019,
        2020,
        2021,
        2022,
        2023,
    )


def test_phase10_gate_requires_all_four_supported_improvements():
    result = _passing_result()
    assert _period_passed(result)

    result["paired_bootstrap_ranking"][
        "mrr_improvement_support"
    ] = 0.79
    assert not _period_passed(result)


def test_phase10_protocol_is_walk_forward_and_holdout_safe():
    source = Path(
        "src/horse_racing_predictions/exotic_longshot_phase10.py"
    ).read_text(encoding="utf-8")
    phase9 = Path(
        "src/horse_racing_predictions/exotic_longshot_phase9.py"
    ).read_text(encoding="utf-8")
    request = Path(
        "research/exotic_longshot_phase10_request.txt"
    ).read_text(encoding="utf-8")

    assert "oof_years=ROLLING_RESIDUAL_OOF_YEARS" in source
    assert "general baseline through 2023" in source
    assert "oof_years: tuple[int, ...] = RESIDUAL_OOF_YEARS" in phase9
    assert '"2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "2018-2023" in request
    assert "2025-2026" in request
