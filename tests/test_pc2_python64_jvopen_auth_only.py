"""Fake COM clients only; validates privacy-safe 64-bit auth diagnostics."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from horse_racing_predictions.jravan import JraVanApiError, JvOpenResult

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_pc2_python64_jvopen_auth_only.py"
SPEC = spec_from_file_location("pc2_python_auth_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mod = module_from_spec(SPEC)
import sys
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
        self.calls.append("JVOpen")
        assert from_time == "00000000000000" and option == 2
        return JvOpenResult(0, 0, 0, "")

    def close(self):
        self.calls.append("JVClose")


def test_x64_fake_success_never_reads_data_or_leaks_secrets(tmp_path):
    FakeClient.instances.clear()
    report = mod.probe_python64_jvopen(
        output=tmp_path / "summary.json", client_factory=FakeClient,
        bits=64, computer="DESKTOP-MVV1FD4", windows=True,
    )
    assert report["status"] == "JVOPEN_AUTHENTICATED"
    assert report["jvInitSucceeded"] is True
    assert report["jvOpenReturnCode"] == 0
    assert report["jvCloseSucceeded"] is True
    assert FakeClient.instances[-1].calls == ["JVInit", "JVOpen", "JVClose"]
    for key in ("usageKeyRead", "rawRecordsRead",
                "protectedHoldoutOpened", "publicationAuthorized",
                "notePostAttempted"):
        assert report[key] is False
    serialized = (tmp_path / "summary.json").read_text()
    assert "licence" not in serialized.lower()
    assert "horse_name" not in serialized.lower()


def test_x86_blocked_before_client_construct(tmp_path):
    def forbidden(**_):
        raise AssertionError("x86 must not attempt provider")
    report = mod.probe_python64_jvopen(
        output=tmp_path / "summary.json", client_factory=forbidden,
        bits=32, computer="DESKTOP-MVV1FD4", windows=True,
    )
    assert report["status"] == "BLOCKED"
    assert report["stage"] == "WINDOWS_PC2_PYTHON64_REQUIRED"
    assert report["jvOpenAttempted"] is False


def test_simulated_minus301_is_sanitized_and_closed(tmp_path):
    class Refused(FakeClient):
        def open_race(self, *, from_time, option):
            self.calls.append("JVOpen")
            raise JraVanApiError("JVOpen failed with return code -301")
    report = mod.probe_python64_jvopen(
        output=tmp_path / "summary.json", client_factory=Refused,
        bits=64, computer="DESKTOP-MVV1FD4", windows=True,
    )
    assert report["status"] == "BLOCKED"
    assert report["jvOpenReturnCode"] == -301
    assert report["jvCloseSucceeded"] is True
    assert Refused.instances[-1].calls == ["JVInit", "JVOpen", "JVClose"]


def test_com_creation_failure_no_raw_message_leaks(tmp_path):
    def failed(**_):
        raise RuntimeError("SECRET usage_key=not-for-upload")
    report = mod.probe_python64_jvopen(
        output=tmp_path / "summary.json", client_factory=failed,
        bits=64, computer="DESKTOP-MVV1FD4", windows=True,
    )
    assert report["status"] == "BLOCKED"
    assert report["stage"] == "COM_DISPATCH"
    assert "SECRET" not in (tmp_path / "summary.json").read_text()
    assert report["rawRecordsRead"] is False


def test_unverified_physical_pc_blocks_com(tmp_path):
    report = mod.probe_python64_jvopen(
        output=tmp_path / "summary.json",
        client_factory=lambda **_: (_ for _ in ()).throw(
            AssertionError("wrong PC must not call COM")
        ),
        bits=64, computer="PC1", windows=True,
    )
    assert report["jvOpenAttempted"] is False
    assert report["status"] == "BLOCKED"
