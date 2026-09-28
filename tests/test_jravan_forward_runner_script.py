from pathlib import Path


def test_forward_runner_reads_json_as_utf8():
    script = Path("scripts/run_jravan_forward_runner.ps1").read_text(
        encoding="utf-8"
    )

    assert (
        "Get-Content -LiteralPath $inputSummaryPath -Raw -Encoding UTF8 "
        "| ConvertFrom-Json"
    ) in script
    assert (
        "Get-Content -LiteralPath $forwardSummaryPath -Raw -Encoding UTF8 "
        "| ConvertFrom-Json"
    ) in script


def test_forward_runner_uses_bounded_decision_window():
    script = Path("scripts/run_jravan_forward_runner.ps1").read_text(
        encoding="utf-8"
    )

    assert "[int]$MinLeadMinutes = 10" in script
    assert "[int]$MaxLeadMinutes = 70" in script
    assert '"--min-lead-minutes", [string]$MinLeadMinutes' in script
    assert '"--max-lead-minutes", [string]$MaxLeadMinutes' in script


def test_forward_runner_runs_residual_v12_paper_on_same_snapshot():
    script = Path("scripts/run_jravan_forward_runner.ps1").read_text(
        encoding="utf-8"
    )

    assert "scripts\\run_residual_v12_forward_paper.py" in script
    assert '"--history", $historyPath' in script
    assert '"--entries", $entriesPath' in script
    assert '"--odds", $oddsPath' in script
    assert '"--paper-ledger", $ledgerPath' in script
    assert '"--residual-model-cache", $residualModelCache' in script
    assert "$baseValidation.residual_v12_paper_executed = $true" in script
    assert "$baseValidation.residual_v12_paper_stale_odds_rows" in script
    assert "$baseValidation.residual_v12_live_execution_enabled" in script
