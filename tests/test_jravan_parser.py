import json

from horse_racing_predictions.jravan_parser import (
    parse_ra,
    parse_raw_jsonl,
    parse_se,
)


def _put(buffer, position, length, value, encoding="ascii"):
    raw = str(value).encode(encoding)
    assert len(raw) <= length
    start = position - 1
    buffer[start:start + length] = (
        raw + b" " * (length - len(raw))
    )


def _ra(
    *,
    data_division="7",
    course="08",
    grade="A",
    condition="999",
    track="17",
):
    buffer = bytearray(b" " * 1270)
    _put(buffer, 1, 2, "RA")
    _put(buffer, 3, 1, data_division)
    _put(buffer, 4, 8, "20260926")
    _put(buffer, 12, 4, "2026")
    _put(buffer, 16, 4, "0926")
    _put(buffer, 20, 2, course)
    _put(buffer, 22, 2, "03")
    _put(buffer, 24, 2, "04")
    _put(buffer, 26, 2, "11")
    _put(buffer, 615, 1, grade)
    _put(buffer, 635, 3, condition)
    _put(buffer, 698, 4, "1600")
    _put(buffer, 706, 2, track)
    _put(buffer, 888, 1, "1")
    _put(buffer, 889, 1, "1")
    _put(buffer, 890, 1, "2")
    return bytes(buffer).decode("cp932")


def _se(
    horse_number,
    horse_name,
    finish,
    odds,
    *,
    data_division="7",
    blood_no="2023100001",
):
    buffer = bytearray(b" " * 553)
    _put(buffer, 1, 2, "SE")
    _put(buffer, 3, 1, data_division)
    _put(buffer, 4, 8, "20260926")
    _put(buffer, 12, 4, "2026")
    _put(buffer, 16, 4, "0926")
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
    _put(buffer, 325, 3, "480")
    _put(buffer, 328, 1, "+")
    _put(buffer, 329, 3, "006")
    _put(buffer, 332, 1, "0")
    _put(buffer, 335, 2, f"{finish:02d}")
    _put(buffer, 352, 2, "02")
    _put(buffer, 354, 2, "02")
    _put(buffer, 356, 2, "01")
    _put(buffer, 358, 2, "01")
    _put(buffer, 360, 4, f"{odds:04d}")
    _put(buffer, 364, 2, f"{horse_number:02d}")
    _put(buffer, 391, 3, "345")
    return bytes(buffer).decode("cp932")


def test_parse_ra_uses_official_fixed_width_positions():
    record = parse_ra(_ra())
    assert record.race_id == "20260926-08-03-04-11"
    assert record.race_date == "2026-09-26"
    assert record.racecourse == "京都"
    assert record.distance_m == 1600
    assert record.surface == "芝"
    assert record.weather == "晴"
    assert record.track_condition == "良"
    assert record.graded_race == "G1"
    assert record.race_class == "オープン"


def test_parse_se_uses_official_fixed_width_positions():
    record = parse_se(
        _se(
            5,
            "テストホース",
            1,
            250,
        )
    )
    assert record.post_position == 5
    assert record.horse_name == "テストホース"
    assert record.sex == "牡"
    assert record.age == 3
    assert record.carried_weight == 57.0
    assert record.horse_weight == 480
    assert record.horse_weight_delta == 6
    assert record.finish_position == 1
    assert record.corner_1 == 2
    assert record.corner_4 == 1
    assert record.win_odds == 25.0
    assert record.last_3f == 34.5


def test_raw_jsonl_prefers_final_records_and_outputs_canonical_history(
    tmp_path,
):
    path = tmp_path / "raw.jsonl"
    rows = [
        {"record_type": "RA", "text": _ra(data_division="3")},
        {"record_type": "RA", "text": _ra(data_division="7")},
        {
            "record_type": "SE",
            "text": _se(
                1,
                "アルファ",
                1,
                250,
                data_division="5",
                blood_no="2023100001",
            ),
        },
        {
            "record_type": "SE",
            "text": _se(
                1,
                "アルファ",
                1,
                220,
                data_division="7",
                blood_no="2023100001",
            ),
        },
        {
            "record_type": "SE",
            "text": _se(
                2,
                "ブラボー",
                2,
                340,
                data_division="7",
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

    frame, report = parse_raw_jsonl(path)

    assert len(frame) == 2
    assert report.output_races == 1
    assert report.selected_ra_records == 1
    assert report.selected_se_records == 2

    winner = frame.loc[
        frame["finish_position"] == 1
    ].iloc[0]
    assert winner["horse_name"] == "アルファ"
    assert winner["win_odds"] == 22.0
    assert winner["racecourse"] == "京都"
    assert winner["surface"] == "芝"
    assert winner["race_class"] == "オープン"
    assert winner["graded_race"] == "G1"


def test_non_jra_and_incomplete_rows_are_fail_safe_filtered(tmp_path):
    path = tmp_path / "raw.jsonl"
    local_ra = _ra(course="44")
    incomplete = _se(
        1,
        "取消馬",
        1,
        0,
    )
    rows = [
        {"record_type": "RA", "text": local_ra},
        {"record_type": "RA", "text": _ra()},
        {"record_type": "SE", "text": incomplete},
    ]
    path.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False)
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )

    frame, report = parse_raw_jsonl(path)

    assert frame.empty
    assert report.skipped_non_jra_ra == 1
    assert report.skipped_incomplete_se == 1


def test_incomplete_current_week_records_can_be_parsed_for_smoke(tmp_path):
    path = tmp_path / "raw.jsonl"
    rows = [
        {"record_type": "RA", "text": _ra(data_division="3")},
        {
            "record_type": "SE",
            "text": _se(
                1,
                "未確定馬",
                0,
                0,
                data_division="3",
                blood_no="2023100099",
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

    strict_frame, strict_report = parse_raw_jsonl(
        path,
        completed_only=True,
    )
    smoke_frame, smoke_report = parse_raw_jsonl(
        path,
        completed_only=False,
    )

    assert strict_frame.empty
    assert strict_report.skipped_incomplete_se == 1
    assert len(smoke_frame) == 1
    assert smoke_report.output_races == 1
    assert smoke_frame.iloc[0]["horse_name"] == "未確定馬"
