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
