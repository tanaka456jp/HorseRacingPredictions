import json

import pytest

from horse_racing_predictions.jravan import (
    JraVanApiError,
    JvLinkClient,
    export_race_raw,
)


class FakeJvLink:
    def __init__(
        self,
        records=None,
        init_code=0,
        open_result=(0, 3, 1, "20260926123456"),
        status_values=None,
    ):
        self.records = list(records or [])
        self.init_code = init_code
        self.open_result = open_result
        self.status_values = list(status_values or [])
        self.closed = 0
        self.open_args = None

    def JVInit(self, app_id):
        self.app_id = app_id
        return self.init_code

    def JVSetUIProperties(self):
        return 0

    def JVStatus(self):
        if self.status_values:
            if len(self.status_values) == 1:
                return self.status_values[0]
            return self.status_values.pop(0)
        return int(self.open_result[2] or 0)

    def JVOpen(
        self,
        dataspec,
        from_time,
        option,
        read_count,
        download_count,
        timestamp,
    ):
        self.open_args = (
            dataspec,
            from_time,
            option,
            read_count,
            download_count,
            timestamp,
        )
        return self.open_result

    def JVGets(self, buff, size, fname):
        if not self.records:
            return (0, memoryview(b""), b"")
        value = self.records.pop(0)
        if isinstance(value, int):
            return (value, memoryview(b""), b"")
        text, file_name = value
        raw = text.encode("cp932")
        return (
            len(raw),
            memoryview(raw),
            file_name.encode("cp932"),
        )

    def JVClose(self):
        self.closed += 1
        return 0


def test_jvlink_open_uses_race_dataspec_and_tuple_result():
    fake = FakeJvLink()
    client = JvLinkClient(jvlink=fake)
    client.initialize()
    result = client.open_race(
        from_time="20210801000000",
        option=4,
    )

    assert result.return_code == 0
    assert result.read_count == 3
    assert result.download_count == 1
    assert result.last_file_timestamp == "20260926123456"
    assert fake.open_args[0] == "RACE"
    assert fake.open_args[1] == "20210801000000"
    assert fake.open_args[2] == 4




def test_wait_for_downloads_follows_jvstatus_until_complete():
    fake = FakeJvLink(
        open_result=(0, 3, 3, "20260926123456"),
        status_values=[0, 1, 3],
    )
    sleeps = []
    client = JvLinkClient(
        jvlink=fake,
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )
    client.initialize()
    result = client.open_race(
        from_time="20210801000000",
        option=4,
    )

    status = client.wait_for_downloads(
        result,
        max_polls=10,
        poll_seconds=0.1,
    )

    assert status == 3
    assert sleeps == [0.1, 0.1]


def test_wait_for_downloads_fails_closed_on_download_error():
    fake = FakeJvLink(
        open_result=(0, 3, 3, "20260926123456"),
        status_values=[-502],
    )
    client = JvLinkClient(
        jvlink=fake,
        sleep_fn=lambda _: None,
    )
    client.initialize()
    result = client.open_race(
        from_time="20210801000000",
        option=4,
    )

    with pytest.raises(JraVanApiError, match="download failure"):
        client.wait_for_downloads(result)


def test_jvlink_iter_records_handles_file_boundary_and_wait():
    fake = FakeJvLink(records=[
        ("RA12345", "race.jvd"),
        -1,
        -3,
        ("SE67890", "horse.jvd"),
    ])
    sleeps = []
    client = JvLinkClient(
        jvlink=fake,
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )
    client.initialize()
    client.open_race(
        from_time="20210801000000",
        option=4,
    )

    records = list(client.iter_records())

    assert [r.record_type for r in records] == ["RA", "SE"]
    assert records[0].text == "RA12345"
    assert records[1].file_name == "horse.jvd"
    assert sleeps == [0.2]


def test_jvlink_init_and_open_fail_closed():
    with pytest.raises(JraVanApiError, match="JVInit failed"):
        JvLinkClient(
            jvlink=FakeJvLink(init_code=-101)
        ).initialize()

    fake = FakeJvLink(open_result=(-111, 0, 0, ""))
    client = JvLinkClient(jvlink=fake)
    client.initialize()
    with pytest.raises(JraVanApiError, match="JVOpen failed"):
        client.open_race(
            from_time="20210801000000",
            option=4,
        )


def test_raw_export_writes_jsonl_summary_and_closes(tmp_path):
    fake = FakeJvLink(records=[
        ("RAaaaa", "a.jvd"),
        ("SEbbbb", "b.jvd"),
        ("HRcccc", "c.jvd"),
    ])
    client = JvLinkClient(jvlink=fake)

    summary = export_race_raw(
        output_path=tmp_path / "raw.jsonl",
        summary_path=tmp_path / "summary.json",
        from_time="20210801000000",
        option=4,
        record_types={"RA", "SE"},
        client=client,
    )

    assert summary.records_written == 2
    assert summary.record_type_counts == {
        "RA": 1,
        "SE": 1,
    }
    assert len(summary.output_sha256) == 64
    assert fake.closed == 1

    rows = [
        json.loads(line)
        for line in (
            tmp_path / "raw.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    assert [row["record_type"] for row in rows] == [
        "RA",
        "SE",
    ]

    saved = json.loads(
        (tmp_path / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["raw_redistribution_allowed"] is False


def test_close_releases_com_before_couninitialize():
    events = []

    class ReleasableJvLink:
        def __del__(self):
            events.append("release")

    class Runtime:
        def CoUninitialize(self):
            events.append("uninit")

    def factory():
        return ReleasableJvLink(), Runtime()

    client = JvLinkClient(com_factory=factory)
    client.close()

    assert events == ["release", "uninit"]
