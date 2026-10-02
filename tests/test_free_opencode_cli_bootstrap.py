from pathlib import Path


def test_free_opencode_cli_bootstrap_is_pinned_and_runner_scoped():
    script = Path(
        "scripts/install_free_opencode_cli.ps1"
    ).read_text(encoding="utf-8")

    assert '[string]$Version = "1.18.29"' in script
    assert '"opencode-ai@$Version"' in script
    assert "HorseRacingPredictionsAutonomousDev" in script
    assert "runner_isolated_localappdata" in script
    assert "paid_provider_used = $false" in script
    assert "api_key_used = $false" in script
    assert "codex_used = $false" in script
    assert "--no-audit" in script
    assert "--no-fund" in script


def test_free_opencode_smoke_uses_only_local_ollama_qwen():
    script = Path(
        "scripts/smoke_free_opencode_ollama.ps1"
    ).read_text(encoding="utf-8")

    assert '[string]$Model = "ollama/qwen3:8b"' in script
    assert "http://127.0.0.1:11434/api/tags" in script
    assert '"provider": {' in script
    assert '"ollama": {' in script
    assert '"baseURL": "http://127.0.0.1:11434/v1"' in script
    assert "FREE_LOCAL_SMOKE_OK" in script
    assert "paid_provider_used = $false" in script
    assert "api_key_used = $false" in script
    assert "repository_modified = $false" in script


def test_free_opencode_bootstrap_workflow_has_no_paid_credentials():
    workflow = Path(
        ".github/workflows/free-opencode-cli-bootstrap-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "research/free_opencode_cli_bootstrap_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "persist-credentials: false" in workflow
    assert "OPENAI_API_KEY" not in workflow
    assert "ANTHROPIC_API_KEY" not in workflow
    assert "Codex" not in workflow
