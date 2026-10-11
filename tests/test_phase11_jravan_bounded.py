from pathlib import Path

import pytest

from horse_racing_predictions.phase11_jravan_bounded import (
    PHASE11_MAX_CALENDAR_END,
    PHASE11_MIN_START,
    PHASE11_SAFE_SETUP_END,
    build_phase11_bounded_plan,
    export_phase11_bounded_history,
    validate_phase11_jvopen_range,
)


@pytest.mark.parametrize(
    "value",
    [
        "20170101000000-20241231235959",
        "20180101000000-20181231235959",
        "20240101000000-20241231235959",
        f"{PHASE11_MIN_START}-{PHASE11_MAX_CALENDAR_END}",
        f"{PHASE11_MIN_START}-{PHASE11_SAFE_SETUP_END}",
    ],
)
def test_bounded_range_accepts_only_pre2025_provider_windows(value):
    start, end = validate_phase11_jvopen_range(value)
    assert f"{start}-{end}" == value


@pytest.mark.parametrize(
    "value",
    [
        "20160101000000-20241231235959",
        "20170101000000-20250101000000",
        "20170101000000-20259999999999",
        "20170101000000-20249999999998",
        "20170101000000-20260101000000",
        "20241231235959-20170101000000",
        "20170101000000",
        "20170101000000-",
        "-20241231235959",
        "20170101000000-20240230000000",
        "not-a-range",
        None,
    ],
)
def test_bounded_range_rejects_unbounded_future_or_invalid_windows(value):
    with pytest.raises(ValueError):
        validate_phase11_jvopen_range(value)



def test_calendar_end_plan_remains_supported_but_is_not_full_year_setup_sentinel():
    plan = build_phase11_bounded_plan(
        "20170101000000-20241231235959"
    )
    assert plan.end == PHASE11_MAX_CALENDAR_END
    assert plan.end_kind == "calendar_timestamp"


def test_only_exact_2024_setup_sentinel_bypasses_real_timestamp_parser():
    for value in (
        "20170101000000-20249999999998",
        "20170101000000-20249899999999",
        "20170101000000-20239999999999",
    ):
        with pytest.raises(ValueError):
            validate_phase11_jvopen_range(value)

def test_plan_locks_option_record_types_and_holdout_boundary():
    plan = build_phase11_bounded_plan(
        "20170101000000-20249999999999"
    )
    assert plan.end == PHASE11_SAFE_SETUP_END
    assert plan.end_kind == "provider_year_setup_sentinel"
    assert plan.option == 4
    assert plan.record_types == ("RA", "SE")
    assert plan.protected_holdout == "2025-2026 untouched"
    assert plan.paid_data_allowed is False
    assert plan.unbounded_fallback_allowed is False
    assert plan.raw_redistribution_allowed is False


def test_export_requires_explicit_zero_cost_entitlement_before_provider_call(tmp_path):
    called = []

    def exporter(**kwargs):
        called.append(kwargs)
        raise AssertionError("provider must not be called")

    with pytest.raises(RuntimeError, match="zero-cost"):
        export_phase11_bounded_history(
            jvopen_range="20170101000000-20249999999999",
            output_path=tmp_path / "raw.jsonl",
            summary_path=tmp_path / "summary.json",
            personal_research_rights_confirmed=True,
            exporter=exporter,
        )

    assert called == []


def test_export_requires_explicit_personal_research_rights_before_provider_call(
    tmp_path,
):
    called = []

    def exporter(**kwargs):
        called.append(kwargs)
        raise AssertionError("provider must not be called")

    with pytest.raises(RuntimeError, match="personal research rights"):
        export_phase11_bounded_history(
            jvopen_range="20170101000000-20249999999999",
            output_path=tmp_path / "raw.jsonl",
            summary_path=tmp_path / "summary.json",
            zero_cost_entitlement_confirmed=True,
            exporter=exporter,
        )

    assert called == []


def test_invalid_holdout_crossing_range_is_rejected_before_provider_call(tmp_path):
    called = []

    def exporter(**kwargs):
        called.append(kwargs)
        raise AssertionError("provider must not be called")

    with pytest.raises(ValueError, match="end must be <="):
        export_phase11_bounded_history(
            jvopen_range="20170101000000-20250101000000",
            output_path=tmp_path / "raw.jsonl",
            summary_path=tmp_path / "summary.json",
            zero_cost_entitlement_confirmed=True,
            personal_research_rights_confirmed=True,
            exporter=exporter,
        )

    assert called == []


def test_bounded_export_passes_exact_server_range_without_fallback(tmp_path):
    calls = []

    class Summary:
        records_written = 10

    def exporter(**kwargs):
        calls.append(kwargs)
        return Summary()

    messages = []
    summary = export_phase11_bounded_history(
        jvopen_range="20170101000000-20249999999999",
        output_path=tmp_path / "raw.jsonl",
        summary_path=tmp_path / "summary.json",
        zero_cost_entitlement_confirmed=True,
        personal_research_rights_confirmed=True,
        exporter=exporter,
        progress_callback=messages.append,
    )

    assert summary.records_written == 10
    assert len(calls) == 1
    call = calls[0]
    assert call["from_time"] == "20170101000000-20249999999999"
    assert call["option"] == 4
    assert call["record_types"] == {"RA", "SE"}
    assert call["output_path"] == tmp_path / "raw.jsonl"
    assert call["summary_path"] == tmp_path / "summary.json"
    assert any("holdout=2025-2026_untouched" in item for item in messages)


def test_module_does_not_expose_recent_or_current_fallback_path():
    source = Path(
        "src/horse_racing_predictions/phase11_jravan_bounded.py"
    ).read_text(encoding="utf-8")
    assert "recent_normal_fallback" not in source
    assert "option=1" in source
    assert "2025-2026 final holdout" in source
