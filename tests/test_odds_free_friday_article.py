"""Synthetic-only checks: no invented horses, odds, post-race evidence or Sunday frames."""
from copy import deepcopy
import pytest
from horse_racing_predictions.odds_free_friday_article import (
    ForecastInputError, render_friday_jra_article,
)


def race(id, name, when, status):
    factors = [
        {"category": "近走内容", "finding": "過去レースのペース補正済み評価",
         "source_url": "https://example.org/history", "observed_at": "2026-10-22T09:00:00+09:00"},
        {"category": "距離適性", "finding": "過去の同距離データによる比較",
         "source_url": "https://example.org/distance", "observed_at": "2026-10-22T09:00:00+09:00"},
        {"category": "脚質・展開", "finding": "先行型・差し型の組み合わせ",
         "source_url": "https://example.org/pace", "observed_at": "2026-10-22T09:00:00+09:00"},
    ]
    return {
        "race_id": id, "title": name, "course": "仮想競馬場 芝1600m",
        "post_at": when, "status": status,
        "horses": [
            {"name": f"架空馬{i}", "number": i if status == "confirmed" else None,
             "strength": float(10 - i), "upside_score": float(i),
             "upside_signals": ["距離適性", "脚質・展開"], "factors": deepcopy(factors)}
            for i in range(1, 5)
        ],
    }


def fixture():
    saturday = race("JRA-20261024-01A", "仮想土曜1R",
                    "2026-10-24T10:00:00+09:00", "confirmed")
    sunday = race("JRA-20261025-01A", "仮想日曜1R",
                  "2026-10-25T10:00:00+09:00", "provisional")
    return {
        "issue_date": "2026-10-23",
        "generated_at": "2026-10-23T19:00:00+09:00",
        "model_id": "research-synthetic-frozen-model-v1",
        "model_frozen_at": "2026-10-21T15:00:00+09:00",
        "input_approved_for_research": True,
        "complete_race_manifest": True,
        "expected_race_ids": [saturday["race_id"], sunday["race_id"]],
        "races": [saturday, sunday],
    }


def test_fictional_article_is_ordered_and_sunday_is_provisional():
    text = render_friday_jra_article(fixture())
    assert "仮想土曜1R" in text and "仮想日曜1R" in text
    assert "1着予想：1番 架空馬1" in text
    assert "2着予想：2番 架空馬2" in text
    assert "3着予想：3番 架空馬3" in text
    assert "日曜・枠番未確定の暫定予想" in text
    assert "1着予想：架空馬1" in text
    assert text.count("### 穴馬1頭（非市場型の伏兵候補）：") == 2
    assert "穴馬1頭（非市場型の伏兵候補）：4番 架空馬4" in text
    assert "穴馬1頭（非市場型の伏兵候補）：架空馬4" in text
    assert "上振れ根拠" in text
    assert "人気薄・高配当・プラス期待値という意味ではありません" in text
    assert "人気順位・投票数・オッズ" in text


@pytest.mark.parametrize("patch", [
    {"issue_date": "2026-10-22"},
    {"generated_at": "2026-10-22T19:00:00+09:00"},
    {"generated_at": "2026-10-23T09:00:00+09:00"},
    {"model_frozen_at": "2026-10-23T20:00:00+09:00"},
    {"input_approved_for_research": False},
    {"complete_race_manifest": False},
    {"expected_race_ids": ["JRA-20261024-01A"]},
    {"odds": "33.2"},
    {"popularity": 1},
    {"market_rank": 1},
    {"final_payout": "1000"},
    {"market_upside_score": 0.9},
])
def test_invalid_envelope_or_market_data_blocks(patch):
    doc = fixture()
    doc.update(patch)
    with pytest.raises(ForecastInputError):
        render_friday_jra_article(doc)


def test_no_unseen_race_can_be_silently_dropped():
    doc = fixture()
    doc["races"].pop()
    with pytest.raises(ForecastInputError):
        render_friday_jra_article(doc)


def test_any_odds_popularity_feature_is_rejected():
    doc = fixture()
    doc["races"][0]["horses"][0]["odds"] = 4.0
    with pytest.raises(ForecastInputError):
        render_friday_jra_article(doc)


@pytest.mark.parametrize("edit", [
    lambda doc: doc["races"][0].update(status="provisional"),
    lambda doc: doc["races"][1].update(status="confirmed"),
    lambda doc: doc["races"][0]["horses"][0].update(number=None),
    lambda doc: doc["races"][1]["horses"][0].update(number=1),
    lambda doc: doc["races"][0]["horses"][1].update(name="架空馬1"),
    lambda doc: doc["races"][0]["horses"][1].update(number=1),
    lambda doc: doc["races"][0]["horses"][1].update(strength=float("nan")),
    lambda doc: doc["races"][0]["horses"][3].update(upside_score=float("inf")),
    lambda doc: doc["races"][0]["horses"][3].update(upside_score=0),
    lambda doc: doc["races"][0]["horses"][3].update(upside_score=True),
    lambda doc: doc["races"][0]["horses"][3].update(upside_signals=["距離適性"]),
    lambda doc: doc["races"][0]["horses"][3].update(upside_signals=["距離適性", "距離適性"]),
    lambda doc: doc["races"][0]["horses"][3].update(upside_signals=["距離適性", "天候"]),
    lambda doc: doc["races"][0]["horses"][3].update(upside_signals=["距離適性", "オッズ"]),
    lambda doc: doc["races"][0]["horses"][0]["factors"][0].update(observed_at="2026-10-24T11:00:00+09:00"),
    lambda doc: doc["races"][0]["horses"][0]["factors"][0].update(category="オッズ"),
    lambda doc: doc["races"][0]["horses"][0]["factors"][1].update(category="近走内容"),
    lambda doc: doc["races"][0]["horses"][0]["factors"][0].update(source_url="http://example.org/x"),
    lambda doc: doc["races"][0].update(post_at="2026-10-23T18:00:00+09:00"),
])
def test_future_info_unconfirmed_frame_duplicate_horse_invalid_factors_block(edit):
    doc = fixture()
    edit(doc)
    with pytest.raises(ForecastInputError):
        render_friday_jra_article(doc)


def test_market_free_ranking_responds_to_strength_not_random_tie():
    doc = fixture()
    doc["races"][0]["horses"][3]["strength"] = 20.0
    text = render_friday_jra_article(doc)
    assert "1着予想：4番 架空馬4" in text


def test_no_publish_permission_or_external_data_acquisition():
    doc = fixture()
    text = render_friday_jra_article(doc)
    assert "自動投稿承認" not in text
    assert "source_url" not in text


def test_outsider_selected_by_independent_condition_upside_not_fourth_strength():
    doc = fixture()
    race = doc["races"][0]
    additional = deepcopy(race["horses"][-1])
    additional.update(name="架空馬5", number=5, strength=1.0,
                      upside_score=99.0)
    race["horses"].append(additional)
    text = render_friday_jra_article(doc)
    assert "### 穴馬1頭（非市場型の伏兵候補）：5番 架空馬5" in text
    assert "### 穴馬1頭（非市場型の伏兵候補）：4番 架空馬4" not in text
    assert "### 3着予想：3番 架空馬3" in text
    assert text.count("### 穴馬1頭（非市場型の伏兵候補）：") == 2


def test_outsider_never_duplicates_top_three_even_if_upside_highest():
    doc = fixture()
    doc["races"][0]["horses"][0]["upside_score"] = 10000.0
    text = render_friday_jra_article(doc)
    assert "### 穴馬1頭（非市場型の伏兵候補）：4番 架空馬4" in text
    assert "### 穴馬1頭（非市場型の伏兵候補）：1番 架空馬1" not in text


def test_outsider_requires_uncontaminated_evidence_for_every_runner():
    doc = fixture()
    del doc["races"][1]["horses"][3]["upside_score"]
    with pytest.raises(ForecastInputError):
        render_friday_jra_article(doc)


def test_outsider_tie_determinism_and_no_market_based_tie_break():
    doc = fixture()
    race = doc["races"][0]
    another = deepcopy(race["horses"][-1])
    another.update(name="架空馬5", number=5, strength=1.0,
                   upside_score=race["horses"][-1]["upside_score"])
    race["horses"].append(another)
    text = render_friday_jra_article(doc)
    assert "### 穴馬1頭（非市場型の伏兵候補）：4番 架空馬4" in text
    assert text == render_friday_jra_article(deepcopy(doc))


def test_outsider_market_input_is_rejected_even_when_only_hidden_in_factors():
    doc = fixture()
    doc["races"][0]["horses"][3]["factors"][0]["payout_bonus"] = 2
    with pytest.raises(ForecastInputError):
        render_friday_jra_article(doc)


@pytest.mark.parametrize("finding", [
    "単勝オッズは4.0倍", "前売り 人気 1 位", "人気順に注目",
    "複勝 1.4倍", "単 勝 評 価", "ｵｯｽﾞ 4.5倍", "投票数 12345",
    "配当期待値を調整", "popularity rank: 3", "odds 4/1",
])
def test_factor_narrative_cannot_hide_market_or_odds_evidence(finding):
    doc = fixture()
    doc["races"][0]["horses"][0]["factors"][0]["finding"] = finding
    with pytest.raises(ForecastInputError, match="factor finding"):
        render_friday_jra_article(doc)


@pytest.mark.parametrize("source_url", [
    "https://example.org/odds/latest",
    "https://example.org/%E5%8D%98%E5%8B%9D/results",
    "https://example.org/market_popularity/2026",
])
def test_market_related_source_url_is_rejected(source_url):
    doc = fixture()
    doc["races"][0]["horses"][0]["factors"][0]["source_url"] = source_url
    with pytest.raises(ForecastInputError, match="factor evidence URL"):
        render_friday_jra_article(doc)


def test_market_based_model_id_is_rejected():
    doc = fixture()
    doc["model_id"] = "v1-market_odds_adjusted"
    with pytest.raises(ForecastInputError, match="model_id"):
        render_friday_jra_article(doc)


def test_non_market_race_factors_still_render():
    doc = fixture()
    doc["races"][0]["horses"][0]["factors"][0]["finding"] = (
        "前走の位置取りと上がり区間を考慮した比較"
    )
    assert "位置取り" in render_friday_jra_article(doc)
