# Phase 11 archive execution gate — cycle 63

Checked: 2026-10-11 JST. Research-only. Existing PR #141 remains draft.

## Current evidence
- Existing archive run 38049353331 remains queued; job 114205178121 is queued.
- Run head 2c297faa55d524a66c048d5f4198bf87af3c097b is older than current PR head.
- No sanitized manifest, local archive count, or SHA-256 evidence has yet been returned.
- Do not create a duplicate archive job while the original remains queued.

## Preconditions before any subsequent run
- Confirm free-trial entitlement and research rights at execution time.
- Require the exact provider-side range 20170101000000-20249999999999.
- Allow only the 14 approved dataspecs; reject duplicates and schedule/registration dataspecs.
- Keep all records local to the Windows runner; publish only sanitized counts, hashes, local paths and errors.
- Preserve existing successful files if a retry is empty or fails.
- Do not use 2025-2026 final holdout, final payouts, or post-race odds as prebet inputs.

## Outstanding review
- Archive implementation currently permits nonapproved dataspecs and alternate bounded ranges.
- A zero-record successful retry can overwrite a nonempty prior file.
- Free entitlement flags in the entrypoint are static rather than independently checked at execution time.
- Manifest overwrite can obscure evidence of prior successful parts.
- Do not merge Phase 11 or evaluate real 2023/2024 until independent development provenance is established.

Next: inspect archive run and sanitized manifest, then make only guarded, minimal changes on the existing PR branch.
