"""Fake archive CLI tests, no provider or private data files."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

from test_pre2025_research_assembler import _fictional_sources

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage_pre2025_research_local.py"
SPEC = spec_from_file_location("private_pre2025_stage_cli", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cli = module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def test_no_explicit_private_flag_never_stages(tmp_path, monkeypatch, capsys):
    sources = _fictional_sources(tmp_path)
    output = tmp_path / "not_created"
    monkeypatch.setattr(sys, "argv", [
        "stage_pre2025_research_local.py",
        "--source-jsonl", str(sources[0]),
        "--source-jsonl", str(sources[1]),
        "--destination", str(output),
    ])
    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("private research flag is required")
    assert not output.exists()


def test_fake_two_shard_cli_stages_only_private_unapproved_candidate(
    tmp_path, monkeypatch, capsys,
):
    sources = _fictional_sources(tmp_path)
    output = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "stage_pre2025_research_local.py",
        "--source-jsonl", str(sources[0]),
        "--source-jsonl", str(sources[1]),
        "--destination", str(output),
        "--private-research-only",
    ])
    assert cli.main() == 0
    response = capsys.readouterr().out
    report = json.loads(response)
    assert report["status"] == "PRIVATE_RESEARCH_STAGING_SOURCE_RIGHTS_PENDING"
    assert report["saved_runners"] == 8
    assert report["model_training_started"] is False
    assert report["publication_authorized"] is False
    assert "架空" not in response
    assert str(sources[0]) not in response
    assert not (output / "INCOMPLETE_DO_NOT_USE").exists()
    assert (output / "REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING").exists()
