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


def test_free_nemotron_audit_workflow_is_pc1_marker_triggered():
    workflow = Path(
        ".github/workflows/free-nemotron-opencode-audit-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "research/free_nemotron_opencode_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "persist-credentials: false" in workflow
    assert "audit_free_nemotron_opencode.ps1" in workflow
    assert "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free" in workflow
