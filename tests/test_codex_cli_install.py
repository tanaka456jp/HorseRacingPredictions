from pathlib import Path


def test_codex_installer_uses_official_release_and_user_scope():
    script = Path("scripts/install_codex_cli.ps1").read_text(
        encoding="utf-8"
    )

    assert 'ExpectedComputerName = "DESKTOP-MVV1FD4"' in script
    assert "repos/openai/codex/releases/latest" in script
    assert 'codex-x86_64-pc-windows-msvc.exe' in script
    assert 'Programs\OpenAI\Codex' in script
    assert '[Environment]::SetEnvironmentVariable("Path"' in script
    assert 'Remove-Item Env:OPENAI_API_KEY' in script
    assert "api_key_used = $false" in script
    assert "secrets_included = $false" in script


def test_codex_install_workflow_is_manual_or_marker_only():
    workflow = Path(
        ".github/workflows/install-codex-cli-self-hosted.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "research/install_codex_cli_request.txt" in workflow
    assert "persist-credentials: false" in workflow
    assert 'ExpectedComputerName "DESKTOP-MVV1FD4"' in workflow
