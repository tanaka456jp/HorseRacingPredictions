import json
from datetime import datetime

from horse_racing_predictions.jravan import JvRawRecord
from horse_racing_predictions.jravan_forward import (
    JST,
    build_future_entries_from_current_week,
    capture_complete_win_odds,
    parse_o1_win_odds,
)


def _put(buffer, position, length, value, encoding="ascii"):
    raw = str(value).encode(encoding)
    assert len(raw) <= length
    start = position - 1
    buffer[start:start + length] = (
        raw + b" " * (length - len(raw))
    )


def _ra(*, hhmm="1000", data_division="3"):
    buffer = bytearray(b" " * 1270)
    _put(buffer, 1, 2, "RA")
    _put(buffer, 3, 1, data_division)
    _put(buffer, 4, 8, "20260927")
    _put(buffer, 12, 4, "2026")
    _put(buffer, 16, 4, "0927")
    _put(buffer, 20, 2, "08")
    _put(buffer, 22, 2, "03")
    _put(buffer, 24, 2, "04")
    _put(buffer, 26, 2, "11")
    _put(buffer, 615, 1, "A")
    _put(buffer, 635, 3, "999")
    _put(buffer, 698, 4, "1600")
    _put(buffer, 706, 2, "17")
    _put(buffer, 874, 4, hhmm)
    _put(buffer, 882, 2, "02")
    _put(buffer, 888, 1, "1")
    _put(buffer, 889, 1, "1")
    _put(buffer, 890, 1, "2")
    return bytes(buffer).decode("cp932")


def _se(
    horse_number,
    horse_name,
    *,
    blood_no,
    data_division="3",
    abnormal="0",
):
    buffer = bytearray(b" " * 553)
    _put(buffer, 1, 2, "SE")
    _put(buffer, 3, 1, data_division)
    _put(buffer, 4, 8, "20260927")
    _put(buffer, 12, 4, "2026")
    _put(buffer, 16, 4, "0927")
    _put(buffer, 20, 2, "08")
    _put(buffer, 22, 2, "03")
    _put(buffer, 24, 2, "04")
    _put(buffer, 26, 2, "11")
    _put(buffer, 29, 2, f"{horse_number:02d}")
    _put(buffer, 31, 10, blood_no)
    _put(buffer, 41, 36, horse_name, "cp932")
    _put(buffer, 79, 1, "1")
    _put(buffer, 83, 2, "03")
    _put(buffer, 91, 8, "調教A", "cp932")
    _put(buffer, 289, 3, "570")
    _put(buffer, 307, 8, "騎手A", "cp932")
    _put(buffer, 332, 1, abnormal)
    return bytes(buffer).decode("cp932")


def _o1(*, include_second=True, data_division="1"):
    buffer = bytearray(b" " * 267)
    _put(buffer, 1, 2, "O1")
    _put(buffer, 3, 1, data_division)
    _put(buffer, 4, 8, "20260927")
    _put(buffer, 12, 4, "2026")
    _put(buffer, 16, 4, "0927")
    _put(buffer, 20, 2, "08")
    _put(buffer, 22, 2, "03")
    _put(buffer, 24, 2, "04")
    _put(buffer, 26, 2, "11")
    _put(buffer, 28, 8, "09270900")
    _put(buffer, 36, 2, "02")
    _put(buffer, 38, 2, "02")
    _put(buffer, 40, 1, "1")
    _put(buffer, 44, 2, "01")
    _put(buffer, 46, 4, "0250")
    _put(buffer, 50, 2, "01")
    if include_second:
        _put(buffer, 52, 2, "02")
        _put(buffer, 54, 4, "0340")
        _put(buffer, 58, 2, "02")
    return bytes(buffer).decode("cp932")


def _write_raw(path):
    rows = [
        {"record_type": "RA", "text": _ra()},
        {
            "record_type": "SE",
            "text": _se(
                1,
                "アルファ",
                blood_no="2023100001",
            ),
        },
        {
            "record_type": "SE",
            "text": _se(
                2,
                "ブラボー",
                blood_no="2023100002",
            ),
        },
    ]
    path.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False)
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_future_entries_uses_scheduled_post_time(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(raw_path)

    entries, schedules, counts = build_future_entries_from_current_week(
        raw_path,
        history_cutoff="2026-09-22",
        now=datetime(2026, 9, 27, 8, 0, tzinfo=JST),
        min_lead_minutes=10,
    )

    assert len(entries) == 2
    assert entries["race_id"].nunique() == 1
    assert set(entries["horse_name"]) == {"アルファ", "ブラボー"}
    assert (
        schedules["20260927-08-03-04-11"]
        .scheduled_post_time.isoformat()
        == "2026-09-27T10:00:00+09:00"
    )
    assert counts["current_week_rows"] == 2


def test_parse_o1_win_odds_reads_single_win_market():
    record = parse_o1_win_odds(_o1())

    assert record.race_id == "20260927-08-03-04-11"
    assert record.data_division == "1"
    assert record.published_mmddhhmm == "09270900"
    assert record.registered_count == 2
    assert record.runner_count == 2
    assert len(record.items) == 2
    assert record.items[0].post_position == 1
    assert record.items[0].decimal_odds == 25.0
    assert record.items[1].post_position == 2
    assert record.items[1].decimal_odds == 34.0


class FakeRealtimeClient:
    def __init__(self, text):
        self.text = text
        self.initialized = False
        self.opened = False
        self.open_args = None

    def initialize(self):
        self.initialized = True

    def open_realtime(self, *, dataspec, key):
        self.open_args = (dataspec, key)
        self.opened = True
        return 0

    def iter_records(self):
        yield JvRawRecord(
            record_type="O1",
            text=self.text,
            file_name="",
        )

    def close(self):
        self.opened = False


def test_complete_odds_capture_requires_every_entry(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(raw_path)
    now = datetime(2026, 9, 27, 8, 0, tzinfo=JST)
    entries, schedules, _ = build_future_entries_from_current_week(
        raw_path,
        history_cutoff="2026-09-22",
        now=now,
        min_lead_minutes=10,
    )

    complete, skipped = capture_complete_win_odds(
        entries,
        schedules,
        min_lead_minutes=10,
        client_factory=lambda: FakeRealtimeClient(_o1()),
        now_fn=lambda: now,
    )

    assert skipped == 0
    assert len(complete) == 2
    assert set(complete["horse_id"]) == {
        "20260927-08-03-04-11-1",
        "20260927-08-03-04-11-2",
    }

    incomplete, skipped = capture_complete_win_odds(
        entries,
        schedules,
        min_lead_minutes=10,
        client_factory=lambda: FakeRealtimeClient(
            _o1(include_second=False)
        ),
        now_fn=lambda: now,
    )

    assert incomplete.empty
    assert skipped == 1
