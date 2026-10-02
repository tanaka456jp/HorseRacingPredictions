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


def test_free_opencode_bootstrap_allows_only_pinned_postinstall():
    script = Path(
        "scripts/install_free_opencode_cli.ps1"
    ).read_text(encoding="utf-8")

    assert '$approvedInstallScript = "opencode-ai@$Version"' in script
    assert "--ignore-scripts" in script
    assert "npm approve-scripts opencode-ai" in script
    assert 'install_script_policy = "pinned_single_package_only"' in script
    assert "approved_install_script = $approvedInstallScript" in script
    assert "npm approve-scripts --all" not in script
    assert "dangerously-allow-all-scripts" not in script


def test_free_opencode_bootstrap_executes_only_verified_package_postinstall():
    script = Path(
        "scripts/install_free_opencode_cli.ps1"
    ).read_text(encoding="utf-8")

    assert 'if ([string]$packageManifest.name -ne "opencode-ai")' in script
    assert "if ([string]$packageManifest.version -ne $Version)" in script
    assert "& node $postinstallPath" in script
    assert 'postinstall_execution = "explicit_pinned_package_script"' in script
    assert "target_binary_size_bytes = $targetBinarySize" in script
    assert "$targetBinarySize -lt 1000000" in script
    assert "npm rebuild opencode-ai" not in script


def test_free_opencode_bootstrap_repairs_broken_same_version_wrapper():
    script = Path(
        "scripts/install_free_opencode_cli.ps1"
    ).read_text(encoding="utf-8")

    assert "$existingExitCode = [int]$LASTEXITCODE" in script
    assert "$existingBinarySize -ge 1000000" in script
    assert "if (-not $existingHealthy)" in script
    assert "$actualExitCode = [int]$LASTEXITCODE" in script
    assert "$finalBinarySize -lt 1000000" in script
    assert "existing_install_healthy = [bool]$existingHealthy" in script
