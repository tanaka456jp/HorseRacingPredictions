from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "phase11_jravan_bounded_export.py"
)
SPEC = importlib.util.spec_from_file_location(
    "phase11_jravan_bounded_export_script",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _args(tmp_path, *extra):
    return MODULE.build_parser().parse_args([
        "--plan-output",
        str(tmp_path / "plan.json"),
        "--output",
        str(tmp_path / "raw.jsonl"),
        "--summary",
        str(tmp_path / "summary.json"),
        *extra,
    ])


def test_default_entrypoint_is_plan_only_and_never_opens_provider(tmp_path, monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("provider must not open in plan-only mode")

    monkeypatch.setattr(
        MODULE,
        "export_phase11_bounded_history",
        forbidden,
    )
    result = MODULE.run(_args(tmp_path))

    assert result["status"] == "plan_only"
    assert result["provider_opened"] is False
    assert result["records_written"] == 0
    assert result["plan"]["end"] == "20249999999999"
    assert result["plan"]["protected_holdout"] == "2025-2026 untouched"
    assert (tmp_path / "plan.json").is_file()
    assert not (tmp_path / "raw.jsonl").exists()


@pytest.mark.parametrize(
    "flags,match",
    [
        (
            ["--execute", "--personal-research-rights-confirmed"],
            "zero-cost-entitlement",
        ),
        (
            ["--execute", "--zero-cost-entitlement-confirmed"],
            "personal-research-rights",
        ),
    ],
)
def test_execute_requires_both_explicit_attestations_before_provider_call(
    tmp_path,
    monkeypatch,
    flags,
    match,
):
    called = []

    def forbidden(**kwargs):
        called.append(kwargs)
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(
        MODULE,
        "export_phase11_bounded_history",
        forbidden,
    )

    with pytest.raises(RuntimeError, match=match):
        MODULE.run(_args(tmp_path, *flags))

    assert called == []


def test_explicit_execute_passes_only_bounded_range_to_guarded_export(
    tmp_path,
    monkeypatch,
):
    calls = []

    class Summary:
        records_written = 123
        output_sha256 = "a" * 64

    def fake_export(**kwargs):
        calls.append(kwargs)
        return Summary()

    monkeypatch.setattr(
        MODULE,
        "export_phase11_bounded_history",
        fake_export,
    )

    result = MODULE.run(
        _args(
            tmp_path,
            "--execute",
            "--zero-cost-entitlement-confirmed",
            "--personal-research-rights-confirmed",
        )
    )

    assert result["status"] == "bounded_export_complete"
    assert result["provider_opened"] is True
    assert result["records_written"] == 123
    assert result["raw_redistribution_allowed"] is False
    assert len(calls) == 1
    call = calls[0]
    assert call["jvopen_range"] == "20170101000000-20249999999999"
    assert call["zero_cost_entitlement_confirmed"] is True
    assert call["personal_research_rights_confirmed"] is True


def test_cli_rejects_holdout_crossing_range_in_plan_only_mode(tmp_path):
    args = _args(
        tmp_path,
        "--range",
        "20170101000000-20250101000000",
    )
    with pytest.raises(ValueError):
        MODULE.run(args)
    assert not (tmp_path / "plan.json").exists()
