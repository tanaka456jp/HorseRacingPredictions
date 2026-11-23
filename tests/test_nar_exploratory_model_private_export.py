"""No real NAR data or native binaries: tests of optional private export."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from horse_racing_predictions.modeling import CatBoostProbabilityModel
from horse_racing_predictions.nar_exploratory_rank_screen import (
    NarExploratoryRankingMetrics, _FEATURES,
)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from screen_nar_pc2_exploratory_status_aware import (
    save_nar_exploratory_models_private,
)


class DummyNative:
    def __init__(self, payload):
        self.payload = payload
    def save_model(self, path):
        Path(path).write_bytes(self.payload)


def metrics():
    return NarExploratoryRankingMetrics(
        status="NAR_EXPLORATORY_2022_RANKING_ONLY_SELECTION_BIAS_HOLD",
        source_flat_races_2017_2022=79431,
        unresolved_flat_races_2017_2022=851,
        fit_races_2017_2021=65173,
        tune_races_2022=13402,
        unevaluable_tune_races_2022=138,
        fit_horses=500000,tune_horses=100000,
        winner_top1_hit_rate_2022=0.294508,
        random_baseline_top1_expected_2022=0.105,
        smoothed_prior_win_baseline_top1_2022=0.29,
        top1_uplift_over_simple_form_2022=0.004,
        top1_uplift_day_bootstrap_ci95_lower=-0.1,
        top1_uplift_day_bootstrap_ci95_upper=0.1,
        independent_2022_race_days=200,
        winner_top1_worst_case_all_flat_2022=0.29,
        winner_top1_best_case_all_flat_2022=0.30,
        top3_picks_podium_precision_2022=0.49,
        outsider_podium_hit_rate_2022=0.34,
    )


def models():
    a=CatBoostProbabilityModel(feature_columns=list(_FEATURES))
    b=CatBoostProbabilityModel(feature_columns=list(_FEATURES))
    a.model=DummyNative(b"SYNTHETIC_WIN_MODEL")
    b.model=DummyNative(b"SYNTHETIC_OUTSIDER_MODEL")
    return a,b


def test_opt_in_private_export_emits_hash_verified_research_contract(tmp_path):
    a,b=models()
    result=save_nar_exploratory_models_private(a,b,metrics(),tmp_path/"candidate")
    assert not result["publicationAuthorized"]
    assert result["sourceUploaded"] is False
    dest=tmp_path/"candidate"
    manifest=json.loads((dest/"candidate_manifest.json").read_text(encoding="utf-8"))
    assert manifest["jurisdiction"]=="NAR"
    assert manifest["trainEnd"]=="2021-12-31"
    assert manifest["researchMetrics"]["outsiderModelTarget"]=="finish_position_le_3_train_only"
    assert manifest["sourceRowsOrRaceIdentitiesExported"] is False
    assert len(result["artifactSha256"]["win.cbm"])==64
    assert len(result["artifactSha256"]["outsider.cbm"])==64
    with pytest.raises(Exception):
        save_nar_exploratory_models_private(a,b,metrics(),dest)


def test_unfitted_model_or_unsafe_features_rejected(tmp_path):
    a,b=models()
    b.model=None
    with pytest.raises(Exception):
        save_nar_exploratory_models_private(a,b,metrics(),tmp_path/"bad")
    assert not (tmp_path/"bad").exists()
