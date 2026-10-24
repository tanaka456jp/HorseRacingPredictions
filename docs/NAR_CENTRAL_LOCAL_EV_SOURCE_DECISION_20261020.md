# Central (JRA) + Local (NAR) Racing: executable-EV source decision

**2026-10-20 | Research source triage, NOT betting permission, source license,
or proof of positive EV.** Applies to Draft PR #141 only. Main unchanged.

## Decision

Expand the positive-expected-value research **scope** from JRA-only to
**JRA and NAR**. Allow either jurisdiction and any otherwise eligible win,
place, quinella, wide, trio or trifecta market to become the first
successful **independent, pre-purchase, net-of-cost EV experiment**.
Do not prefer exotic tickets merely because they have larger visible odds.
Never infer market-beating profitability from accuracy, hit rate, or synthetic
positive arithmetic.

**New, materially promising lead:** NAR's official Local Horse Racing
Information website now documents a publicly downloadable ZIP/CSV facility:

- Official manual: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
  (history lists an update on 2026-09-16).
- Official general terms: https://www.keiba.go.jp/terms.html
- Official race site: https://www.keiba.go.jp/
- The PC site has *today* ZIP files (`YYYYMMDD_(timestamp)_race.zip` and
  `YYYYMMDD_(timestamp)_odds.zip`) containing race-list, entry,
  settlement and odds CSV. The day's files refresh approximately every
  **2 minutes** and include **intermediate** odds.
- Separate *monthly* ZIP files (`YYYYMM_(timestamp)_race.zip` and
  `YYYYMM_(timestamp)_odds.zip`) refresh once per day at night.
  **Monthly odds are post-result/final only**: NEVER classify them as
  executable decision-time prices. Monthly odds are split into three
  ten-day date periods.
- The manual states **race information from January 1998**, and **odds
  information from March 2026**. Historical race coverage is incomplete
  in places. Data availability does not imply use rights.
- Its FAQ says horse, jockey and trainer **globally unique identifiers
  are not supplied**. The CSV quote example has venue, race date,
  race number, bet type, up to three horse numbers, odds, maximum odds,
  and popularity. Filenames' Unix timestamps indicate file version
  naming, NOT proof of actual client receipt, freshness, betting cutoff,
  executable price, or archival historical intermediate snapshots.
- The site's FAQ *recommends* at most approximately one acquisition per
  two minutes for same-day files and one per day for monthly files.
  This is **not** blanket permission for automation or redistribution.
- General terms reserve rights, prohibit unapproved reproduction and
  redistribution, and allow blocking abnormal/bad automated access.
  Explicit rights verification remains mandatory for robotic download,
  retention, private machine-learning research and downstream model use.
  Do not infer a research license from the presence of a download button.

### Protected date fence

The existing independent **2025–2026 final holdout is frozen** and must
**not** be read, downloaded, searched as a race dataset, trained on, or
re-evaluated. **All currently available historical NAR odds start in 2026
and therefore overlap that protected holdout**. The official download
manual and terms can be inspected as documentation; race-result or odds
rows from 2025–2026 cannot be used for development or as a backtest.

Subject to affirmative rights approval, NAR historical race information
from **no later than 2024-12-31** is a *potential* candidate for a
separate development input. But because historical pre-decision NAR odds
do not precede 2026 in the published download facility, there is no
documented paired pre-2025 quote source yet. A final-odds backtest cannot
establish the purchase-available edge. Future prospective collection
would need **explicitly pre-registered periods outside the locked
holdout** and an independently approved legal source; it is not
implicitly authorized by this document.

### Jurisdiction and market normalization

| Jurisdiction/segment | Markets/evidence | Evaluation unit |
| --- | --- | --- |
| `JRA` | Existing main/Phase 11 analysis; RACE provider -301 unresolved; no approved historical executable exotic quote feed | JRA race × eligible bet type × decision/cutoff |
| `NAR` thoroughbred flat racing | Monbetsu, Morioka, Mizusawa, Urawa, Funabashi, Oi, Kawasaki, Kanazawa, Kasamatsu, Nagoya, Sonoda, Himeji, Kochi, Saga | **Venue × race × bet type** with venue-specific cutoff/liquidity |
| `NAR_BANEI` | Obihiro (ばんえい). Different race physiology, pace, track, feature schema | Independent pipeline/model, no automatic pooling with flat-racing observations |

Do not mix JRA and NAR economic metrics by default. Cross-jurisdiction
horse identity requires validated entity resolution; matching Japanese
horse names alone is NOT authoritative. NAR venue-specific field size,
track/surface, early races, market liquidity, scratch/withdrawal,
bet-type availability and bet cutoffs are potential covariates.
Not all tickets are offered at every venue/race; an absent market is a
recorded **no-trade**, not an exclusion from the opportunity universe.

### Exact implementation and evaluation gates (all fail closed)

1. **Source authorization:** written/source-term confirmation of lawful
   free access, machine processing, retention, collection frequency,
   redistributability restrictions and any revocation.
2. **Strict input partition:** identify jurisdiction/venue/race/date/type;
   protect 2025–2026 and never silently map `NAR_BANEI` onto JRA/NAR flat.
   Every race ID/horse identity must be verified rather than imputed.
3. **Pre-purchase evidence:** separately retain quote generation/version
   timestamp, *observed-at / first-received-at*, predicted-at,
   submitted-at (only in an approved paper protocol), local purchase
   cutoff and scheduled post. Require actual receipt **before** decision
   and cutoff. A later downloaded historical file cannot retroactively
   qualify, even if its filename contains an earlier epoch.
4. **Execution realism:** odds can move, pari-mutuel quoted odds are not
   necessarily guaranteed fill prices; model the actually available
   amount and unfilled/late bets, commissions/fees, rounding and
   worst-case daily exposure. Only hypothetical paper observation
   unless the user separately authorizes an operational phase.
5. **Frozen strategy and independent comparison:** same venue/race/bet
   type/decision time/capital constraints for the JRA or NAR strategy
   and market baseline; include abstained and unavailable opportunities.
   Compute net ROI, paired advantage and independent day/race cluster
   uncertainty. Multiple venues, bet types and SNS hypotheses imply
   multiple testing: adjust before asserting superiority.

### Nonofficial/SNS inputs

Local reporters, venue-dependent weather/paddock information,
trainer/jockey remarks and public social media may improve event
awareness. Record `published_at` **and** `first_seen_at`, source
terms/rights, venue and independent race identity, revisions and rumor
reliability. Explicitly measure baseline-vs-SNS **incremental net EV**
using the identical pre-purchase market quote. Do not use after-the-fact
posts and do not upload author identity or copyrighted raw content to
GitHub/Actions.

## Immediate Go/No-Go / blockers

| Evidence gate | JRA | NAR |
| --- | --- | --- |
| Free and lawful historical race input | PARTIAL — archive BLDN; RACE -301 | CANDIDATE — official historical race ZIP/CSV, rights and completeness not approved |
| Legitimate decision-time quoted odds | BLOCKED | **CANDIDATE** only: official same-day intermediate CSV exists; license, actual collection clock and protected period unresolved |
| True executable odds/cutoff/nonfill | BLOCKED | BLOCKED |
| Frozen economic OOS compared against market | NOT RUN | NOT RUN |
| Positive **actual** net EV, independent support | NOT PROVEN | NOT PROVEN |

**GO is currently not justified for either.** For NAR, the lawful
point-in-time quote acquisition route is more concrete than JRA but
has *not* passed use-rights or holdout gates. Reassess feasibility
against the user's existing one-week deadline rather than indefinitely
adding synthetic tests. If approved free evidence cannot be found,
advise research freeze/retirement; do **not** destroy code/data without
user approval.

Nothing here authorizes automated downloading, any JRA-VAN authentication
retry or purchase, paid data, protected holdout access, actual betting,
Paper promotion, changes to Phase 12/13 one-shot gates, or merging PR #141.
