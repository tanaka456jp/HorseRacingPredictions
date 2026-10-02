from pathlib import Path


def test_paid_codex_workflows_require_explicit_manual_approval():
    install = Path(
        ".github/workflows/install-codex-cli-self-hosted.yml"
    ).read_text(encoding="utf-8")
    autonomous = Path(
        ".github/workflows/autonomous-dev-12h-self-hosted.yml"
    ).read_text(encoding="utf-8")

    for workflow in (install, autonomous):
        assert "workflow_dispatch:" in workflow
        assert "I_APPROVE_PAID_CODEX" in workflow
        assert "push:" not in workflow


def test_free_opencode_stack_audit_is_local_only_by_policy():
    script = Path(
        "scripts/audit_free_opencode_stack.ps1"
    ).read_text(encoding="utf-8")

    assert 'ExpectedComputerName = "DESKTOP-MVV1FD4"' in script
    assert "Resolve-OpenCodePath" in script
    assert '"ollama"' in script
    assert 'ollama_local_endpoint = "http://127.0.0.1:11434"' in script
    assert "paid_cloud_provider_allowed = $false" in script
    assert "codex_allowed_without_explicit_approval = $false" in script
    assert "api_key_usage_allowed_without_explicit_approval = $false" in script
    assert "secrets_included = $false" in script


def test_free_stack_audit_workflow_has_no_paid_provider_setup():
    workflow = Path(
        ".github/workflows/free-opencode-stack-audit-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "research/free_opencode_stack_request.txt" in workflow
    assert "OPENAI_API_KEY" not in workflow
    assert "ANTHROPIC_API_KEY" not in workflow


def test_free_stack_audit_discovers_user_install_and_ollama_api():
    script = Path(
        "scripts/audit_free_opencode_stack.ps1"
    ).read_text(encoding="utf-8")

    assert "Resolve-OpenCodePath" in script
    assert "AppData\\Roaming\\npm\\opencode.cmd" in script
    assert ".opencode\\bin\\opencode.exe" in script
    assert "Sanitize-UserPath" in script
    assert "http://127.0.0.1:11434/api/tags" in script
    assert "ollama_api_reachable" in script
