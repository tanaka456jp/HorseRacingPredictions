# Phase 11 prebet execution cutoff audit — 2026-10-10

Status: RESEARCH ONLY; no approved free source and no EV evaluation.

A quote observed before the scheduled start is not necessarily purchasable at decision time. A separate purchase cutoff instant must be evidenced. For a prospective quote, require observed_at <= captured_at <= decision_at < purchase_cutoff_at < scheduled_post_time. A provider-supplied cutoff reference is self-attested and must be verified independently. Quote source_name and source_reference must match the independently reviewed source record.

The official JRA ticket rules state that on-site sales close two minutes before scheduled post time (https://www.jra.go.jp/kouza/baken/). This is not proof of internet-channel cutoff, actual availability, or final executable odds.

The JvLink To Importer utility (https://jvlink-importer.org/) describes itself as MIT-licensed/free, but explicitly requires a paid JRA-VAN DataLab membership. Therefore it is NOT an approved free odds source. Free collector software does not imply free underlying data or acquisition/retention/ML rights.

Required next gate: independently verify zero-cost lawful access, automation and retention permission, purchase-channel-specific cutoff, immutable UTC quote capture, exact race/combination mapping, and time-stamped odds. No data may be collected or evaluated until approval. Do not use payouts or final odds as prebet prices.

A local synthetic-only proposed integration gate checks source/quote identity and purchase cutoff. Its 23 tests passed locally, but source/test commits were rejected by write safety checks; these results are NOT CI evidence.

Do not read the 2025-2026 final holdout or combined/current_history.csv for Phase 11, alter Forward Paper, or enable real wagers. Phase 11 Draft PR #141 must not merge without independent approved pre-2025 development-data provenance.
