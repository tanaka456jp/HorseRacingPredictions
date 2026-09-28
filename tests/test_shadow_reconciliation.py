import pandas as pd

from horse_racing_predictions.residual_shadow_ledger import (
    ResidualShadowLedger,
)
from horse_racing_predictions.shadow_reconciliation import (
    reconcile_pending_shadow_results,
)


def _predictions() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "race_id": "R1",
            "horse_id": "R1-1",
            "post_position": 1,
            "race_date": "2026-09-28",
            "observed_at": "2026-09-28T00:00:00+00:00",
            "scheduled_post_time": "2026-09-28T01:00:00+00:00",
            "decimal_odds": 2.0,
            "market_probability": 0.6,
            "residual_v12_probability": 0.65,
            "overlay_ratio": 0.0833333333333333,
            "fixed_gamma": 4.0,
        },
        {
            "race_id": "R1",
            "horse_id": "R1-2",
            "post_position": 2,
            "race_date": "2026-09-28",
            "observed_at": "2026-09-28T00:00:00+00:00",
            "scheduled_post_time": "2026-09-28T01:00:00+00:00",
            "decimal_odds": 4.0,
            "market_probability": 0.4,
            "residual_v12_probability": 0.35,
            "overlay_ratio": -0.125,
            "fixed_gamma": 4.0,
        },
    ])


def _results() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "race_id": "R1",
            "post_position": 1,
            "finish_position": 1,
        },
        {
            "race_id": "R1",
            "post_position": 2,
            "finish_position": 2,
        },
    ])


def test_reconcile_pending_shadow_results_updates_only_results(tmp_path):
    ledger = ResidualShadowLedger(tmp_path / "shadow.sqlite3")
    try:
        ledger.record_predictions(_predictions())
        calls = []

        def fake_fetcher(request):
            calls.append(request["race_id"].tolist())
            return _results(), 0

        result = reconcile_pending_shadow_results(
            ledger,
            result_fetcher=fake_fetcher,
        )

        assert calls == [["R1"]]
        assert result["status"] == "reconciled_all"
        assert result["new_result_rows"] == 2
        assert result["pending_races_before"] == 1
        assert result["pending_races_after"] == 0
        assert result["reconciled_races"] == 1
        assert result["result_fetch_errors"] == 0
        assert result["cumulative"]["evaluated_races"] == 1
    finally:
        ledger.close()


def test_reconcile_pending_shadow_results_skips_fetch_when_clear(tmp_path):
    ledger = ResidualShadowLedger(tmp_path / "shadow.sqlite3")
    try:
        ledger.record_predictions(_predictions())
        ledger.record_results(_results())

        def fail_fetcher(_request):
            raise AssertionError("fetcher must not run without pending races")

        result = reconcile_pending_shadow_results(
            ledger,
            result_fetcher=fail_fetcher,
        )

        assert result["status"] == "no_pending_results"
        assert result["new_result_rows"] == 0
        assert result["pending_races_before"] == 0
        assert result["pending_races_after"] == 0
        assert result["reconciled_races"] == 0
    finally:
        ledger.close()
