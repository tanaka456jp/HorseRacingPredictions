from horse_racing_predictions.jravan import JvLinkClient
from horse_racing_predictions.jravan_doctor import (
    run_jravan_doctor,
)


class FakeJvLink:
    def __init__(
        self,
        *,
        init_code=0,
        open_code=0,
        records=None,
        status_code=-203,
    ):
        self.init_code = init_code
        self.open_code = open_code
        self.records = list(records or [])
        self.status_code = status_code
        self.closed = 0

    def JVInit(self, sid):
        self.sid = sid
        return self.init_code

    def JVStatus(self):
        return self.status_code

    def JVOpen(
        self,
        dataspec,
        from_time,
        option,
        read_count,
        download_count,
        last_time,
    ):
        return (
            self.open_code,
            len(self.records),
            0,
            "20260926120000",
        )

    def JVGets(self, buff, size, fname):
        if not self.records:
            return (0, memoryview(b""), b"")
        text = self.records.pop(0)
        raw = text.encode("cp932")
        return (
            len(raw),
            memoryview(raw),
            b"sample.jvd",
        )

    def JVClose(self):
        self.closed += 1
        return 0


def _client(fake):
    return JvLinkClient(
        jvlink=fake,
        application_id="UNKNOWN",
        sleep_fn=lambda _: None,
    )


def test_doctor_marks_ra_se_connectivity_ready():
    fake = FakeJvLink(
        records=["RAabc", "SEdef", "HRghi"],
    )
    report = run_jravan_doctor(
        client=_client(fake),
        max_records=10,
    )

    assert report.ready
    assert report.initialized
    assert report.from_time == "00000000000000"
    assert report.option == 2
    assert report.status_before_open == -203
    assert report.ra_records == 1
    assert report.se_records == 1
    assert report.record_type_counts["HR"] == 1
    assert any(
        "expected" in message
        for message in report.guidance
    )
    assert fake.closed == 1


def test_doctor_classifies_authentication_error():
    fake = FakeJvLink(open_code=-301)
    report = run_jravan_doctor(
        client=_client(fake),
    )

    assert not report.ready
    assert report.status == "blocked"
    assert any(
        "Authentication error" in message
        for message in report.guidance
    )


def test_doctor_classifies_missing_key_error():
    fake = FakeJvLink(open_code=-303)
    report = run_jravan_doctor(
        client=_client(fake),
    )

    assert not report.ready
    assert any(
        "No usage key" in message
        for message in report.guidance
    )


def test_doctor_reports_connected_without_ra_se():
    fake = FakeJvLink(
        records=["HRabc", "JGdef"],
    )
    report = run_jravan_doctor(
        client=_client(fake),
        max_records=10,
    )

    assert report.status == "connected_no_ra_se"
    assert report.ready
    assert report.sample_records == 2


def test_doctor_accepts_successful_empty_open_as_connected():
    fake = FakeJvLink(records=[])
    report = run_jravan_doctor(
        client=_client(fake),
        max_records=10,
    )

    assert report.status == "connected_no_records"
    assert report.ready
    assert report.open_return_code == 0
