# JRA-VAN support reply: personal-only research interpretation (2026-10-28)

**Scope:** HorseRacingPredictions Draft PR #142, non-public personal research only.
**Evidence handling:** User supplied a support-desk reply in private conversation. This public repository records only a summarized permission interpretation; the original email, sender metadata, contact address, account identifiers, keys and race records must never be committed, logged, or uploaded as artifacts.

## Directly evidenced in the support response

The JRA-VAN support desk referred the user to https://jra-van.jp/info/post_guide.html for JRA-VAN data uses, advised use within the guideline scope, and explicitly stated that **input into external AI is possible for personal use**, with appropriate data handling and attention to available AI-learning opt-out settings.

This is positive, source-specific evidence supporting a **personal-use / non-public research route**. It is not a commercial or unlimited redistribution license, and it does not by itself attest that any particular local historic file was acquired from JRA-VAN, that an ended trial allows indefinite retention, or that a self-hosted runner action previously rejected by a security review is now approved.

Independent current official references:
- [JRA-VAN terms, section 7: personal private use](https://jra-van.jp/info/rule.html)
- [JRA-VAN posting guideline](https://jra-van.jp/info/post_guide.html): JV-Link-acquired data cannot be posted to web services (including note); distinct conditional cases for TARGET and permitted screenshots should not be conflated with JV-Link data.
- [Developer announcement on redistributed commercial services](https://developer.jra-van.jp/t/topic/899): commercial supply of raw/provider data to end users requires a separate licensing route.

## Decision matrix (not machine-verifiable proof of archive rights)

| Planned action | Status | Conditions |
| --- | --- | --- |
| Local model training/backtest on PC②, personal private use | **PERSONAL_RESEARCH_ROUTE_SUPPORTED** | Confirm each historical file's provenance, contractual scope, and the personal/non-commercial/non-distributive purpose; keep data local |
| External AI input for personal use | **PERSONAL_USE_PERMITTED_WITH_PRECAUTIONS** | Only when necessary; verify opt-out/privacy options and downstream retention; never use default cloud export; limit/redact data |
| GitHub code-only development with synthetic fixtures | **ALLOWED** | No protected JV-Link records, actual horse identities, source filenames, credentials, model weights or private digests in public code, logs, artifacts |
| Public note/website/social release of raw JV-Link information | **BLOCKED** | Posting guideline's explicit ban; no reinterpretation based on AI transformations |
| Commercial/public third-party service, sale, redistribution | **SEPARATE_PERMISSION_REQUIRED** | Outside this personal-study approval |
| Retention/use of trial-acquired data after expiration | **UNCONFIRMED** | Needs contract-specific evidence, not assumed from support's generic reply |
| Read contents of the PC② 5.71 GB archive via previously rejected new Actions workflow | **BLOCKED** | A support reply cannot override that security refusal; no relabel, child-process reroute, or alternative implicit workflow |
| Modeling using archived files of unknown origin / mixed origins | **SOURCE_SPECIFIC_REVIEW_REQUIRED** | Actual archive contents and provenance have not been established |
| Using 2025–2026 protected final holdout for fitting/tuning | **BLOCKED** | Final holdout isolation unchanged |

## Operational default

1. **LOCAL_ONLY:** Use PC② local CatBoost / Python tools by default. No cloud LLM upload, no JRA-VAN/provider API refresh, no note login/post and no real betting.
2. **Rights evidence stays private:** Record the source contract, acquisition provenance and this support reply in a user-owned local evidence store **outside GitHub**, for operator review. A public document does not substitute for a binding source-specific approval receipt.
3. **Retain guards:** Old research-only archive-stage markers, 2025–2026 holdout isolation, pre-race feature availability, explicit full-file chronology validation, and verified official payouts remain mandatory.
4. **Next evidence step:** Review exact archived-source origins and allowable retention with the operator/authorized channel; use a separately permitted execution method for any local full-file read. Do not attempt to bypass the denied Windows workflow.
5. **Decision authority:** Only a separately approved actual-source lineage and lawful, local read permits historical validation. Note publishing remains inactive regardless of any private AI model performance.

**Evidence state at 2026-10-28:** support reply received; generic personal-use AI input supported; historical archive lineage not proven; 5.71 GB whole-file scan not performed; no actual CatBoost fit/official-payout ROI; positive-EV claim not demonstrated. No status here represents an automatic legal authorization or software-generated right to publish.
