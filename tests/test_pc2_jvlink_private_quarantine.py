"""Purely fictional PC2 quarantine tests; no provider and no real records."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

from horse_racing_predictions.jravan import JvOpenResult, JvRawRecord
from test_jv_fixedwidth_ra_se_preflight import fictional_record

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quarantine_pc2_jvlink_currentweek_local.py"
SPEC = spec_from_file_location("private_jv_quarantine", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class FakeClient:
    calls = []

    def __init__(self, *, application_id):
        assert application_id == "UNKNOWN"
        self.calls.clear()

    def initialize(self):
        self.calls.append("JVInit")

    def open_race(self, *, from_time, option):
        assert from_time == "00000000000000"
        assert option == 2
        self.calls.append("JVOpen")
        return JvOpenResult(0, 0, 0, "")

    def wait_for_downloads(self, opened, *, max_polls, poll_seconds):
        assert max_polls == 8 and poll_seconds == 0.5

    def iter_records(self, **_):
        self.calls.append("JVGets")
        yield JvRawRecord("JG", "SENSITIVE-NON-RA")
        yield JvRawRecord("RA", fictional_record("RA"))
        yield JvRawRecord("SE", fictional_record("SE"))

    def close(self):
        self.calls.append("JVClose")


def _run(tmp_path, client=FakeClient, *, computer="DESKTOP-MVV1FD4",
         bits=64, space=2_000_000_000):
    return module.quarantine_currentweek_ra_se(
        output=tmp_path / "metadata.json",
        root=tmp_path / "pc2-private", client_factory=client,
        computer=computer, bits=bits, windows=True,
        quota_bytes=space,
    )


def test_private_snapshot_is_new_never_train_and_never_upload(tmp_path):
    report = _run(tmp_path)
    assert report["status"] == "QUARANTINED_PRIVATE_RECORDS_NOT_TRAINABLE"
    assert report["raCount"] == 1 and report["seCount"] == 1
    assert report["existingSnapshotsOverwritten"] is False
    assert report["protectedHoldoutTrainingAllowed"] is False
    assert report["publicationAuthorized"] is False
    assert report["rawDataUploaded"] is False
    assert FakeClient.calls == ["JVInit", "JVOpen", "JVGets", "JVClose"]
    snapshots = list((tmp_path / "pc2-private").iterdir())
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert (snapshot / "DO_NOT_TRAIN_OR_REPOST").exists()
    assert not (snapshot / "INCOMPLETE_DO_NOT_TRAIN").exists()
    raw = (snapshot / "race_raw.jsonl").read_text(encoding="utf8")
    assert len(raw.splitlines()) == 2
    manifest = json.loads(
        (snapshot / "private_manifest.json").read_text(encoding="utf8")
    )
    assert manifest["trainOnThisFile"] is False
    assert manifest["rawRedistributionAllowed"] is False
    assert manifest["publicationAuthorized"] is False
    assert "架空" not in (tmp_path / "metadata.json").read_text(encoding="utf8")
    report2 = _run(tmp_path)
    assert report2["status"] == "QUARANTINED_PRIVATE_RECORDS_NOT_TRAINABLE"
    assert len(list((tmp_path / "pc2-private").iterdir())) == 2


def test_no_x86_no_wrong_pc_no_local_file_creation(tmp_path):
    for pc, bits in (("PC1", 64), ("DESKTOP-MVV1FD4", 32)):
        report = _run(tmp_path, computer=pc, bits=bits)
        assert report["status"] == "BLOCKED"
        assert report["jvOpenAttempted"] is False
        assert not (tmp_path / "pc2-private").exists()


def test_low_free_space_never_calls_provider(tmp_path):
    report = _run(tmp_path, space=100)
    assert report["stage"] == "D_QUARANTINE_PRECONDITION_FAILED"
    assert report["jvOpenAttempted"] is False


def test_incomplete_se_rejected_and_partial_kept_only(tmp_path):
    class Incomplete(FakeClient):
        def iter_records(self, **_):
            yield JvRawRecord("RA", fictional_record("RA"))
    report = _run(tmp_path, client=Incomplete)
    assert report["status"] == "BLOCKED"
    assert report["savedLocally"] is False
    snapshots = list((tmp_path / "pc2-private").iterdir())
    assert len(snapshots) == 1
    assert (snapshots[0] / "INCOMPLETE_DO_NOT_TRAIN").exists()
    assert not (snapshots[0] / "race_raw.jsonl").exists()
    assert not (snapshots[0] / "private_manifest.json").exists()
