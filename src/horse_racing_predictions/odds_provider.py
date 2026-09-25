from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from .snapshots import PreRaceOddsSnapshot


class OddsProvider(Protocol):
    def snapshots_for_race(
        self,
        race_id: str,
    ) -> list[PreRaceOddsSnapshot]:
        ...


class PaidDataGateError(RuntimeError):
    pass


def _parse_iso_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def latest_snapshots_by_horse(
    snapshots: Iterable[PreRaceOddsSnapshot],
) -> list[PreRaceOddsSnapshot]:
    latest: dict[str, PreRaceOddsSnapshot] = {}
    for snapshot in snapshots:
        current = latest.get(snapshot.horse_id)
        if current is None or snapshot.observed_at > current.observed_at:
            latest[snapshot.horse_id] = snapshot
    return sorted(
        latest.values(),
        key=lambda item: item.horse_id,
    )


class InMemoryOddsProvider:
    def __init__(
        self,
        snapshots: Iterable[PreRaceOddsSnapshot],
    ):
        self._snapshots = list(snapshots)

    def snapshots_for_race(
        self,
        race_id: str,
    ) -> list[PreRaceOddsSnapshot]:
        return sorted(
            [
                snapshot
                for snapshot in self._snapshots
                if snapshot.race_id == race_id
            ],
            key=lambda item: (
                item.horse_id,
                item.observed_at,
            ),
        )


class CsvOddsSnapshotProvider:
    REQUIRED_COLUMNS = {
        "race_id",
        "horse_id",
        "horse_name",
        "decimal_odds",
        "observed_at",
        "scheduled_post_time",
    }

    def __init__(
        self,
        path: str | Path,
        default_source: str = "manual_csv",
    ):
        self.path = Path(path)
        self.default_source = default_source
        self._snapshots = self._load()

    def _load(self) -> list[PreRaceOddsSnapshot]:
        with self.path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            missing = self.REQUIRED_COLUMNS - fieldnames
            if missing:
                raise ValueError(
                    f"missing CSV odds columns: {sorted(missing)}"
                )

            snapshots = []
            for row_number, row in enumerate(reader, start=2):
                try:
                    source = (
                        row.get("source", "").strip()
                        or self.default_source
                    )
                    reference = row.get(
                        "source_reference",
                        "",
                    ).strip()

                    snapshots.append(
                        PreRaceOddsSnapshot(
                            race_id=row["race_id"].strip(),
                            horse_id=row["horse_id"].strip(),
                            horse_name=row["horse_name"].strip(),
                            decimal_odds=float(row["decimal_odds"]),
                            observed_at=_parse_iso_datetime(
                                row["observed_at"]
                            ),
                            scheduled_post_time=_parse_iso_datetime(
                                row["scheduled_post_time"]
                            ),
                            source=source,
                            source_reference=reference,
                        )
                    )
                except Exception as exc:
                    raise ValueError(
                        f"invalid odds CSV row {row_number}: {exc}"
                    ) from exc
        return snapshots

    def snapshots_for_race(
        self,
        race_id: str,
    ) -> list[PreRaceOddsSnapshot]:
        return sorted(
            [
                snapshot
                for snapshot in self._snapshots
                if snapshot.race_id == race_id
            ],
            key=lambda item: (
                item.horse_id,
                item.observed_at,
            ),
        )


class JraVanDataLabProvider:
    """
    Reserved paid provider adapter.

    JRA-VAN Data Lab is not enabled while the FREE-FIRST paid-data
    gate remains closed.  This class intentionally exposes no
    acquisition implementation yet.
    """

    def __init__(
        self,
        paid_data_gate_passed: bool = False,
    ):
        self.paid_data_gate_passed = paid_data_gate_passed

    def snapshots_for_race(
        self,
        race_id: str,
    ) -> list[PreRaceOddsSnapshot]:
        if not self.paid_data_gate_passed:
            raise PaidDataGateError(
                "JRA-VAN Data Lab is disabled by the FREE-FIRST "
                "paid-data gate."
            )
        raise NotImplementedError(
            "JRA-VAN Data Lab adapter is reserved but not implemented."
        )
