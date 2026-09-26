from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import gc
import json
import platform
from pathlib import Path
import time
from typing import Callable, Iterable


class JraVanUnavailableError(RuntimeError):
    pass


class JraVanApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class JvOpenResult:
    return_code: int
    read_count: int
    download_count: int
    last_file_timestamp: str


@dataclass(frozen=True)
class JvRawRecord:
    record_type: str
    text: str
    file_name: str = ""


@dataclass(frozen=True)
class JvExportSummary:
    dataspec: str
    from_time: str
    option: int
    open_result: JvOpenResult
    records_written: int
    record_type_counts: dict[str, int]
    output_sha256: str
    output_path: str
    raw_redistribution_allowed: bool = False


def _normalize_open_result(value) -> JvOpenResult:
    if isinstance(value, (tuple, list)):
        if not value:
            raise JraVanApiError("JVOpen returned an empty tuple")
        parts = list(value) + [0, 0, ""]
        return JvOpenResult(
            return_code=int(parts[0]),
            read_count=int(parts[1] or 0),
            download_count=int(parts[2] or 0),
            last_file_timestamp=str(parts[3] or ""),
        )
    return JvOpenResult(
        return_code=int(value),
        read_count=0,
        download_count=0,
        last_file_timestamp="",
    )


def _file_name_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode(
            "cp932",
            errors="replace",
        ).rstrip("\x00")
    return str(value)


def _record_text(memview, record_length: int) -> str:
    if isinstance(memview, memoryview):
        raw = memview.tobytes()
    elif isinstance(memview, (bytes, bytearray)):
        raw = bytes(memview)
    else:
        raw = bytes(memview)

    if record_length > 0 and len(raw) >= record_length:
        raw = raw[:record_length]
    return raw.decode(
        "cp932",
        errors="replace",
    ).rstrip("\x00\r\n")


def _default_com_factory():
    if platform.system() != "Windows":
        raise JraVanUnavailableError(
            "JV-Link requires Windows and cannot run on this platform"
        )

    try:
        import pythoncom
        import win32com.client.dynamic
    except ImportError as exc:
        raise JraVanUnavailableError(
            "JV-Link requires pywin32. Install requirements-jravan.txt."
        ) from exc

    pythoncom.CoInitialize()
    try:
        jv = win32com.client.dynamic.Dispatch(
            "JVDTLab.JVLink"
        )
    except Exception:
        pythoncom.CoUninitialize()
        raise
    return jv, pythoncom


class JvLinkClient:
    def __init__(
        self,
        *,
        jvlink=None,
        com_factory: Callable | None = None,
        application_id: str = "UNKNOWN",
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.application_id = application_id
        self.sleep_fn = sleep_fn
        self._runtime = None
        self._owns_runtime = jvlink is None

        if jvlink is not None:
            self.jvlink = jvlink
        else:
            factory = com_factory or _default_com_factory
            created = factory()
            if isinstance(created, tuple) and len(created) == 2:
                self.jvlink, self._runtime = created
            else:
                self.jvlink = created

        self.initialized = False
        self.opened = False

    def initialize(self) -> None:
        result = int(self.jvlink.JVInit(self.application_id))
        if result != 0:
            raise JraVanApiError(
                f"JVInit failed with return code {result}"
            )
        self.initialized = True

    def open_settings(self) -> int:
        if not self.initialized:
            self.initialize()
        return int(self.jvlink.JVSetUIProperties())

    def status(self) -> int | None:
        method = getattr(self.jvlink, "JVStatus", None)
        if method is None:
            return None
        return int(method())

    def open_race(
        self,
        *,
        from_time: str,
        option: int = 4,
    ) -> JvOpenResult:
        if not self.initialized:
            self.initialize()
        if len(from_time) != 14 or not from_time.isdigit():
            raise ValueError(
                "from_time must be YYYYMMDDhhmmss (14 digits)"
            )
        if option not in (1, 2, 3, 4):
            raise ValueError("option must be 1, 2, 3 or 4")

        result = _normalize_open_result(
            self.jvlink.JVOpen(
                "RACE",
                from_time,
                int(option),
                0,
                0,
                "",
            )
        )
        if result.return_code < 0:
            raise JraVanApiError(
                "JVOpen failed with return code "
                f"{result.return_code}"
            )
        self.opened = True
        return result

    def open_realtime(
        self,
        *,
        dataspec: str,
        key: str,
    ) -> int:
        if not self.initialized:
            self.initialize()
        if len(dataspec) != 4:
            raise ValueError("realtime dataspec must be exactly 4 characters")
        if len(key) not in (8, 12, 16) or not key.isdigit():
            raise ValueError(
                "realtime key must be YYYYMMDD, YYYYMMDDJJRR, "
                "or YYYYMMDDJJKKHHRR digits"
            )

        result = int(self.jvlink.JVRTOpen(dataspec, key))
        if result < 0:
            raise JraVanApiError(
                "JVRTOpen failed with return code "
                f"{result} for dataspec={dataspec} key={key}"
            )
        self.opened = True
        return result

    def wait_for_downloads(
        self,
        open_result: JvOpenResult,
        *,
        max_polls: int = 7200,
        poll_seconds: float = 0.5,
        progress_callback: Callable[[str], None] | None = None,
        progress_every_polls: int = 20,
    ) -> int | None:
        if open_result.download_count <= 0:
            return 0
        if max_polls < 1:
            raise ValueError("max_polls must be positive")
        if progress_every_polls < 1:
            raise ValueError("progress_every_polls must be positive")

        last_status = None
        expected = open_result.download_count

        for poll_index in range(max_polls):
            status = self.status()
            if (
                progress_callback is not None
                and (
                    status != last_status
                    or poll_index % progress_every_polls == 0
                )
            ):
                shown = 0 if status in (None, -203) else max(status, 0)
                progress_callback(
                    f"download_progress={shown}/{expected} "
                    f"poll={poll_index + 1}"
                )
            last_status = status
            if status is None:
                return None
            if status >= open_result.download_count:
                return status
            if status == -502:
                raise JraVanApiError(
                    "JVStatus reported download failure (-502)"
                )
            if status < 0 and status != -203:
                raise JraVanApiError(
                    f"JVStatus failed with return code {status}"
                )
            self.sleep_fn(poll_seconds)

        raise JraVanApiError(
            "JV-Link download did not finish before the wait limit: "
            f"expected={open_result.download_count}"
        )

    def iter_records(
        self,
        *,
        buffer_size: int = 150_000,
        wait_retries: int = 300,
        wait_seconds: float = 0.2,
    ) -> Iterable[JvRawRecord]:
        if not self.opened:
            raise RuntimeError(
                "JVOpen must succeed before reading records"
            )
        if buffer_size < 1:
            raise ValueError("buffer_size must be positive")

        wait_count = 0
        while True:
            result = self.jvlink.JVGets(
                bytearray(),
                int(buffer_size),
                bytearray(),
            )
            if not isinstance(result, (tuple, list)):
                raise JraVanApiError(
                    "JVGets returned an unexpected value"
                )
            if len(result) < 2:
                raise JraVanApiError(
                    "JVGets returned too few values"
                )

            return_code = int(result[0])
            if return_code > 0:
                wait_count = 0
                text = _record_text(
                    result[1],
                    return_code,
                )
                file_name = _file_name_text(
                    result[2] if len(result) > 2 else ""
                )
                yield JvRawRecord(
                    record_type=text[:2],
                    text=text,
                    file_name=file_name,
                )
                continue

            if return_code == 0:
                break
            if return_code == -1:
                continue
            if return_code == -3:
                wait_count += 1
                if wait_count > wait_retries:
                    raise JraVanApiError(
                        "JVGets remained in wait state (-3) "
                        f"for more than {wait_retries} retries"
                    )
                self.sleep_fn(wait_seconds)
                continue

            raise JraVanApiError(
                f"JVGets failed with return code {return_code}"
            )

    def close(self) -> None:
        try:
            if self.opened and self.jvlink is not None:
                self.jvlink.JVClose()
        finally:
            self.opened = False
            if self._owns_runtime and self._runtime is not None:
                # Release the COM object before leaving the COM apartment.
                # Otherwise pywin32 may emit:
                # "Win32 exception occurred releasing IUnknown".
                self.jvlink = None
                gc.collect()

                uninit = getattr(
                    self._runtime,
                    "CoUninitialize",
                    None,
                )
                if uninit is not None:
                    uninit()
                self._runtime = None


def export_race_raw(
    *,
    output_path: str | Path,
    summary_path: str | Path,
    from_time: str,
    option: int = 4,
    record_types: set[str] | None = None,
    max_records: int | None = None,
    client: JvLinkClient | None = None,
    download_wait_polls: int = 7200,
    download_poll_seconds: float = 0.5,
    progress_callback: Callable[[str], None] | None = None,
    record_progress_every: int = 5000,
) -> JvExportSummary:
    if max_records is not None and max_records < 1:
        raise ValueError("max_records must be positive")
    if record_progress_every < 1:
        raise ValueError("record_progress_every must be positive")

    output_path = Path(output_path)
    summary_path = Path(summary_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    own_client = client is None
    client = client or JvLinkClient()
    counts: Counter[str] = Counter()
    written = 0

    try:
        if not client.initialized:
            client.initialize()

        open_result = client.open_race(
            from_time=from_time,
            option=option,
        )
        if progress_callback is not None:
            progress_callback(
                "jvopen_ok "
                f"from_time={from_time} option={option} "
                f"read_count={open_result.read_count} "
                f"download_count={open_result.download_count}"
            )
        client.wait_for_downloads(
            open_result,
            max_polls=download_wait_polls,
            poll_seconds=download_poll_seconds,
            progress_callback=progress_callback,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            for record in client.iter_records():
                if (
                    record_types is not None
                    and record.record_type not in record_types
                ):
                    continue

                handle.write(
                    json.dumps(
                        asdict(record),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                counts[record.record_type] += 1
                written += 1

                if (
                    progress_callback is not None
                    and written % record_progress_every == 0
                ):
                    progress_callback(
                        f"record_progress={written}"
                    )

                if (
                    max_records is not None
                    and written >= max_records
                ):
                    break
    finally:
        if client.opened:
            client.close()
        elif own_client:
            client.close()

    if progress_callback is not None:
        progress_callback(
            f"record_progress={written} complete"
        )

    digest = hashlib.sha256(
        output_path.read_bytes()
    ).hexdigest()

    summary = JvExportSummary(
        dataspec="RACE",
        from_time=from_time,
        option=option,
        open_result=open_result,
        records_written=written,
        record_type_counts=dict(sorted(counts.items())),
        output_sha256=digest,
        output_path=str(output_path),
        raw_redistribution_allowed=False,
    )
    summary_path.write_text(
        json.dumps(
            asdict(summary),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary
