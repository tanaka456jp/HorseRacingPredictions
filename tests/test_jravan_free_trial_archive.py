import json

import pytest

from horse_racing_predictions.jravan import JvLinkClient
from horse_racing_predictions.jravan_free_trial_archive import (
    FREE_TRIAL_ARCHIVE_DATASPECS,
    archive_free_trial_pre2025,
)


class FakeJv:
    def __init__(self):
        self.open_args = None
        self.closed = 0
        self.records = [
            ("SKabc", "sk.jvd"),
            ("HNdef", "hn.jvd"),
        ]

    def JVInit(self, app_id):
        return 0

    def JVOpen(self, dataspec, from_time, option, read_count, download_count, timestamp):
        self.open_args = (dataspec, from_time, option)
        return (0, 2, 0, "20241299999999")

    def JVStatus(self):
        return 0

    def JVGets(self, buff, size, fname):
        if not self.records:
            return (0, memoryview(b""), b"")
        text, name = self.records.pop(0)
        raw = text.encode("cp932")
        return (len(raw), memoryview(raw), name.encode("cp932"))

    def JVClose(self):
        self.closed += 1
        return 0


def test_open_data_accepts_bounded_range():
    fake = FakeJv()
    client = JvLinkClient(jvlink=fake)
    client.initialize()
    client.open_data(
        dataspec="BLDN",
        from_time="20170101000000-20249999999999",
        option=4,
    )
    assert fake.open_args == (
        "BLDN",
        "20170101000000-20249999999999",
        4,
    )


def test_archive_defaults_exclude_future_schedule_sources():
    assert "YSCH" not in FREE_TRIAL_ARCHIVE_DATASPECS
    assert "TOKU" not in FREE_TRIAL_ARCHIVE_DATASPECS
    assert "RACE" in FREE_TRIAL_ARCHIVE_DATASPECS
    assert "BLDN" in FREE_TRIAL_ARCHIVE_DATASPECS
    assert "DIFN" in FREE_TRIAL_ARCHIVE_DATASPECS


def test_archive_requires_free_entitlement_before_provider_open(tmp_path):
    called = []

    def factory():
        called.append(True)
        return JvLinkClient(jvlink=FakeJv())

    with pytest.raises(RuntimeError, match="zero-cost"):
        archive_free_trial_pre2025(
            archive_dir=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.json",
            dataspecs=("BLDN",),
            personal_research_rights_confirmed=True,
            client_factory=factory,
        )
    assert called == []


def test_archive_writes_hash_manifest_and_keeps_raw_local(tmp_path):
    created = []

    def factory():
        fake = FakeJv()
        created.append(fake)
        return JvLinkClient(jvlink=fake)

    manifest = archive_free_trial_pre2025(
        archive_dir=tmp_path / "raw",
        manifest_path=tmp_path / "manifest.json",
        dataspecs=("BLDN",),
        zero_cost_entitlement_confirmed=True,
        personal_research_rights_confirmed=True,
        client_factory=factory,
    )

    assert manifest.status == "complete"
    assert manifest.total_records_written == 2
    part = manifest.parts[0]
    assert part.record_type_counts == {"HN": 1, "SK": 1}
    assert len(part.output_sha256) == 64
    assert created[0].open_args[1] == "20170101000000-20249999999999"
    assert created[0].closed == 1
    raw = (tmp_path / "raw" / "bldn_raw.jsonl").read_text(encoding="utf-8")
    assert json.loads(raw.splitlines()[0])["record_type"] == "SK"


def test_archive_rejects_schedule_or_registration_dataspec(tmp_path):
    for spec in ("YSCH", "TOKU"):
        with pytest.raises(ValueError, match="excluded"):
            archive_free_trial_pre2025(
                archive_dir=tmp_path / "raw",
                manifest_path=tmp_path / "manifest.json",
                dataspecs=(spec,),
                zero_cost_entitlement_confirmed=True,
                personal_research_rights_confirmed=True,
            )
