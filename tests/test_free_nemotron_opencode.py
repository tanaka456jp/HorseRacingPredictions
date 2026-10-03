from pathlib import Path


def test_free_nemotron_audit_is_exact_free_model_only():
    script = Path("scripts/audit_free_nemotron_opencode.ps1").read_text(
        encoding="utf-8"
    )

    model = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert model in script
    assert 'Only the exact OpenRouter Nemotron 3 Ultra :free model is allowed.' in script
    assert 'paid_provider_used = $false' in script
    assert 'paid_fallback_allowed = $false' in script
    assert 'free_model_suffix_verified = $Model.EndsWith(":free")' in script
    assert "OPENROUTER_NOT_AUTHENTICATED" in script
    assert "FREE_NEMOTRON_SMOKE_OK" in script
    assert "raw_model_output_included = $false" in script
    assert "secrets_included = $false" in script


def test_free_nemotron_audit_never_exposes_or_falls_back_to_paid_provider():
    script = Path("scripts/audit_free_nemotron_opencode.ps1").read_text(
        encoding="utf-8"
    )

    assert "OPENROUTER_API_KEY" in script
    assert "auth list" in script
    assert "authText" in script
    assert "Write-Host $authText" not in script
    assert "openrouter_authenticated" in script
    assert "paid_fallback_allowed=False" in script
    assert "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free" in script


def test_free_nemotron_audit_workflow_is_pc2_marker_triggered():
    workflow = Path(
        ".github/workflows/free-nemotron-opencode-audit-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "research/free_nemotron_opencode_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "Audit Free Nemotron OpenCode (PC2)" in workflow
    assert "DESKTOP-MVV1FD4 is PC2" in workflow
    assert "persist-credentials: false" in workflow
    assert "audit_free_nemotron_opencode.ps1" in workflow
    assert "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free" in workflow


def test_free_opencode_cycle_supports_exact_nemotron_free_model():
    script = Path("scripts/run_free_opencode_dev_cycle.ps1").read_text(
        encoding="utf-8"
    )

    model = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert '$NemotronFreeModel = "' + model + '"' in script
    assert "OPENROUTER_NOT_AUTHENTICATED" in script
    assert "OPENROUTER_API_KEY" in script
    assert 'Remove-Item "Env:OPENROUTER_API_KEY"' not in script
    assert '"model": "' + model + '"' in script
    assert '$fullPrompt = if ($isOllama)' in script
    assert "Invoking free OpenCode model=$Model" in script
    assert "switch away from the selected free model" in script


def test_free_nemotron_microtask_benchmark_preempts_qwen_autonomous_run():
    workflow = Path(
        ".github/workflows/free-nemotron-microtask-benchmark-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "research/free_nemotron_microtask_benchmark_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "Nemotron Free Microtask Benchmark (PC2)" in workflow
    assert "Run one guarded Nemotron free microtask on PC2" in workflow
    assert "DESKTOP-MVV1FD4 is PC2" in workflow
    assert "horse-racing-autonomous-development-pc1" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "audit_free_nemotron_opencode.ps1" in workflow
    assert "run_free_opencode_dev_cycle.ps1" in workflow
    assert 'Cycle 1' in workflow
    assert 'ModelTimeoutSeconds 600' in workflow
    assert "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free" in workflow
    assert "I_APPROVE_PAID_CODEX" not in workflow


def test_nemotron_workflows_receive_only_actions_secret_for_openrouter():
    audit = Path(
        ".github/workflows/free-nemotron-opencode-audit-self-hosted.yml"
    ).read_text(encoding="utf-8")
    benchmark = Path(
        ".github/workflows/free-nemotron-microtask-benchmark-self-hosted.yml"
    ).read_text(encoding="utf-8")

    secret_line = "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}"
    assert secret_line in audit
    assert benchmark.count(secret_line) == 2
    assert "OPENROUTER_API_KEY:" not in benchmark.replace(secret_line, "")


def test_free_nemotron_smoke_clears_stale_native_exit_code():
    script = Path("scripts/audit_free_nemotron_opencode.ps1").read_text(
        encoding="utf-8"
    )
    assert "$global:LASTEXITCODE = 0" in script
    assert script.strip().endswith("$global:LASTEXITCODE = 0")


def test_12h_autonomous_workflow_uses_exact_free_nemotron_and_secret():
    workflow = Path(
        ".github/workflows/free-opencode-autonomous-dev-12h-self-hosted.yml"
    ).read_text(encoding="utf-8")
    orchestrator = Path("scripts/run_free_opencode_dev_12h.ps1").read_text(
        encoding="utf-8"
    )

    model = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert model in workflow
    assert model in orchestrator
    assert "audit_free_nemotron_opencode.ps1" in workflow
    assert "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}" in workflow
    assert "paid_fallback_allowed = $false" in orchestrator
    assert 'provider = $providerName' in orchestrator
    assert 'api_key_used = $apiKeyUsed' in orchestrator
    assert "I_APPROVE_PAID_CODEX" not in workflow


def test_free_nemotron_smoke_retries_without_qwen_no_think_directive():
    script = Path("scripts/audit_free_nemotron_opencode.ps1").read_text(
        encoding="utf-8"
    )

    assert '$prompt = "Reply exactly FREE_NEMOTRON_SMOKE_OK.' in script
    assert "/no_think Reply exactly FREE_NEMOTRON_SMOKE_OK" not in script
    assert "for ($attempt = 1; $attempt -le 2; $attempt++)" in script
    assert "Retrying exact free Nemotron smoke after 30 seconds." in script
    assert "Start-Sleep -Seconds 30" in script
    assert "smoke_attempts = $AttemptsUsed" in script
    assert "smoke_attempts=$attemptsUsed" in script
