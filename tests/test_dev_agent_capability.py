from pathlib import Path


def test_dev_agent_capability_audit_is_pc1_guarded_and_sanitized():
    script = Path(
        "scripts/audit_dev_agent_capability.ps1"
    ).read_text(encoding="utf-8")

    assert 'ExpectedComputerName = "DESKTOP-MVV1FD4"' in script
    assert '"codex"' in script
    assert '"opencode"' in script
    assert '"claude"' in script
    assert '"aider"' in script
    assert '"gh"' in script
    assert '"login", "status"' in script
    assert '"auth", "status", "--hostname", "github.com"' in script
    assert "secrets_included = $false" in script
    assert "raw_auth_output_included = $false" in script
    assert "live_execution_enabled = $false" in script


def test_dev_agent_capability_workflow_has_no_schedule():
    workflow = Path(
        ".github/workflows/dev-agent-capability-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "research/dev_agent_capability_request.txt" in workflow
    assert "persist-credentials: false" in workflow
    assert 'ExpectedComputerName "DESKTOP-MVV1FD4"' in workflow
