"""Download only explicitly permitted official NAR race ZIPs, on physical PC2.

No JRA-VAN, paid API, login, scraping, automatic provider discovery, model
fitting, bets, held-out years or source-data uploads. Direct documented
download-button endpoint on keiba.go.jp; one bounded request at a time.
All candidate ZIPs pass CRC/member validation before non-overwriting storage
on a private D: drive. Reruns skip existing 2017–2022 months.
"""
from __future__ import annotations

import argparse
import email.message
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

_EXPECTED = tuple(f"{y}{m:02d}" for y in range(2017, 2023)
                  for m in range(1, 13))
_ZIP = re.compile(r"(201[7-9]|202[0-2])(0[1-9]|1[0-2])_[0-9]{8,13}_race\.zip\Z")
_CSV = re.compile(r"(201[7-9]|202[0-2])(0[1-9]|1[0-2])_(racelist|horselist|payback)\.csv\Z")
_HOST = "www.keiba.go.jp"
_PATH = "/KeibaWeb/DataDownload/RaceDataDownload"
_FOLDER = r"D:\Development\HorseRacingPredictions\nar-personal"
_MAX_ZIP_BYTES = 400_000_000
_PAUSE_SECONDS = 4


class AcquisitionFailure(Exception):
    """Only static error codes; never print response, source text or paths."""


class OfficialOnlyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        dest = urlsplit(newurl)
        if (dest.scheme != "https" or dest.hostname != _HOST or
                dest.port is not None or dest.path != _PATH or
                dest.username or dest.password or dest.fragment):
            raise AcquisitionFailure("NAR_DOWNLOAD_UNAPPROVED_REDIRECT")
        old = parse_qs(urlsplit(req.full_url).query, strict_parsing=True)
        new = parse_qs(dest.query, strict_parsing=True)
        if old != new:
            raise AcquisitionFailure("NAR_DOWNLOAD_CHANGED_MONTH_REDIRECT")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def official_race_url(month_id: str) -> str:
    if month_id not in _EXPECTED:
        raise AcquisitionFailure("NAR_DOWNLOAD_OUTSIDE_TRAIN_MONTHS")
    return "https://" + _HOST + _PATH + "?" + urlencode({
        "k_month": int(month_id[4:]), "k_year": int(month_id[:4]),
        "type": "monthly",
    })


def _official_name(disposition: str, month: str) -> str:
    if not isinstance(disposition, str) or not 0 < len(disposition) <= 700:
        raise AcquisitionFailure("NAR_DOWNLOAD_OFFICIAL_FILENAME_MISSING")
    header = email.message.Message()
    header["Content-Disposition"] = disposition
    name = header.get_filename()
    if not isinstance(name, str) or not _ZIP.fullmatch(name) or name[:6] != month:
        raise AcquisitionFailure("NAR_DOWNLOAD_OFFICIAL_FILENAME_INVALID")
    return name


def _guard(folder: Path, *, pc2: bool):
    if pc2 and os.environ.get("COMPUTERNAME", "").upper() != "DESKTOP-MVV1FD4":
        raise AcquisitionFailure("NAR_DOWNLOAD_WRONG_PHYSICAL_PC")
    if (not isinstance(folder, Path) or not folder.is_absolute() or
            not folder.is_dir() or folder.is_symlink() or
            any(p.is_symlink() for p in folder.parents)):
        raise AcquisitionFailure("NAR_DOWNLOAD_UNTRUSTED_D_DIRECTORY")
    if pc2:
        if str(folder).lower() != _FOLDER.lower():
            raise AcquisitionFailure("NAR_DOWNLOAD_UNAPPROVED_PRIVATE_DESTINATION")
        if (os.environ.get("GITHUB_ACTIONS") != "true" or
                os.environ.get("GITHUB_REPOSITORY") != "tanaka456jp/HorseRacingPredictions" or
                os.environ.get("GITHUB_REF_NAME") != "feature/weekly-odds-free-note-20261021"):
            raise AcquisitionFailure("NAR_DOWNLOAD_UNTRUSTED_WORKFLOW")
    if len(list(folder.iterdir())) > 1000:
        raise AcquisitionFailure("NAR_DOWNLOAD_TOO_MANY_PRIVATE_FOLDER_ENTRIES")


def _inventory(folder: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in folder.iterdir():
        if path.is_symlink() or path.is_dir():
            raise AcquisitionFailure("NAR_DOWNLOAD_REPARSE_OR_SUBDIRECTORY_PRESENT")
        if path.suffix.lower() != ".zip":
            continue
        if not _ZIP.fullmatch(path.name):
            raise AcquisitionFailure("NAR_DOWNLOAD_UNEXPECTED_ZIP_PRESENT")
        month = path.name[:6]
        if month in found:
            raise AcquisitionFailure("NAR_DOWNLOAD_DUPLICATE_EXISTING_MONTH")
        found[month] = path
    return found


def _zip_verified(path: Path, month: str) -> None:
    try:
        with ZipFile(path) as zf:
            infos = zf.infolist()
            if len(infos) != 3:
                raise AcquisitionFailure("NAR_DOWNLOAD_ARCHIVE_MEMBER_COUNT_INVALID")
            kinds = set()
            total = 0
            for info in infos:
                match = _CSV.fullmatch(info.filename)
                if (not match or match.group(1) + match.group(2) != month or
                        info.flag_bits & 1 or info.is_dir() or
                        info.file_size <= 0 or info.file_size > 16_000_000):
                    raise AcquisitionFailure("NAR_DOWNLOAD_ARCHIVE_MONTH_OR_MEMBER_MISMATCH")
                kinds.add(match.group(3))
                total += info.file_size
            if kinds != {"racelist", "horselist", "payback"} or total > 40_000_000:
                raise AcquisitionFailure("NAR_DOWNLOAD_ARCHIVE_MEMBER_CONTRACT_INVALID")
            if zf.testzip() is not None:
                raise AcquisitionFailure("NAR_DOWNLOAD_ARCHIVE_CRC_INVALID")
    except (BadZipFile, OSError, EOFError, RuntimeError):
        raise AcquisitionFailure("NAR_DOWNLOAD_OFFICIAL_ZIP_VALIDATION_FAILED") from None


def _one(folder: Path, month: str, *, opener) -> None:
    req = Request(official_race_url(month), headers={
        "User-Agent": "HorseRacingPredictions-private-NAR-research/1.0",
        "Accept": "application/zip,application/octet-stream",
    })
    temp = None
    try:
        with opener.open(req, timeout=45) as response:
            actual = urlsplit(response.geturl())
            if (actual.scheme != "https" or actual.hostname != _HOST or
                    actual.path != _PATH or actual.port is not None):
                raise AcquisitionFailure("NAR_DOWNLOAD_UNAPPROVED_FINAL_URL")
            ctype = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if ctype not in ("application/zip", "application/octet-stream",
                             "application/x-zip-compressed"):
                raise AcquisitionFailure("NAR_DOWNLOAD_UNEXPECTED_CONTENT_TYPE")
            filename = _official_name(response.headers.get("Content-Disposition", ""), month)
            size = response.headers.get("Content-Length", "")
            if size and (not size.isdecimal() or int(size) > _MAX_ZIP_BYTES):
                raise AcquisitionFailure("NAR_DOWNLOAD_DECLARED_SIZE_INVALID")
            target = folder / filename
            if target.exists() or target.is_symlink():
                raise AcquisitionFailure("NAR_DOWNLOAD_DESTINATION_EXISTS")
            # Unvalidated data never gets the official ZIP suffix.
            fd, name = tempfile.mkstemp(prefix=".nar_partial_", suffix=".part", dir=str(folder))
            temp = Path(name)
            with os.fdopen(fd, "wb") as sink:
                n = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    n += len(chunk)
                    if n > _MAX_ZIP_BYTES:
                        raise AcquisitionFailure("NAR_DOWNLOAD_STREAM_EXCEEDS_MAX")
                    sink.write(chunk)
                sink.flush()
                os.fsync(sink.fileno())
            if n < 100 or size and n != int(size):
                raise AcquisitionFailure("NAR_DOWNLOAD_INCOMPLETE_STREAM")
            _zip_verified(temp, month)
            # Exclusive same-drive adoption: cannot clobber historical
            # private source on crash, retry or simultaneous manual download.
            os.link(temp, target)
            temp.unlink()
            temp = None
    except HTTPError as exc:
        if exc.code in (403, 429):
            raise AcquisitionFailure("NAR_DOWNLOAD_PROVIDER_DENIED_OR_RATE_LIMITED") from None
        raise AcquisitionFailure("NAR_DOWNLOAD_HTTP_RESPONSE_FAILED") from None
    except (URLError, TimeoutError, OSError):
        raise AcquisitionFailure("NAR_DOWNLOAD_NETWORK_OR_FILESYSTEM_FAILED") from None
    finally:
        if temp is not None:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass


def acquire(folder: Path, *, permission: bool, pc2: bool = True,
            opener=None, sleep=time.sleep, max_downloads: int = 72) -> dict:
    if type(max_downloads) is not int or not 1 <= max_downloads <= 72:
        raise AcquisitionFailure("NAR_DOWNLOAD_BATCH_SIZE_INVALID")
    if permission is not True:
        raise AcquisitionFailure("NAR_DOWNLOAD_EXPLICIT_NAR_PERMISSION_REQUIRED")
    _guard(folder, pc2=pc2)
    initial = _inventory(folder)
    missing = [m for m in _EXPECTED if m not in initial]
    downloaded = 0
    error = ""
    opener = opener if opener is not None else build_opener(OfficialOnlyRedirect())
    for index, month in enumerate(missing[:max_downloads]):
        if index:
            sleep(_PAUSE_SECONDS)
        try:
            _one(folder, month, opener=opener)
            downloaded += 1
        except AcquisitionFailure as exc:
            error = str(exc)
            break
    after = _inventory(folder)
    left = sum(m not in after for m in _EXPECTED)
    return {
        "schema": "NAR.PC2.OfficialMonthlyAcquisition.v1",
        "status": ("ALL_72_MONTHS_LOCALLY_PRESENT_VALIDATION_SEPARATE"
                   if not left else "INCOMPLETE_OFFICIAL_ACQUISITION_HOLD"),
        "sourceMonthsInitiallyPresent": len(initial),
        "sourceMonthsInitiallyMissing": len(missing),
        "newOfficialZipsValidated": downloaded,
        "monthsStillMissing": left,
        "staticStopReason": error,
        "privateDataUploaded": False,
        "sourceRecordsPrinted": False,
        "protectedOosRead": False,
        "trainingPerformed": False,
        "positiveEvDemonstrated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-nar-private-monthly-acquisition-authorized", action="store_true")
    parser.add_argument("--max-downloads", type=int, choices=range(1, 73), default=72)
    args = parser.parse_args()
    try:
        data = acquire(Path(_FOLDER), permission=args.confirm_nar_private_monthly_acquisition_authorized,
                       max_downloads=args.max_downloads)
    except (AcquisitionFailure, OSError, ValueError):
        print(json.dumps({
            "schema": "NAR.PC2.OfficialMonthlyAcquisition.v1",
            "status": "UNSAFE_ACQUISITION_BLOCKED", "privateDataUploaded": False,
            "positiveEvDemonstrated": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(data, sort_keys=True, allow_nan=False))
    return 0 if data["monthsStillMissing"] == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
