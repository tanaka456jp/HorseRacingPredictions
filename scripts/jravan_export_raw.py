import argparse

from horse_racing_predictions.jravan import (
    JvLinkClient,
    export_race_raw,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export JRA-VAN JV-Link RACE records to local JSONL. "
            "Windows/JV-Link only; raw output is not for redistribution."
        )
    )
    parser.add_argument(
        "--from-time",
        default="20210801000000",
        help="JVOpen data-provision timestamp YYYYMMDDhhmmss.",
    )
    parser.add_argument(
        "--option",
        type=int,
        choices=(1, 2, 3, 4),
        default=4,
    )
    parser.add_argument(
        "--output",
        default="data/jravan/race_raw.jsonl",
    )
    parser.add_argument(
        "--summary",
        default="artifacts/jravan_race_raw_summary.json",
    )
    parser.add_argument(
        "--record-types",
        help="Comma-separated record IDs such as RA,SE,HR,O1.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional read limit for a smoke run.",
    )
    parser.add_argument(
        "--open-settings",
        action="store_true",
        help="Open JV-Link settings UI and exit.",
    )
    args = parser.parse_args()

    record_types = None
    if args.record_types:
        record_types = {
            value.strip().upper()
            for value in args.record_types.split(",")
            if value.strip()
        }

    client = JvLinkClient()
    if args.open_settings:
        try:
            client.initialize()
            result = client.open_settings()
            print(f"JVSetUIProperties={result}")
            status = client.status()
            if status is not None:
                print(f"JVStatus={status}")
        finally:
            client.close()
        return

    summary = export_race_raw(
        output_path=args.output,
        summary_path=args.summary,
        from_time=args.from_time,
        option=args.option,
        record_types=record_types,
        max_records=args.max_records,
        client=client,
    )
    print(f"records={summary.records_written}")
    print(
        "record_types="
        + ",".join(
            f"{key}:{value}"
            for key, value in summary.record_type_counts.items()
        )
    )
    print(
        "last_file_timestamp="
        + summary.open_result.last_file_timestamp
    )
    print(f"sha256={summary.output_sha256}")


if __name__ == "__main__":
    main()
