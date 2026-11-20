# NAR official 2017–2022 monthly race ZIP acquisition — PC2, 2026-11-07

## Actual authorized PC2 acquisition (not fictional testing)

The operator requested acquisition of **all 71 missing NAR official
2017-01 through 2022-12 monthly race ZIPs** using the project's PC②
self-hosted Windows runner. The work used the official NAR monthly
"レース情報" button's HTTPS endpoint only:

`https://www.keiba.go.jp/KeibaWeb/DataDownload/RaceDataDownload?k_month=1&k_year=2017&type=monthly`

Only the year and month vary inside the **fixed 2017–2022** allowlist.
Reference: NAR's official
[data-download guide](https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf),
[monthly schedule](https://www.keiba.go.jp/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop?k_month=1&k_year=2017),
and [usage terms](https://www.keiba.go.jp/terms.html).
The user previously reported NAR permission for their own research;
that statement does not certify broad commercial redistribution rights.

### Direct GitHub Actions evidence

| Event | PC2 run | Verified outcome |
| --- | --- | --- |
| Existing month, before retrieval | Prior PC2 training inventory | 1/72, 71 missing |
| First test month | [#42376654398](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42376654398) | **One** official ZIP downloaded and validated. The run was marked failed only because the PowerShell step propagated the CLI's expected partial-download exit status. The ZIP remained valid and was retained. |
| Resumed one-month gate, then bulk | [#42376764634](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42376764634) | **SUCCESS:** 1 more one-month ZIP, then **69 additional ZIPs**, total **72/72 present, 0 missing**, with the existing original 2017-11 month never replaced. |
| Downloader fictional regressions | [CI #42376821933](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42376821933) | **992 PASS / 33 SKIP**, network-mocked test data only |

The final run's sanitized aggregate reports:
`originallyPresentThisBatch=3`,
`newlyValidatedOfficialZips=69`,
`missingAfter=0`, `sanitizedStopReason=""`.
Together with the preexisting 1 month plus two one-month gates,
**71 new ZIPs** were acquired. No 2017-11 original ZIP was overwritten.

### Implementation and safeguards

- `scripts/acquire_pc2_nar_2017_2022_months.py`: Windows PC②
  identity, repository/ref, and private D-drive directory guards.
- `.github/workflows/nar-pc2-acquire-71-official-months.yml`:
  self-hosted Windows, disk-space preflight, **one-month probe before
  batch**, 4-second interval per official GET, no third-party redirects,
  only HTTPS and fixed authorized endpoint; stop on provider 403/429.
- Per-file 400 MB cap, canonical official ZIP filename/month, three
  exactly matching CSV members, no encryption, 40 MB total uncompressed
  CSV cap, and **full CRC verification**.
- Unique `.part` temporary file on D: and **exclusive hard-link commit**
  into the final ZIP name prevents aborts or repeats from overwriting
  existing monthly originals. Reruns skip months already present.
- Private destination on PC②:
  `D:\Development\HorseRacingPredictions\nar-personal`.
- No raw CSV, horse names, race IDs, full ZIP paths, provider
  authorization credentials, original ZIP bytes or individual
  performance data were uploaded as GitHub artifacts or emitted into
  public Actions logs.
- 2023–2024 independent OOS and 2025–2026 final holdout contents
  were **never opened** in this download workflow. No JRA-VAN
  attempt, note posting, wagering, model fitting or ROI evaluation.

### Scope of completion

This proves *availability and validated ZIP integrity* for the
complete 72-month training/tuning source period. It does **not**
prove all original CSV records are internally consistent, free
of known historical exceptions, legally reusable commercially,
genuinely available before historical race start, or profitable.

The separate full 72-month read-only content/official-status preflight
[Run #42377327241](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/42377327241)
also completed **SUCCESS**. It processed real, private, authorized original
monthly ZIPs on PC2 and emitted only aggregate status counts:

| All-source denominator and outcomes | Exact count |
| --- | ---: |
| Months present, missing | **72**, **0** |
| NAR original source races | **89,654** |
| Predeclared banei/Obihiro races out of flat scope | **10,223** |
| Flat-race research scope | **79,431** |
| Previous strict numeric-rank only validated flat races | **69,484** |
| Previous strict unresolved flat races | **9,947** |
| Post-event official-status-and-payout reconciled flat races | **78,580** |
| Still unresolved flat races under official-status reading | **851** |
| Whole months with no status-aware unresolved flat races | **17** |
| Whole months passing strict rank-only train gate | **0** |

Arithmetic contracts: 89,654 = 10,223 + 79,431;
79,431 = 78,580 + 851 = 69,484 + 9,947.
The paired official-status interpretation newly resolves **9,096** races
that the old, rank-only parser would have quarantined, but the
remaining **851** must stay in the denominator and HOLD training/ROI
authorization. The 72 strict-unresolved months refer to the
*unchanged strict rank-only* gate, while the 17 fully status-aware
months refer to the separate post-event interpretation.

No forecasting model was fitted, no protected independent OOS was
opened, no historical pre-off timeline was verified and no economic
profitability was estimated by the preflight. Neither the full
download nor 78,580 correctly interpreted historical results
constitutes an after-cost positive-expectation demonstration.

Any unresolved payout/rank/status conflict must remain in the
full-source denominator and HOLD training authorization until
reconciled under the preregistered policy.

**After-cost positive out-of-sample expected value is NOT
demonstrated by obtaining the ZIP files.**
