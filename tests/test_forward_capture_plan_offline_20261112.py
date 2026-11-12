"""Offline-only validation of public-safe prospective capture metadata.

No provider access, file I/O, private identifiers, or side effects.
This is a feasibility gate, not a positive-EV or executable-price claim.
"""
from datetime import date, datetime, timezone
import unittest


def validate_public_capture_plan(plan, now_utc):
    """Return generic reason codes; never echo inputs to logs."""
    required = {"race_day", "freeze_utc", "first_off_utc", "race_count",
                "entrant_count", "win_tickets", "place_tickets"}
    if not isinstance(plan, dict) or set(plan) != required:
        return "HOLD_SCHEMA"
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is None:
        return "HOLD_CLOCK"
    try:
        race_day = date.fromisoformat(plan["race_day"])
        freeze = datetime.fromisoformat(plan["freeze_utc"].replace("Z", "+00:00"))
        off = datetime.fromisoformat(plan["first_off_utc"].replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return "HOLD_TIME"
    if freeze.tzinfo is None or off.tzinfo is None:
        return "HOLD_TIME"
    if any(type(plan[k]) is not int for k in
           ("race_count", "entrant_count", "win_tickets", "place_tickets")):
        return "HOLD_COUNTS"
    races, entrants = plan["race_count"], plan["entrant_count"]
    if not (0 < races <= entrants and
            plan["win_tickets"] == races and plan["place_tickets"] == races):
        return "HOLD_DENOMINATOR"
    if freeze >= off or freeze > now_utc or off <= now_utc:
        return "HOLD_CHRONOLOGY"
    # Date of the first off is local Japan calendar date, not UTC date.
    from datetime import timedelta
    jst = timezone(timedelta(hours=9))
    if off.astimezone(jst).date() != race_day:
        return "HOLD_RACE_DAY"
    return "READY_FOR_SEPARATE_PRIVATE_REVIEW_NOT_CAPTURE_AUTHORIZATION"


class ProspectiveMetadataTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        self.p = dict(race_day="2026-11-13",
                      freeze_utc="2026-11-12T11:00:00Z",
                      first_off_utc="2026-11-13T02:00:00Z",
                      race_count=2, entrant_count=20,
                      win_tickets=2, place_tickets=2)

    def test_valid_is_not_capture_authorization(self):
        self.assertEqual(validate_public_capture_plan(self.p, self.now),
                         "READY_FOR_SEPARATE_PRIVATE_REVIEW_NOT_CAPTURE_AUTHORIZATION")

    def test_rejects_old_off(self):
        self.p["first_off_utc"] = "2026-11-12T02:00:00Z"
        self.assertEqual(validate_public_capture_plan(self.p, self.now), "HOLD_CHRONOLOGY")

    def test_rejects_changed_denominator(self):
        self.p["place_tickets"] = 1
        self.assertEqual(validate_public_capture_plan(self.p, self.now), "HOLD_DENOMINATOR")

    def test_rejects_bool_count(self):
        self.p["race_count"] = True
        self.assertEqual(validate_public_capture_plan(self.p, self.now), "HOLD_COUNTS")

    def test_rejects_future_freeze(self):
        self.p["freeze_utc"] = "2026-11-12T13:00:00Z"
        self.assertEqual(validate_public_capture_plan(self.p, self.now), "HOLD_CHRONOLOGY")

    def test_rejects_wrong_local_day(self):
        self.p["race_day"] = "2026-11-14"
        self.assertEqual(validate_public_capture_plan(self.p, self.now), "HOLD_RACE_DAY")

    def test_rejects_extra_private_field(self):
        self.p["horse_name"] = "REDACTED"
        self.assertEqual(validate_public_capture_plan(self.p, self.now), "HOLD_SCHEMA")


if __name__ == "__main__":
    unittest.main()
