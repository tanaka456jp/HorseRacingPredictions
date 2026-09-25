from datetime import datetime, timedelta, timezone

import pytest

from horse_racing_predictions.odds_provider import (
    CsvOddsSnapshotProvider,
    InMemoryOddsProvider,
    JraVanDataLabProvider,
    PaidDataGateError,
    latest_snapshots_by_horse,
)
from horse_racing_predictions.snapshots import PreRaceOddsSnapshot


UTC = timezone.utc


def _snapshot(horse_id, odds, minute):
    post = datetime(2026, 10, 10, 6, 30, tzinfo=UTC)
    return PreRaceOddsSnapshot(
        race_id="R1",
        horse_id=horse_id,
        horse_name=f"HORSE {horse_id}",
        decimal_odds=odds,
        observed_at=post - timedelta(minutes=minute),
        scheduled_post_time=post,
        source="memory",
        source_reference=f"{horse_id}-{minute}",
    )


def test_in_memory_provider_and_latest_snapshot_selection():
    snapshots = [
        _snapshot("H1", 5.0, 15),
        _snapshot("H1", 4.5, 5),
        _snapshot("H2", 8.0, 10),
    ]
    provider = InMemoryOddsProvider(snapshots)

    race = provider.snapshots_for_race("R1")
    assert len(race) == 3

    latest = latest_snapshots_by_horse(race)
    assert len(latest) == 2
    by_horse = {item.horse_id: item for item in latest}
    assert by_horse["H1"].decimal_odds == 4.5
    assert by_horse["H2"].decimal_odds == 8.0


def test_csv_provider_requires_timezone_aware_pre_race_rows(tmp_path):
    csv_path = tmp_path / "odds.csv"
    csv_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time,source_reference\n"
        "R1,H1,ALPHA,5.2,2026-10-10T06:20:00+00:00,"
        "2026-10-10T06:30:00+00:00,q1\n",
        encoding="utf-8",
    )

    provider = CsvOddsSnapshotProvider(csv_path)
    rows = provider.snapshots_for_race("R1")
    assert len(rows) == 1
    assert rows[0].source == "manual_csv"
    assert rows[0].source_reference == "q1"


def test_csv_provider_rejects_naive_timestamp(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "race_id,horse_id,horse_name,decimal_odds,observed_at,"
        "scheduled_post_time\n"
        "R1,H1,ALPHA,5.2,2026-10-10T06:20:00,"
        "2026-10-10T06:30:00\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        CsvOddsSnapshotProvider(csv_path)


def test_paid_jravan_provider_is_closed_by_default():
    provider = JraVanDataLabProvider()
    with pytest.raises(PaidDataGateError, match="FREE-FIRST"):
        provider.snapshots_for_race("R1")

    approved = JraVanDataLabProvider(
        paid_data_gate_passed=True
    )
    with pytest.raises(NotImplementedError):
        approved.snapshots_for_race("R1")
