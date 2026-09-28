from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.residual_v12_shadow import (
    build_residual_v12_shadow_predictions,
    capture_shadow_results_0b12,
    evaluate_shadow_results,
    summarize_shadow_predictions,
)


def _row(
    race_id,
    race_date,
    post,
    *,
    winner,
    odds,
):
    return {
        "race_id": race_id,
        "race_date": race_date,
        "horse_name": f"H{post}",
        "jockey": f"J{post}",
        "trainer": f"T{post}",
        "finish_position": 1 if post == winner else post + 1,
        "win_odds": odds,
        "distance_m": 1600,
        "post_position": post,
        "age": 3,
        "carried_weight": 54 + post,
        "horse_weight": 450 + post * 10,
        "horse_weight_delta": 0,
        "racecourse": "Kyoto",
        "surface": "Turf",
        "weather": "Fine",
        "track_condition": "Good",
        "sex": "M",
        "race_class": "OPEN",
        "graded_race": "NONE",
    }


def _history():
    rows = []
    dates = [
        "2017-01-05",
        "2018-01-05",
        "2019-01-05",
        "2020-01-05",
        "2021-01-05",
        "2022-01-05",
        "2023-01-05",
        "2024-01-05",
        "2026-09-22",
    ]
    for idx, date in enumerate(dates, start=1):
        winner = 1 if idx % 2 else 2
        odds = (
            [1.8, 4.0, 8.0]
            if winner == 1
            else [4.0, 1.8, 8.0]
        )
        for post in (1, 2, 3):
            rows.append(
                _row(
                    f"R{idx:02d}",
                    date,
                    post,
                    winner=winner,
                    odds=odds[post - 1],
                )
            )
    return pd.DataFrame(rows)


def _entries():
    rows = []
    for post in (1, 2, 3):
        row = _row(
            "20260927-08-03-04-11",
            "2026-09-27",
            post,
            winner=1,
            odds=3.0 + post,
        )
        row.pop("finish_position")
        row.pop("win_odds")
        rows.append(row)
    return pd.DataFrame(rows)


def _odds():
    race_id = "20260927-08-03-04-11"
    return pd.DataFrame([
        {
            "race_id": race_id,
            "horse_id": f"{race_id}-1",
            "decimal_odds": 2.0,
            "observed_at": "2026-09-27T04:00:00+09:00",
            "scheduled_post_time": "2026-09-27T15:00:00+09:00",
            "source": "JRA-VAN 0B31",
            "source_reference": "quote-1",
        },
        {
            "race_id": race_id,
            "horse_id": f"{race_id}-2",
            "decimal_odds": 4.0,
            "observed_at": "2026-09-27T04:00:00+09:00",
            "scheduled_post_time": "2026-09-27T15:00:00+09:00",
            "source": "JRA-VAN 0B31",
            "source_reference": "quote-1",
        },
        {
            "race_id": race_id,
            "horse_id": f"{race_id}-3",
            "decimal_odds": 8.0,
            "observed_at": "2026-09-27T04:00:00+09:00",
            "scheduled_post_time": "2026-09-27T15:00:00+09:00",
            "source": "JRA-VAN 0B31",
            "source_reference": "quote-1",
        },
    ])


def _champion():
    return SimpleNamespace(
        manifest=SimpleNamespace(
            train_start="2017-01-01",
            train_end="2021-07-31",
        )
    )


def test_shadow_predictions_use_fixed_gamma_and_normalize():
    pytest.importorskip("catboost")

    predictions = build_residual_v12_shadow_predictions(
        _history(),
        _entries(),
        _odds(),
        _champion(),
        iterations=5,
    )

    assert len(predictions) == 3
    assert set(predictions["fixed_gamma"]) == {4.0}
    assert set(predictions["model_version"]) == {
        "shadow-market-residual-v12"
    }
    assert abs(
        predictions["market_probability"].sum() - 1.0
    ) < 1e-12
    assert abs(
        predictions["residual_v12_probability"].sum() - 1.0
    ) < 1e-12

    summary = summarize_shadow_predictions(predictions)
    assert summary["rows"] == 3
    assert summary["races"] == 1
    assert summary["min_lead_minutes"] > 0


def test_shadow_predictions_reject_gamma_changes():
    pytest.importorskip("catboost")

    with pytest.raises(
        ValueError,
        match="frozen gamma=4.0",
    ):
        build_residual_v12_shadow_predictions(
            _history(),
            _entries(),
            _odds(),
            _champion(),
            iterations=5,
            fixed_gamma=2.0,
        )


def test_shadow_result_evaluation_waits_for_complete_race():
    pytest.importorskip("catboost")
    predictions = build_residual_v12_shadow_predictions(
        _history(),
        _entries(),
        _odds(),
        _champion(),
        iterations=5,
    )
    race_id = predictions.iloc[0]["race_id"]

    incomplete = pd.DataFrame([
        {
            "race_id": race_id,
            "post_position": 1,
            "finish_position": 1,
        },
        {
            "race_id": race_id,
            "post_position": 2,
            "finish_position": 2,
        },
    ])
    pending = evaluate_shadow_results(
        predictions,
        incomplete,
    )
    assert pending["status"] == "pending_complete_results"

    complete = pd.DataFrame([
        {
            "race_id": race_id,
            "post_position": 1,
            "finish_position": 1,
        },
        {
            "race_id": race_id,
            "post_position": 2,
            "finish_position": 2,
        },
        {
            "race_id": race_id,
            "post_position": 3,
            "finish_position": 3,
        },
    ])
    evaluated = evaluate_shadow_results(
        predictions,
        complete,
    )
    assert evaluated["status"] == "evaluated"
    assert evaluated["evaluated_races"] == 1
    assert "market_quality" in evaluated
    assert "residual_quality" in evaluated



class _WaitTrackingClient:
    calls = []

    def __init__(self):
        self.initialized = False
        self.opened = False

    def initialize(self):
        self.initialized = True

    def open_realtime(self, *, dataspec, key):
        self.opened = True
        return 0

    def iter_records(self, **kwargs):
        type(self).calls.append(dict(kwargs))
        return iter(())

    def close(self):
        self.opened = False


def test_shadow_result_lookup_uses_bounded_wait():
    _WaitTrackingClient.calls.clear()
    predictions = pd.DataFrame([
        {
            "race_id": "20260927-08-03-04-11",
        }
    ])

    results, errors = capture_shadow_results_0b12(
        predictions,
        client_factory=_WaitTrackingClient,
    )

    assert results.empty
    assert errors == 0
    assert _WaitTrackingClient.calls == [
        {
            "wait_retries": 25,
            "wait_seconds": 0.2,
        }
    ]


def test_market_context_handles_existing_decimal_odds_column():
    from horse_racing_predictions.market_aware_ranker_v11 import (
        add_market_context_features,
    )

    frame = pd.DataFrame([
        {
            "race_id": "R1",
            "win_odds": 2.0,
            "decimal_odds": 2.0,
        },
        {
            "race_id": "R1",
            "win_odds": 4.0,
            "decimal_odds": 4.0,
        },
        {
            "race_id": "R1",
            "win_odds": 8.0,
            "decimal_odds": 8.0,
        },
    ])

    out = add_market_context_features(frame)

    assert "market_implied_probability" in out.columns
    assert abs(
        out["market_implied_probability"].sum() - 1.0
    ) < 1e-12
    assert list(out["decimal_odds"]) == [2.0, 4.0, 8.0]
