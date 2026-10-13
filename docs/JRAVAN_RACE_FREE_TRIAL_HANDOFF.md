# JRA-VAN RACE auth blocker — PC2 handoff (2026-10-14)

## Verified current state

GitHub PR #141 remains Draft. This is an **offline, local provenance**
handoff, not permission to purchase or retry provider access.

- Physical archive host: PC2 (`DESKTOP-MVV1FD4`).
- Approved, VERIFIED research archive: `D:\JRA-VAN\Data Lab\archive\pre2025`.
- Existing former D location: `D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025` — retained as a separate, unmodified source backup.
- C local archive location contains the pre-existing `MOVED_TO_D.json` marker. The private research archive is already on D.
- Original and v2 manifests were preserved byte-for-byte during migration.
- Private archive migration workflow run **38384279230**: 12 files, 5,712,772,127 bytes verified via SHA-256. Original source was not deleted.
- Offline RACE manifest diagnosis workflow run **38390982174**: SUCCESS. Across original, reassessed and relocated manifests, `RACE.status=failed`, `return_code=-301`, `records_written=0`, `raw_file_present=false`, `research_use_allowed=false`.
- BLDN pedigree provenance verification **38385246243**: SUCCESS, 79,888 BLDN records and 62,880 snapshot rows.
- Last confirmed C free: about 31.35 GiB; D free: about 920.73 GiB.
- JV-Link's **provider-managed cache and official Data Save settings have not been modified by this development**. Do not confuse the provider cache with our private research archive.
- 2025–2026 protected final holdout remains unopened.

## The only outstanding RACE unblock path

RACE is absent because the bounded original JVOpen was rejected with **-301**.
This is not a manifest path, migration, or parquet/parser issue. The official
validation tool may behave differently from an external Python COM client; that
difference has **not** been verified on this session.

Use the **64-bit Data Lab validation tool** on PC2. **Do not switch to a paid service.**
**Do not request 2025 or 2026 data.** These constraints are mandatory for the
manual setup validation, not just for the project's Python interface.

On physical PC2, when independently confirmed that the existing entitlement is
still free and personal research use is permitted, a human can use the official
64-bit JRA-VAN Data Lab validation/sample tool to check the bounded RACE setup
open. Preserve existing JV-Link settings and local cache. Do **not** read,
print, reissue or upload the usage key; do not change the paid-service state.

Approved test envelope, **if the official tool supports the exact setup bound**:

- dataspec: `RACE`
- setup option: `4`
- start: `20170101000000`
- end: `20249999999999`
- No fallback to current 2025/2026 data, unbounded setup, or option 1.

Capture and share **only** sanitized metadata: JVInit/JVOpen return codes,
read count, download count, last-file timestamp and official-tool completion
status. If the official tool cannot guarantee the provider-side range, **stop
before accessing data**.

Relevant JRA-VAN developer community references (historical context;
not evidence that an entitlement is valid today):

- https://developer.jra-van.jp/t/topic/916
- https://developer.jra-van.jp/t/topic/822
- https://developer.jra-van.jp/t/topic/959

**Do not** pay/renew, uninstall/reinstall JV-Link, delete any previous source
archive, retry authentication in a loop, or change the provider Data Save
setting automatically.

## One-shot integrity rule

The Phase 12 and 13 evaluators now use an atomic exclusive receipt claim
(`os.O_CREAT | os.O_EXCL`) **after bounded provenance verification but
before parsing RACE or training any model**. A killed or failed run leaves
`phase12_evaluation_started` or `phase13_evaluation_started` locally and
cannot be retried without a new, independently approved research protocol.
Successful runs finalize to `phase12_real_evaluation_consumed` or
`phase13_real_evaluation_consumed` with summary SHA-256.

Both evaluation workflows additionally reject hosts other than physical PC2.
The existing checksums, 2025–2026 final holdout, no-paid-services policy,
research-only requirement and no-live-bets boundary remain in force.

**As of this handoff: both Phase 12 and Phase 13 one-shot evaluations remain
UNCONSUMED. No gain in real expected value has been established.**
