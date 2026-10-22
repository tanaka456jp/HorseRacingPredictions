# Research note: pari-mutuel quote is not an executable fixed price (2026-10-23)

Scope: JRA and NAR research; no raw race/odds data, protected holdout, scraping, or live wagers.

## Verified source and implication

JRA's odds glossary describes displayed odds as an *estimated payout multiple* (概算払戻率). Even a published final odds figure can differ from the eventual payout when scratches or dead heats occur:
https://www.jra.go.jp/kouza/yougo/w406.html

Therefore an observed pre-close decimal odds quote is **not** a fixed, executable payout price. A paper ticket can be accepted while its realized payout multiple differs from the observed quote. This distinction is important for all pari-mutuel ticket types, especially thin markets. This note does not claim the JRA rule is a legal specification for each NAR venue; NAR venue and ticket-specific rules need independent confirmation.

## Mandatory economic evidence, per market

Record separately: venue, organizer, ticket type, selection, odds source and permitted use, actual first-seen/observation time, quote, decision time, ticket acceptance/rejection, accepted stake, actual cutoff, final official payout/return/refund, and independently verifiable source provenance. A simulation must not mark an accepted ticket as a guaranteed-odds fill. If actual prospective accepted tickets are unavailable, label all estimates as scenario analyses, not measured executable ROI.

Use **realized net profit** = official payout/refund minus stake minus all attributable costs. Divide by committed stake for realized net ROI. Report paired market-baseline excess profit on the same eligible races/decision times, race/day clustered uncertainty, rejection rates, and liquidity/exposure constraints. Distinguish stake-weighted from race-weighted comparisons; do not claim economic GO from statistical positive paper ROI alone.

## Five gates (fail closed)

1. Lawful, free, sustainable data and retention/research rights: NOT VERIFIED.
2. Point-in-time pre-purchase odds with timestamp provenance: NOT VERIFIED.
3. Acceptance, changing payouts, costs, non-fills and capital constraints: NOT VERIFIED.
4. Independent chronological OOS/forward paper plus paired market comparator: NOT VERIFIED.
5. Positive realized net ROI and excess net profit with race/day uncertainty: NOT MEASURED.

Keep JRA and each NAR venue/format/ticket type separate. Treat Obihiro ban'ei separately. No 2025-2026 protected final holdout reads, no unapproved odds downloads, and no automatic paper/live promotion. SNS contributions require lawful access, first_seen_at and net EV lift versus the same no-SNS baseline.

**Status: MEASUREMENT_BLOCKED, economic GO prohibited.** This is a design/provenance note, not a claim of empirical improvement.
