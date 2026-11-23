"""Synthetic source and fake CatBoost only; real PC2 exercise is separate."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import replay_nar_20261110_preoff_real_model_private as R  # noqa: E402
from test_nar_official_daily_preoff import fictional_daily_zip  # noqa: E402
from test_freeze_nar_partial_catboost_daily_private import fake_model  # noqa: E402

DAY = date(2026, 11, 10)
OBS = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)
GEN = OBS + timedelta(minutes=2)


def test_real_preoff_zip_replay_contract_never_claims_prospective_hits(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    (tmp_path / "nar-prospective-captures").mkdir()
    baseline = {
        "source_races": 2, "source_horses": 8,
        "day": DAY.isoformat(),
        "host_observed_utc": OBS.isoformat(),
        "host_generated_utc": GEN.isoformat(),
        "odds_observed": False, "positive_ev_proven": False,
        "no_real_tickets": True,
    }
    monkeypatch.setattr(R, "_load_original_frozen_forecast",
                        lambda _, __: (baseline, fictional_daily_zip()))
    monkeypatch.setattr(R, "load_nar_private_dual_candidate",
                        lambda _: fake_model())
    result = R.replay_private_source(
        tmp_path, expected_races=2, expected_runners=8,
    )
    assert result["actual_native_two_catboost_models_executed"]
    assert result["official_prior_preoff_flat_races"] == 2
    assert result["official_prior_preoff_runners"] == 8
    assert not result["prospective_model_selection_frozen_before_results"]
    assert not result["prospective_hit_rate_measured"]
    assert not result["private_bytes_uploaded"]
    with pytest.raises(ValueError, match="DENOMINATOR"):
        R.replay_private_source(tmp_path, expected_races=59,
                                expected_runners=641)
