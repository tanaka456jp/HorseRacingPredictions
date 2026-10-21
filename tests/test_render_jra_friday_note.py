"""Offline sample handoff cannot implicitly grant note publication."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_jra_friday_note.py"
_spec = importlib.util.spec_from_file_location("render_jra_friday_note", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def sample():
    factors = [
        {"category": name, "finding": "合成データ検証のみ",
         "source_url": "https://example.org/synthetic",
         "observed_at": "2026-10-22T09:00:00+09:00"}
        for name in ("近走内容", "距離適性", "血統")
    ]
    return {
        "issue_date": "2026-10-23",
        "generated_at": "2026-10-23T19:00:00+09:00",
        "model_id": "synthetic-research-v1",
        "model_frozen_at": "2026-10-21T13:00:00+09:00",
        "input_approved_for_research": True,
        "complete_race_manifest": True,
        "expected_race_ids": ["JRA-20261024-01A"],
        "races": [{
            "race_id": "JRA-20261024-01A", "title": "架空土曜競走",
            "course": "架空芝1600m",
            "post_at": "2026-10-24T10:30:00+09:00",
            "status": "confirmed",
            "horses": [
                {"name": "架空馬" + str(n), "number": n,
                 "strength": 8.0 - n, "factors": factors}
                for n in range(1, 5)
            ],
        }],
    }


def test_handoff_always_requires_an_independent_publication_approval(tmp_path):
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(sample(), ensure_ascii=False), encoding="utf-8")
    article, receipt_path = _module.render_handoff(input_file, tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["articleSha256"] == sha256(article.read_bytes()).hexdigest()
    assert receipt["sourceManifestSha256"] == sha256(input_file.read_bytes()).hexdigest()
    assert receipt["episodeId"] == "20261023"
    assert receipt["raceCount"] == 1
    assert receipt["status"] == "REVIEW_REQUIRED_NOT_APPROVED_FOR_AUTOPUBLISH"
    for key in (
        "sourceRightsIndependentlyVerified", "fullWeekendManifestVerified",
        "frozenOddsFreeModelVerified", "realHorseIdentityVerified",
        "pointInTimeFeatureGatePassed"
    ):
        assert receipt[key] is False
    assert receipt["syntheticOnly"] is True
    with pytest.raises(ValueError, match="already exists"):
        _module.render_handoff(input_file, tmp_path)


def test_rejects_market_input_without_writing_episode(tmp_path):
    fake = sample()
    fake["odds"] = 10
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(fake), encoding="utf-8")
    with pytest.raises(ValueError, match="article envelope mismatch|forbidden"):
        _module.render_handoff(input_file, tmp_path)
    assert not list(tmp_path.glob("*.md"))


def test_rejects_missing_output_directory(tmp_path):
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(sample()), encoding="utf-8")
    with pytest.raises(ValueError, match="existing local"):
        _module.render_handoff(input_file, tmp_path / "absent")
