from pathlib import Path


def test_wsl_opencode_audit_is_free_only_and_non_installing():
    script = Path(
        "scripts/audit_wsl_opencode.ps1"
    ).read_text(encoding="utf-8")

    assert 'ExpectedComputerName = "DESKTOP-MVV1FD4"' in script
    assert "wsl.exe -l -q" in script
    assert "command -v opencode" in script
    assert "opencode --version" in script
    assert "opencode run --help" in script
    assert "http://127.0.0.1:11434/api/tags" in script
    assert 'required_model = "qwen3:8b"' in script
    assert "paid_cloud_provider_allowed = $false" in script
    assert "api_key_usage_allowed = $false" in script
    assert "codex_allowed = $false" in script
    assert "curl | sh" not in script
    assert "npm install" not in script


def test_wsl_opencode_audit_workflow_is_manual_or_marker_only():
    workflow = Path(
        ".github/workflows/wsl-opencode-audit-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "research/wsl_opencode_audit_request.txt" in workflow
    assert "runs-on: [self-hosted, Windows]" in workflow
    assert "persist-credentials: false" in workflow


def test_wsl_audit_treats_no_distro_as_diagnostic_not_install_request():
    script = Path(
        "scripts/audit_wsl_opencode.ps1"
    ).read_text(encoding="utf-8")

    assert "wsl_list_exit_code" in script
    assert "wsl_command_available = $true" in script
    assert "$distros.Count -gt 0" in script
