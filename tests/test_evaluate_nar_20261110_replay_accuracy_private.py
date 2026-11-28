"""Synthetic full-cohort descriptive replay arithmetic."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from evaluate_nar_20261110_replay_accuracy_private import metrics, paired_accuracy


def test_full_denominator_and_refund():
    picks = {"a": (("1","2","3"),"4"), "b": (("1","2","3"),"4"),
             "c": (("1","2","3"),"4")}
    ranks = {"a":{"1":1,"2":2,"3":3,"4":4},
             "b":{"1":0,"2":1,"3":2,"4":3},
             "c":{"1":0,"2":1,"3":2,"4":3}}
    statuses = {r:{h:"FINISHED" for h in row} for r,row in ranks.items()}
    statuses["b"]["1"]="EXCLUDED_REFUND"
    statuses["c"]["1"]="SCRATCH_NOT_OFFERED"
    pay={"a":({"1":250},{}),"b":({"2":150},{}),"c":({"2":130},{})}
    out=metrics(picks,ranks,statuses,pay)
    assert out["races"] == 3
    assert out["top1_hits"] == 1
    assert out["top3_hits"] == 7
    assert out["outsider_top3_hits"] == 2
    assert out["paper_win_stake_yen"] == 200
    assert out["paper_win_return_yen"] == 350
    assert out["paper_win_gross_return_rate"] == 1.75
    assert out["refunded_win_slots"] == out["no_offer_win_slots"] == 1
    with pytest.raises(ValueError):
        metrics(picks,ranks,statuses,{"a":pay["a"]})
    pay["b"]=({"3":150},{})
    with pytest.raises(ValueError):
        metrics(picks,ranks,statuses,pay)


def test_matched_race_counts_no_statistical_claim():
    basic = {"a": (("1","2","3"),"4"), "b": (("1","2","3"),"4"),
             "c": (("1","2","3"),"4"), "d": (("1","2","3"),"4")}
    fitted = {"a": (("1","2","3"),"4"), "b": (("2","1","4"),"3"),
              "c": (("2","3","4"),"1"), "d": (("2","1","3"),"4")}
    ranks = {"a":{"1":1,"2":2,"3":3,"4":4},
             "b":{"1":2,"2":1,"3":4,"4":3},
             "c":{"1":1,"2":2,"3":3,"4":4},
             "d":{"1":2,"2":3,"3":1,"4":4}}
    out = paired_accuracy(basic, fitted, ranks)
    assert out["top1"] == {"both_hit":1,"catboost_only_hit":1,
                           "baseline_only_hit":1,"neither_hit":1}
    assert out["top3_overlap_comparison"] == {
        "catboost_better":1,"baseline_better":1,"equal":2}
    assert out["same_top1_selection_count"] == 1
    assert out["independent_race_days"] == 1
    assert out["day_cluster_confidence_interval"] is None
    assert not out["statistical_superiority_established"]
    with pytest.raises(ValueError):
        paired_accuracy(basic, fitted, {"a":ranks["a"]})
