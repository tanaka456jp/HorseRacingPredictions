"""JVGets smoke tests use synthetic local objects, never JRA-VAN."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from horse_racing_predictions.jravan import JvOpenResult, JvRawRecord

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_pc2_bounded_jvgets_record_types.py"
SPEC = spec_from_file_location("bounded_jvgets_records", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mod = module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class FakeClient:
    instances = []

    def __init__(self, *, application_id):
        assert application_id == "UNKNOWN"
        self.calls = []
        self.instances.append(self)

    def initialize(self):
        self.calls.append("JVInit")

    def open_race(self, *, from_time, option):
        assert from_time == "00000000000000"
        assert option == 2
        self.calls.append("JVOpen")
        return JvOpenResult(0, 25, 0, "20261026000000")

    def wait_for_downloads(self, opened, *, max_polls, poll_seconds):
        self.calls.append("JVStatus")
        assert max_polls == 8 and poll_seconds == 0.5

    def iter_records(self, *, buffer_size, wait_retries, wait_seconds):
        assert buffer_size == 150_000
        assert wait_retries == 3
        self.calls.append("JVGets")
        for x in range(100):
            yield JvRawRecord(
                record_type=("RA" if x % 2 == 0 else "SE"),
                text="UNPUBLISHABLE_REAL_HORSE=SECRET" * 15,
                file_name="private.xls",
            )

    def close(self):
        self.calls.append("JVClose")


def _execute(tmp_path, klass=FakeClient, bits=64, pc="DESKTOP-MVV1FD4"):
    return mod.probe_bounded_race_types(
        output=tmp_path / "summary.json", client_factory=klass,
        computer=pc, bits=bits, windows=True,
    )


def test_reads_no_more_than_twelve_types_and_never_publishes(tmp_path):
    FakeClient.instances.clear()
    result = _execute(tmp_path)
    assert result["status"] == "SAMPLE_METADATA_ONLY"
    assert result["stage"] == "CURRENT_WEEK_SAMPLE_READ"
    assert result["sampleRecordCount"] == 12
    assert result["recordTypeCounts"] == {"RA": 6, "SE": 6}
    assert FakeClient.instances[-1].calls == [
        "JVInit", "JVOpen", "JVStatus", "JVGets", "JVClose"
    ]
    for key in ("rawRecordsSaved", "rawRecordsUploaded", "usageKeyRead",
                "protectedHoldoutTrainingAttempted", "notePostAttempted",
                "publicationAuthorized"):
        assert result[key] is False
    data = (tmp_path / "summary.json").read_text(encoding="utf-8")
    assert "SECRET" not in data
    assert "private.xls" not in data
    assert "UNPUBLISHABLE_REAL_HORSE" not in data


def test_wrong_bitness_or_pc_never_touches_provider(tmp_path):
    def forbidden(**_):
        raise AssertionError("no provider access")
    for bits, pc in ((32, "DESKTOP-MVV1FD4"), (64, "PC1")):
        r = mod.probe_bounded_race_types(
            output=tmp_path / "summary.json",
            client_factory=forbidden, computer=pc, bits=bits, windows=True,
        )
        assert r["status"] == "BLOCKED"
        assert r["jvOpenAttempted"] is False


def test_failed_jvgets_still_closes_without_leaking_message(tmp_path):
    class Broken(FakeClient):
        def iter_records(self, **_):
            self.calls.append("JVGets")
            raise RuntimeError("secret C:/users/data KEYVALUE")
    r = _execute(tmp_path, klass=Broken)
    assert r["stage"] == "JVGETS_OR_RECORD_STREAM_FAILED"
    assert r["status"] == "BLOCKED"
    assert r["jvCloseSucceeded"] is True
    assert "KEYVALUE" not in (tmp_path / "summary.json").read_text()


def test_option_two_accepted_without_records_does_not_claim_real_data(tmp_path):
    class Empty(FakeClient):
        def iter_records(self, **_):
            self.calls.append("JVGets")
            return iter(())
    r = _execute(tmp_path, klass=Empty)
    assert r["stage"] == "CURRENT_WEEK_NO_RECORDS"
    assert r["sampleRecordCount"] == 0
    assert r["status"] == "SAMPLE_METADATA_ONLY"
    assert r["publicationAuthorized"] is False
