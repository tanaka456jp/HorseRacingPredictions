# Local Friday OOS Economic Research Handoff (Pre-2025 only)

This is a **research-only** operator-prepared input contract for the frozen
JRA 2023–2024 evaluation plan. It is not a new JRA-VAN data retrieval route.
**Do not run it on the private historical archive without separately reviewed
source-use permission.** It must not be used to bypass any earlier runner or
archive-read refusal.

## Usage on a specifically approved, curated local JSON

```powershell
python scripts/evaluate_preregistered_friday_oos_local.py `
  --candidate-json "D:\ApprovedResearch\friday_oos_candidate.json" `
  --local-review-only
```

The example path is **illustrative** and does not imply that such an approved
file currently exists. The caller must supply a bounded, independently
reviewed JSON file, not a directory, archive, ZIP, JRA-VAN raw dataset,
automated provider session, or note credentials.

The JSON object must have **exactly** these keys:

```json
{
  "schema": "JRAFridayLockedOOSCandidate.v1",
  "expected_races": {"JRA-YYYYMMDD-01": "YYYY-MM-DD"},
  "documented_exclusions": {},
  "forecasts": [
    {
      "race_id": "JRA-YYYYMMDD-01",
      "race_day": "YYYY-MM-DD",
      "post_time_utc": "YYYY-MM-DDTHH:MM:SS+00:00",
      "predicted_at_utc": "YYYY-MM-DDTHH:MM:SS+00:00",
      "model_ref": "pre-2023-frozen-model-identifier",
      "model_fit_through_day": "2022-12-31",
      "winner_scores": {"FICTIONAL_HORSE_1": 0.3},
      "outsider_scores": {"FICTIONAL_HORSE_1": 0.1},
      "odds_used_in_selection": false
    }
  ],
  "settlements": [
    {
      "race_id": "JRA-YYYYMMDD-01",
      "finishing_positions": {"FICTIONAL_HORSE_1": 1},
      "win_return_per_100_yen": {"FICTIONAL_HORSE_1": 300},
      "place_return_per_100_yen": {"FICTIONAL_HORSE_1": 150}
    }
  ]
}
```

**The snippet above is a schema illustration, not a runnable full-race
fixture.** Real admission needs one independently identified race with
5–18 starters, every actual runner included in both score maps, finish ranks
1 through N, and complete official 100-yen win/place payouts including
zeroes for non-winners. No fabricated date, horse, result or price should be
substituted for unavailable data. Payouts are joined **after** forecast freeze.

For the locked study, all expected racing days must be Saturdays/Sundays in
2023–2024; each included forecast must have been genuinely recorded on the
immediately preceding Friday in Japan **after noon and before post time**.
The model fitting cutoff is no later than 2022-12-31. Every manifest race
must be either fully paired (forecast + settlement) or documented with an
approved, specific exclusion reason. Partial evaluation is refused: fewer
than **500 settled races and 60 distinct racing days** results in **no ROI**.

Even if sufficient fictional or independently prepared records produce a
positive simulated historical realized ROI:

- It does **not** verify source rights, historical timestamp provenance,
  independent model training, Friday information availability or official
  payouts.
- It does **not** prove future positive expected value, settle the untouched
  2025–2026 final holdout, authorize live wagering or activate note posting.
- Reports contain aggregated counts, reason categories and optional monetary
  diagnostics; they do not print horse names, private JSON values, filesystem
  paths or dataset rows.
- A failing safety/chronology/schema check emits a generic BLOCKED reason
  with exit code 2. Sub-threshold studies also exit 2; passing structural
  screening alone cannot override the independent review requirements.

The published GitHub test suite for this CLI uses **fictional races only**.
No legal or complete real-data input was discovered or reviewed in this change.
