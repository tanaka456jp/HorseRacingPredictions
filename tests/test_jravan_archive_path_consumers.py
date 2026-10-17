from pathlib import Path


CONSUMERS = (
    Path("scripts/archive_jravan_free_trial_pre2025.py"),
    Path("scripts/build_jravan_pedigree_snapshot.py"),
    Path("scripts/reassess_jravan_free_trial_archive.py"),
    Path("scripts/evaluate_exotic_pedigree_phase12.py"),
    Path("scripts/evaluate_exotic_conditional_partner_phase13.py"),
)


def test_jravan_archive_consumers_use_shared_d_preferred_resolver_only():
    for path in CONSUMERS:
        text = path.read_text(encoding="utf-8")
        assert (
            "from horse_racing_predictions.jravan_archive_paths import"
            in text
        ), path
        assert "default_archive_root," in text, path
        assert "def default_archive_root()" not in text, path


def test_jravan_archive_consumers_do_not_hardcode_localappdata_archive():
    for path in CONSUMERS:
        text = path.read_text(encoding="utf-8")
        assert "LOCALAPPDATA" not in text, path
        assert "AppData\\Local\\HorseRacingPredictions" not in text, path


def test_shared_resolver_declares_d_drive_archive_as_primary_windows_location():
    text = Path(
        "src/horse_racing_predictions/jravan_archive_paths.py"
    ).read_text(encoding="utf-8")
    assert (
        'r"D:\\JRA-VAN\\Data Lab\\archive\\pre2025"'
        in text
    )
    assert 'd_root = Path("D:\\\\")' in text
    assert "if d_root.exists()" in text
    assert "migration_receipt.json" in text
    assert "return D_DRIVE_ARCHIVE_ROOT" in text
