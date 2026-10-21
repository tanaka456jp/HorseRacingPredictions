"""Offline, review-only handoff for a JRA Friday note article.

The input is an already curated and approved point-in-time JRA forecast
document, NOT an odds feed. Does not perform network acquisition, pay, place
bets, create note articles, or approve an external source. Emits conservative
authorization blockers for the separate note publishing application.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from horse_racing_predictions.odds_free_friday_article import (
    ForecastInputError,
    render_friday_jra_article,
)


def _write_atomic(path: Path, text: str) -> None:
    import os
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n",
        dir=path.parent, prefix=".jra-friday-", suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        name = handle.name
    try:
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def render_handoff(input_path: Path, output_dir: Path) -> tuple[Path, Path]:
    raw = input_path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("Friday article input is too large")
    document = json.loads(raw)
    article = render_friday_jra_article(document)
    issue = document["issue_date"]
    episode = issue.replace("-", "")
    if not output_dir.is_dir():
        raise ValueError("existing local output directory required")
    article_path = output_dir / (episode + ".md")
    receipt_path = output_dir / (episode + ".handoff.json")
    if article_path.exists() or receipt_path.exists():
        raise ValueError("Friday edition already exists; never silently overwrite")

    receipt = {
        "schemaVersion": 1,
        "seriesId": "jra-weekly-top3-oddsfree",
        "issueDate": issue,
        "episodeId": episode,
        "generatedAt": document["generated_at"],
        "modelId": document["model_id"],
        "raceCount": len(document["races"]),
        "outsiderPerRace": 1,
        "outsiderPolicy": "independent_pre_market_condition_upside_outside_top3",
        "articleSha256": sha256(article.encode("utf-8")).hexdigest(),
        "sourceManifestSha256": sha256(raw).hexdigest(),
        "jraOnly": True,
        "syntheticOnly": True,
        "sourceRightsIndependentlyVerified": False,
        "fullWeekendManifestVerified": False,
        "frozenOddsFreeModelVerified": False,
        "realHorseIdentityVerified": False,
        "pointInTimeFeatureGatePassed": False,
        "status": "REVIEW_REQUIRED_NOT_APPROVED_FOR_AUTOPUBLISH",
        "disposition": (
            "Independent source-rights, horse IDs, full JRA race manifest, "
            "frozen non-odds model and publication proof needed separately. "
            "Never treat self-attested JSON as publisher authorization."
        ),
    }
    _write_atomic(article_path, article)
    _write_atomic(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return article_path, receipt_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        article, receipt = render_handoff(args.input_json, args.output_dir)
    except (ValueError, OSError, KeyError, ForecastInputError, json.JSONDecodeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    print("REVIEW_REQUIRED: " + str(article))
    print("HANDOFF: " + str(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
