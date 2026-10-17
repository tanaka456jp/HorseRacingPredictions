from pathlib import Path


SCRIPT = Path("scripts/prepare_jravan_validation_storage.ps1")
WORKFLOW = Path(
    ".github/workflows/jravan-validation-storage-self-hosted.yml"
)
DOC = Path("docs/JRAVAN_RACE_FREE_TRIAL_HANDOFF.md")


def test_validation_storage_only_prepares_d_drive():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'D:\\JRA-VAN\\Data Lab' in text
    assert "New-Item -ItemType Directory" in text
    assert "provider_cache_moved = $false" in text
    assert "jvlink_settings_changed = $false" in text
    assert "provider_access_attempted = $false" in text
    assert "usage_key_read = $false" in text
    assert "paid_action_authorized = $false" in text


def test_validation_storage_does_not_touch_c_cache_or_registry():
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "Remove-Item",
        "Move-Item",
        "Copy-Item",
        "Set-ItemProperty",
        "New-ItemProperty",
        "reg.exe",
        "JVOpen",
        "JVRTOpen",
        "JVInit",
    )
    assert all(value not in text for value in forbidden)


def test_validation_storage_requires_safe_d_free_space():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "MinimumFreeGiB = 20" in text
    assert "Get-PSDrive -Name D" in text
    assert "free space is below the safety minimum" in text


def test_validation_storage_workflow_is_self_hosted_and_sanitized():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text
    assert "prepare_jravan_validation_storage.ps1" in text
    upload = text.split(
        "- name: Publish sanitized storage preparation report",
        maxsplit=1,
    )[1]
    assert "jravan_validation_storage.json" in upload
    assert "race_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload


def test_handoff_keeps_free_trial_and_holdout_boundaries():
    text = DOC.read_text(encoding="utf-8")
    assert "do not switch to a paid service" in text.lower()
    assert "20170101000000" in text
    assert "20249999999999" in text
    assert "do not request 2025 or 2026 data" in text.lower()
    assert "64-bit Data Lab validation tool" in text
