"""Network-free fictional ZIP/HTTP tests. Never contact NAR."""
from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from zipfile import ZipFile

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "acquire_pc2_nar_2017_2022_months.py"
_SPEC = importlib.util.spec_from_file_location("nar_official_pc2_download_fixture", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
A = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(A)


def _fake_zip(month, *, missing_member=False):
    sink = BytesIO()
    with ZipFile(sink, "w") as zf:
        for name in ("racelist", "horselist", "payback"):
            if missing_member and name == "payback":
                continue
            zf.writestr(f"{month}_{name}.csv", "FICTIONAL_" + name)
    return sink.getvalue()


class _Response:
    def __init__(self, url, month, *, broken=False, missing_member=False,
                 content_type="application/zip", missing_name=False):
        self.url = url
        self.body = BytesIO((b"INVALID" * 40) if broken else _fake_zip(
            month, missing_member=missing_member))
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(self.body.getvalue())),
        }
        if not missing_name:
            self.headers["Content-Disposition"] = (
                f'attachment; filename="{month}_1730041000_race.zip"')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def geturl(self):
        return self.url

    def read(self, n):
        return self.body.read(n)


class _Opener:
    def __init__(self, **flags):
        self.flags = flags
        self.calls = []

    def open(self, req, timeout):
        assert timeout == 45
        url = req.full_url
        assert url.startswith("https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?")
        q = parse_qs(urlsplit(url).query)
        assert q["type"] == ["monthly"]
        month = q["k_year"][0] + f"{int(q['k_month'][0]):02d}"
        self.calls.append(month)
        return _Response(url, month, **self.flags)


def test_only_official_explicit_study_months():
    assert A.official_race_url("201701") == (
        "https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?"
        "k_month=1&k_year=2017&type=monthly")
    assert "k_year=2022" in A.official_race_url("202212")
    for value in ("201613", "202301", "202511", "202611", "20171101"):
        with pytest.raises(A.AcquisitionFailure, match="NAR_DOWNLOAD_OUTSIDE_TRAIN_MONTHS"):
            A.official_race_url(value)


def test_private_downloader_resumes_without_overwriting(tmp_path):
    sender = _Opener()
    first = A.acquire(tmp_path, permission=True, pc2=False,
                      opener=sender, sleep=lambda _: None, max_downloads=1)
    assert first["sourceMonthsInitiallyPresent"] == 0
    assert first["newOfficialZipsValidated"] == 1
    assert first["monthsStillMissing"] == 71
    one = next(tmp_path.glob("*.zip"))
    before = one.read_bytes()
    second = A.acquire(tmp_path, permission=True, pc2=False,
                       opener=sender, sleep=lambda _: None, max_downloads=1)
    assert one.read_bytes() == before
    assert second["sourceMonthsInitiallyPresent"] == 1
    assert second["monthsStillMissing"] == 70
    assert sender.calls == ["201701", "201702"]
    assert not second["privateDataUploaded"]
    assert not second["positiveEvDemonstrated"]


def test_preexisting_201711_archive_is_skipped_untouched(tmp_path):
    old = tmp_path / "201711_1730041000_race.zip"
    old.write_bytes(_fake_zip("201711"))
    original = old.read_bytes()
    sender = _Opener()
    report = A.acquire(tmp_path, permission=True, pc2=False,
                       opener=sender, sleep=lambda _: None, max_downloads=1)
    assert report["sourceMonthsInitiallyPresent"] == 1
    assert "201711" not in sender.calls
    assert old.read_bytes() == original


@pytest.mark.parametrize(("flags", "reason"), [
    ({"broken": True}, "NAR_DOWNLOAD_OFFICIAL_ZIP_VALIDATION_FAILED"),
    ({"missing_member": True}, "NAR_DOWNLOAD_ARCHIVE_MEMBER_COUNT_INVALID"),
    ({"content_type": "text/html"}, "NAR_DOWNLOAD_UNEXPECTED_CONTENT_TYPE"),
    ({"missing_name": True}, "NAR_DOWNLOAD_OFFICIAL_FILENAME_MISSING"),
])
def test_invalid_candidate_never_committed(tmp_path, flags, reason):
    report = A.acquire(tmp_path, permission=True, pc2=False,
                       opener=_Opener(**flags), sleep=lambda _: None,
                       max_downloads=1)
    assert report["status"] == "INCOMPLETE_OFFICIAL_ACQUISITION_HOLD"
    assert report["staticStopReason"] == reason
    assert report["newOfficialZipsValidated"] == 0
    assert report["monthsStillMissing"] == 72
    assert list(tmp_path.iterdir()) == []


def test_existing_unapproved_year_and_duplicate_month_block_before_network(tmp_path):
    source = tmp_path / "202301_1730041000_race.zip"
    source.write_bytes(b"INVENTED")
    sender = _Opener()
    with pytest.raises(A.AcquisitionFailure, match="NAR_DOWNLOAD_UNEXPECTED_ZIP_PRESENT"):
        A.acquire(tmp_path, permission=True, pc2=False, opener=sender)
    assert sender.calls == []
    source.unlink()
    for stamp in ("1730041000", "1730041001"):
        (tmp_path / f"201711_{stamp}_race.zip").write_bytes(b"INVENTED")
    with pytest.raises(A.AcquisitionFailure, match="NAR_DOWNLOAD_DUPLICATE_EXISTING_MONTH"):
        A.acquire(tmp_path, permission=True, pc2=False, opener=sender)


def test_user_permission_and_physical_pc2_required(tmp_path, monkeypatch):
    sender = _Opener()
    with pytest.raises(A.AcquisitionFailure, match="NAR_DOWNLOAD_EXPLICIT_NAR_PERMISSION_REQUIRED"):
        A.acquire(tmp_path, permission=False, pc2=False, opener=sender)
    monkeypatch.delenv("COMPUTERNAME", raising=False)
    with pytest.raises(A.AcquisitionFailure, match="NAR_DOWNLOAD_WRONG_PHYSICAL_PC"):
        A.acquire(tmp_path, permission=True, pc2=True, opener=sender)
    assert sender.calls == []


def test_redirects_cannot_escape_provider_or_switch_month():
    redirect = A.OfficialOnlyRedirect()
    class Req:
        full_url = A.official_race_url("201701")
    for link in (
        "http://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?k_month=1&k_year=2017&type=monthly",
        "https://malicious.example/KeibaWeb/DataDownload/RaceDataDownload?k_month=1&k_year=2017&type=monthly",
    ):
        with pytest.raises(A.AcquisitionFailure, match="NAR_DOWNLOAD_UNAPPROVED_REDIRECT"):
            redirect.redirect_request(Req(), None, 302, "", {}, link)
    with pytest.raises(A.AcquisitionFailure, match="NAR_DOWNLOAD_CHANGED_MONTH_REDIRECT"):
        redirect.redirect_request(Req(), None, 302, "", {}, A.official_race_url("201702"))
