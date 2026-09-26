import argparse

from horse_racing_predictions.jravan_runtime import (
    inspect_jravan_runtime,
    write_runtime_report,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="artifacts/jravan_runtime.json",
    )
    args = parser.parse_args()

    report = inspect_jravan_runtime()
    write_runtime_report(report, args.output)

    print(
        f"Python={report.python_version} "
        f"bits={report.python_bits}"
    )
    print(
        "JV-Link registry: "
        f"64bit={report.registered_64bit} "
        f"32bit={report.registered_32bit}"
    )
    if report.com_created:
        print("JV-Link COM=OK")
    else:
        print(
            "JV-Link COM is not registered or cannot be created: "
            f"{report.error}"
        )
    for message in report.guidance:
        print(f"GUIDANCE: {message}")

    if report.status != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
