from pathlib import Path


SCRIPT = Path("scripts/probe_jravan_environment.ps1")
WORKFLOW = Path(
    ".github/workflows/jravan-environment-probe-self-hosted.yml"
)


def test_environment_probe_never_calls_provider_or_reads_usage_key():
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "JVOpen",
        "JVRTOpen",
        "JVInit",
        "usagekey",
        "利用キー",
        "GetValueNames",
    )
    assert all(value not in text for value in forbidden)
    assert "provider_access_attempted = $false" in text
    assert "registry_secrets_read = $false" in text
    assert "usage_key_read = $false" in text
    assert "raw_records_read = $false" in text


def test_environment_probe_checks_both_registry_views_and_python_bitness():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "RegistryView]::Registry32" in text
    assert "RegistryView]::Registry64" in text
    assert "struct.calcsize('P')*8" in text
    assert "dual_jvlink_registration" in text


def test_environment_probe_measures_provider_cache_without_listing_names():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "C:\\ProgramData\\JRA-VAN\\Data Lab\\data" in text
    assert "file_count" in text
    assert "total_bytes" in text
    assert "total_gib" in text
    assert "Select-Object Name" not in text
    assert "FullName" not in text


def test_environment_probe_checks_d_archive_and_free_space():
    text = SCRIPT.read_text(encoding="utf-8")
    assert (
        "D:\\HorseRacingPredictions\\JraVanFreeTrialArchive\\pre2025"
        in text
    )
    assert "Get-PSDrive -Name C" in text
    assert "Get-PSDrive -Name D" in text
    assert "c_free_gib" in text
    assert "d_free_gib" in text


def test_environment_probe_workflow_is_self_hosted_and_sanitized():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows]" in text
    assert "probe_jravan_environment.ps1" in text
    assert "jravan_environment_probe.json" in text
    upload = text.split(
        "- name: Publish sanitized environment report only",
        maxsplit=1,
    )[1]
    assert "race_raw.jsonl" not in upload
    assert "pedigree_snapshot.csv" not in upload
    assert "latest_manifest" not in upload
