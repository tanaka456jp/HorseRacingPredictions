"""Only invented race rows: no NAR personal ZIP or source records."""
from __future__ import annotations

import csv
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
import json
from pathlib import Path

import pytest

from test_nar_local_monthly_intake import _make_zip
from test_nar_published_result_normalizer import _fixture


script = Path(__file__).resolve().parents[1] / "scripts" / "probe_nar_private_csv_header_shapes.py"
spec = spec_from_file_location("nar_private_finish_marker_probe", script)
assert spec is not None and spec.loader is not None
module = module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize(("raw", "expected"), [
    ("1", "NUMERIC_RANK"),
    ("１８", "NUMERIC_RANK"),
    ("0", "OTHER_NUMBER"),
    ("19", "OTHER_NUMBER"),
    ("取消", "SCRATCH"),
    ("出走取消", "SCRATCH"),
    ("除外", "EXCLUDED"),
    ("競走除外", "EXCLUDED"),
    ("中止", "DID_NOT_FINISH"),
    ("競走中止", "DID_NOT_FINISH"),
    ("失格", "DISQUALIFIED"),
    ("取止", "RACE_CANCELLED"),
    ("不成", "NO_CONTEST"),
    ("３降", "DEMOTED"),
    ("  3 降着", "DEMOTED"),
    ("", "BLANK"),
    ("unknown fictional marker", "OTHER_TEXT"),
])
def test_rank_bucket_is_fixed_and_not_raw(raw, expected):
    category = module._safe_finish_bucket(raw)
    assert category == expected
    assert category.isascii()
    assert "fictional" not in category


def test_offline_fictional_zip_aggregates_exceptional_ranks_without_identities(tmp_path):
    data = _fixture(month="201711", with_header=True)
    rows = list(csv.reader(StringIO(data["horselist"])))
    rows[1][31] = "中止"
    rows[2][31] = "取消"
    rows[3][31] = "失格"
    text = StringIO(newline="")
    csv.writer(text).writerows(rows)
    path = _make_zip(tmp_path, month="201711", override={"horselist": text.getvalue()})
    original = path.read_bytes()
    result = module.inspect_header_shape(
        path, month="201711", permission_confirmed=True
    )
    stats = result["flatFinishRankAggregate"]
    assert stats["flatHorseRows"] == 8
    assert stats["horseRowsByFixedCategory"] == {
        "DID_NOT_FINISH": 1, "DISQUALIFIED": 1,
        "NUMERIC_RANK": 5, "SCRATCH": 1,
    }
    assert stats["flatRacesWithExceptionalRank"] == 1
    assert stats["flatRacesByExceptionalCategory"] == {
        "DID_NOT_FINISH": 1, "DISQUALIFIED": 1, "SCRATCH": 1,
    }
    assert stats["rawRankTextExported"] is False
    assert result["sourceTextExported"] is False
    serialized = json.dumps(result, ensure_ascii=False)
    assert "架空" not in serialized
    assert "20171114" not in serialized
    assert str(path) not in serialized
    assert path.read_bytes() == original


def test_predeclared_obihiro_rows_do_not_appear_in_flat_rank_histogram(tmp_path):
    data = _fixture(month="201711", with_header=True)
    rows = list(csv.reader(StringIO(data["horselist"])))
    for row in rows[1:]:
        row[0] = "帯広ば"
        row[31] = "中止"
    text = StringIO(newline="")
    csv.writer(text).writerows(rows)
    path = _make_zip(tmp_path, month="201711", override={"horselist": text.getvalue()})
    stats = module.inspect_header_shape(
        path, month="201711", permission_confirmed=True
    )["flatFinishRankAggregate"]
    assert stats["flatHorseRows"] == 0
    assert stats["horseRowsByFixedCategory"] == {}
    assert stats["flatRacesWithExceptionalRank"] == 0


def test_context_only_reports_fixed_flags_never_source_text():
    row = [""] * 36
    row[32] = "競走中止"
    row[33] = "取消"
    row[34] = "38.9"
    row[35] = "8"
    sig, indicators = module._blank_finish_context(row)
    assert sig == "1111"
    assert indicators == {"TIME": "DID_NOT_FINISH", "MARGIN": "SCRATCH"}
    assert not any("取消" in value or "中止" in value
                   for value in indicators.values())


def test_blank_rank_context_report_is_aggregate_only_fictional_zip(tmp_path):
    dataset = _fixture(month="201711", with_header=True)
    records = list(csv.reader(StringIO(dataset["horselist"])))
    records[1][31] = ""
    records[1][33] = "出走取消"
    records[2][31] = ""
    records[2][32] = "競走中止"
    records[2][35] = ""
    encoded = StringIO(newline="")
    csv.writer(encoded).writerows(records)
    path = _make_zip(
        tmp_path, month="201711",
        override={"horselist": encoded.getvalue()},
    )
    original_bytes = path.read_bytes()
    report = module.inspect_header_shape(
        path, month="201711", permission_confirmed=True
    )
    info = report["flatBlankContextEvidence"]
    assert info["blankRowsByTimeMarginLast3fPopularityFlags"] == {
        "0101": 1, "1000": 1,
    }
    assert info["blankRowsWithAnyExplicitOfficialMarkerInOtherFields"] == 2
    assert info["explicitMarkersInOtherFieldsOnly"] == {
        "MARGIN_SCRATCH": 1, "TIME_DID_NOT_FINISH": 1,
    }
    assert info["unknownStatusRows"] == 0
    assert info["evidenceOnlyNotRefundOrLossClassification"]
    assert info["noRawFieldContentsExported"]
    serialized = json.dumps(report, ensure_ascii=False)
    assert "出走取消" not in serialized
    assert "競走中止" not in serialized
    assert "架空" not in serialized
    assert "20171114" not in serialized
    assert str(path) not in serialized
    assert path.read_bytes() == original_bytes
