"""Synthetic JV-Data RA/SE fixed-width layout checks only."""
from __future__ import annotations

from horse_racing_predictions.jv_fixedwidth_ra_se_preflight import (
    verify_ra_se_fixed_width,
)


def fictional_record(kind: str, *, course: str = "05",
                     year: str = "2026", md: str = "1101") -> str:
    data = bytearray(b" " * (1272 if kind == "RA" else 555))
    data[0:2] = kind.encode("ascii")
    data[2:3] = b"1"
    data[11:15] = year.encode("ascii")
    data[15:19] = md.encode("ascii")
    data[19:21] = course.encode("ascii")
    data[21:27] = b"010101"
    return data.decode("cp932")


def test_fictional_ra_and_se_are_fixed_width_without_identity_output():
    for kind in ("RA", "SE"):
        result = verify_ra_se_fixed_width(kind, fictional_record(kind))
        assert result.record_type == kind
        assert result.length_valid and result.header_valid
        assert result.jra_course_code_valid
        assert result.date_shape_valid
        assert result.codepage_roundtrip_valid
        assert "2026" not in str(result)


def test_malformed_records_are_reported_without_leaking_bytes():
    assert not verify_ra_se_fixed_width("RA", "RA").length_valid
    assert not verify_ra_se_fixed_width("SE", fictional_record("SE", course="99")).jra_course_code_valid
    assert not verify_ra_se_fixed_width("RA", fictional_record("RA", md="9999")).date_shape_valid
    assert not verify_ra_se_fixed_width("RA", fictional_record("RA", year="AAAB")).date_shape_valid


def test_unknown_record_types_cannot_be_reinterpreted_as_ra():
    try:
        verify_ra_se_fixed_width("JG", fictional_record("RA"))
    except ValueError as exc:
        assert "RA/SE" in str(exc)
    else:
        raise AssertionError("non-RA/SE layout accepted")


def test_actual_production_ra_se_parser_imports_without_pandas_side_effect():
    from horse_racing_predictions.jravan_parser import parse_ra, parse_se
    ra = parse_ra(fictional_record("RA"))
    se = parse_se(fictional_record("SE"))
    assert ra.race_id == se.race_id
    assert ra.race_date == "2026-11-01"
    assert se.finish_position is None
    assert ra.racecourse_code == "05"
