"""Synthetic-only contract for prospective exotic odds evidence.

No network access, race-result access, EV decisions, or ticket generation.
A structurally valid quote is NOT a verified, lawful, executable price.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def _instant(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a nonempty ISO-8601 string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _combination(value: Any, bet_type: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("combination requires exactly three horse numbers")
    if any(type(n) is not int or n < 1 or n > 18 for n in value):
        raise ValueError("combination requires integer horse numbers 1..18")
    numbers = tuple(value)
    if len(set(numbers)) != 3:
        raise ValueError("combination horse numbers must be distinct")
    if bet_type == "trio":
        return tuple(sorted(numbers))
    return numbers


def inspect_exotic_prebet_quote(
    quote: Mapping[str, Any], *, decision_at: str
) -> dict[str, Any]:
    """Validate evidence metadata without granting acquisition or EV approval.

    The caller MUST separately verify source rights, actual availability at the
    decision time, race identity, and immutable acquisition evidence. Neither a
    source assertion nor a passed test can enable production or paper staking.
    """
    blockers: list[str] = []
    if not isinstance(quote, Mapping):
        return {
            "status": "blocked", "blockers": ["quote must be an object"],
            "approved_for_ev": False, "approved_for_acquisition": False,
        }

    def required(field: str) -> str:
        value = quote.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"missing {field}")
        return value.strip()

    canonical_key = None
    try:
        race_id = required("race_id")
        bet_type = required("bet_type")
        if bet_type not in ("trio", "trifecta"):
            raise ValueError("bet_type must be trio or trifecta")
        numbers = _combination(quote.get("horse_numbers"), bet_type)
        canonical_key = f"{race_id}:{bet_type}:" + "-".join(map(str, numbers))
        required("source_name")
        required("source_reference")
        if quote.get("quote_stage") != "pre_race":
            raise ValueError("quote_stage must be pre_race")
        if quote.get("odds_kind") != "decimal_quote":
            raise ValueError("odds_kind must be decimal_quote")
        if any(k in quote for k in (
            "payout", "final_payout", "settlement", "result",
            "finish_position", "final_odds",
        )):
            raise ValueError("result/final-payout fields are forbidden")
        allowed_fields = {
            "race_id", "bet_type", "horse_numbers", "decimal_odds",
            "source_name", "source_reference", "quote_stage", "odds_kind",
            "observed_at", "captured_at", "scheduled_post_time",
        }
        unknown_fields = set(quote) - allowed_fields
        if unknown_fields:
            raise ValueError("unrecognized quote fields are forbidden")
        try:
            odds = Decimal(str(quote["decimal_odds"]))
        except (KeyError, InvalidOperation, ValueError):
            raise ValueError("invalid decimal_odds") from None
        if not odds.is_finite() or odds <= 1:
            raise ValueError("decimal_odds must be finite and greater than 1")
        observed = _instant(quote.get("observed_at"))
        captured = _instant(quote.get("captured_at"))
        decision = _instant(decision_at)
        scheduled = _instant(quote.get("scheduled_post_time"))
        if not observed <= captured <= decision < scheduled:
            raise ValueError(
                "must satisfy observed_at <= captured_at <= decision_at "
                "< scheduled_post_time"
            )
    except (ValueError, TypeError) as exc:
        blockers.append(str(exc))

    return {
        "status": "blocked" if blockers else "human_review_required",
        "blockers": blockers,
        "canonical_combination_key": canonical_key if not blockers else None,
        "approved_for_ev": False,
        "approved_for_acquisition": False,
        "note": (
            "Timestamps and quote_stage are unverified source assertions. "
            "Human rights review, immutable capture evidence, bettable-price "
            "verification and strict OOS protocol are required before EV use."
        ),
    }
