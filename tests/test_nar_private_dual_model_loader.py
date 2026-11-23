"""Synthetic private NAR 5-feature artifact read, checksum, and gate tests."""
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from horse_racing_predictions.nar_private_dual_model_loader import (
    load_nar_private_dual_candidate, _NAR_FEATURES,
)


def model_dir(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    hashes = {}
    for name in ("win.cbm", "outsider.cbm"):
        payload = ("SYNTHETIC_CB_MODEL_" + name).encode("ascii")
        (candidate / name).write_bytes(payload)
        hashes[name] = sha256(payload).hexdigest()
    doc = {
        "schemaVersion": 1,
        "artifactKind": "dual-catboost-oddsfree-research-candidate",
        "status": "RESEARCH_NOT_APPROVED_FOR_PUBLICATION",
        "jurisdiction": "NAR",
        "sourceRef": "nar-personal-2017-2022-72months-reviewed-local",
        "generatedAt": "2026-11-23T10:00:00+00:00",
        "trainStart": "2017-01-01", "trainEnd": "2021-12-31",
        "featureColumns": list(_NAR_FEATURES),
        "artifactSha256": hashes,
        "publicationAuthorized": False,
        "retrainingOnProtectedHoldoutAllowed": False,
        "sourceRightsIndependentlyVerified": False,
        "independentOutsiderModelVerified": False,
        "modelRuntimeProvenanceVerified": False,
        "sourceRowsOrRaceIdentitiesExported": False,
        "researchMetrics": {
            "fitThrough": "2021-12-31",
            "winModelTarget": "is_winner",
            "outsiderModelTarget": "finish_position_le_3_train_only",
            "trainingRaces": 65173, "validationRaces": 13402,
            "publicationAuthorized": False,
            "positiveExpectedValueDemonstrated": False,
        },
    }
    (candidate / "candidate_manifest.json").write_text(
        json.dumps(doc), encoding="utf-8"
    )
    return candidate


class FakeNative:
    def __init__(self):
        self.feature_names_ = list(_NAR_FEATURES)
    def load_model(self, filename):
        assert Path(filename).is_file()


def test_nar_exact_five_features_not_jra_whitelist(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "catboost",
                        SimpleNamespace(CatBoostClassifier=FakeNative))
    candidate = model_dir(tmp_path)
    loaded = load_nar_private_dual_candidate(candidate)
    assert loaded.features == _NAR_FEATURES
    assert loaded.train_end == "2021-12-31"
    assert loaded.winner.model is not loaded.outsider.model
    assert loaded.digest_by_role["win.cbm"]


@pytest.mark.parametrize("mutate", [
    "unapproved", "extra_feature", "after_cutoff", "bad_checksum",
])
def test_nar_private_model_cannot_bypass_rights_feature_or_date(
    monkeypatch, tmp_path, mutate,
):
    monkeypatch.setitem(sys.modules, "catboost",
                        SimpleNamespace(CatBoostClassifier=FakeNative))
    candidate = model_dir(tmp_path)
    manifest = candidate / "candidate_manifest.json"
    document = json.loads(manifest.read_text())
    if mutate == "unapproved":
        document["publicationAuthorized"] = True
    elif mutate == "extra_feature":
        document["featureColumns"].append("finish_position")
    elif mutate == "after_cutoff":
        document["trainEnd"] = "2026-12-31"
    else:
        (candidate / "win.cbm").write_bytes(b"ALTERED")
    manifest.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        load_nar_private_dual_candidate(candidate)
