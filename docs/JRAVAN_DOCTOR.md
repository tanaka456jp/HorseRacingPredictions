# JV-Link Windows doctor

Run this before a large free-trial acquisition.

    pip install -r requirements-jravan.txt
    python scripts/jravan_doctor.py

The default doctor is intentionally lightweight: it opens RACE with option 2
and fromtime 00000000000000, which requests current-week data instead of
starting the historical setup download.

The doctor checks:

- Python architecture/version
- COM creation
- JVInit with SID UNKNOWN
- JVStatus before open
- JVOpen with dataspec RACE
- a bounded JVGets read
- RA/SE presence

The default SID UNKNOWN is the official value for personal/test development.
For distributed software a formally issued software ID is required.

Important error guidance:

- -301: authentication error
- -302: service right expired
- -303: usage key not configured
- -305: terms not accepted
- -112: invalid fromtime
- -202: previous open not closed

JVStatus=-203 before JVOpen is not treated as failure because JVStatus reports
download/read progress and no operation has started yet.

If the doctor reports -301 during the one-month free trial, first run the
official Data Lab validation/sample tool on the same Windows PC. A recent
community report observed official-tool success while a custom UNKNOWN-SID
program returned -301 during the trial, so the doctor preserves the exact
return codes instead of guessing that the subscription is required.

When status=ready, run:

    python scripts/jravan_trial_smoke.py

That performs a bounded RA/SE export and immediately runs the official-spec
parser. No raw JV-Data is committed or redistributed.


A bounded doctor sample that contains valid RACE records but happens to contain
no RA/SE is treated as a working JV-Link connection, not as a hard failure.
The larger trial smoke is responsible for proving that RA/SE can actually be
captured and parsed.


For setup/full acquisition, the exporter waits for JVStatus to reach the
JVOpen download_count before JVGets begins. JVGets -3 handling remains as a
fallback, but normal operation follows the official download-completion flow.
