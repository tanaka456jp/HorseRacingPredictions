# Windows JRA-VAN bootstrap

The easiest local validation path is now a double-click launcher.

## Before running

Install the current JRA-VAN JV-Link on the Windows PC.

No project Python environment needs to be prepared manually.

## Smoke

From the repository root, double-click:

    RUN_JRAVAN_SMOKE.cmd

or run:

    powershell -ExecutionPolicy Bypass -File scripts/bootstrap_jravan_trial.ps1

The bootstrap:

1. locates Python 3.11+ (prefers Python 3.14 when available)
2. creates .venv-jravan
3. installs the project, CatBoost, pywin32 and kagglehub
4. verifies JVDTLab.JVLink COM registration
5. runs the lightweight Doctor
6. runs the bounded RA/SE smoke
7. creates artifacts/jravan_support_bundle.zip

The support ZIP is intentionally small and contains reports, not raw JV-Data.

## Full free-trial history acquisition

After Smoke PASS, double-click:

    RUN_JRAVAN_FULL.cmd

or run:

    powershell -ExecutionPolicy Bypass -File scripts/bootstrap_jravan_trial.ps1 -Full

The approved 1986-2021 base is downloaded automatically, so a base-history
path is normally unnecessary.

Successful full output:

    data/jravan/full/current_history.csv

This is the input to the Champion Forward Paper pipeline.

## Failure

If either launcher fails, keep:

    artifacts/jravan_support_bundle.zip

That bundle contains the Doctor/Smoke/Full audit reports and environment
metadata needed to diagnose the next step without copying raw JRA-VAN data.
