# JRA-VAN RACE free-trial handoff (PC2)

## Why the automatic RACE path is paused

The local free-trial archive succeeded for several setup dataspecs, but RACE
remains blocked when called from the project's external Python COM client.

Sanitized environment evidence from PC2:

- machine: DESKTOP-MVV1FD4
- project Python: 3.14.2 / 64-bit
- 32-bit JVDTLab.JVLink COM registration: present
- 64-bit JVDTLab.JVLink COM registration: present
- project archive: D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025
- project archive size: about 5.32 GiB
- official JV-Link provider cache on C: about 2.22 GiB
- C free space at probe time: about 31.31 GiB
- D free space at probe time: about 926.05 GiB
- provider access during the environment probe: none
- usage key read: none

JRA-VAN's public developer community contains the same free-trial pattern:
the official Data Lab validation tool can open RACE while an external program
using JVInit("UNKNOWN") receives an authentication failure.

Relevant public references:

- https://developer.jra-van.jp/t/topic/916
- https://developer.jra-van.jp/t/topic/822
- https://developer.jra-van.jp/t/topic/959

No paid subscription, key reissue, uninstall/reinstall, or dual-install removal
is authorized by this handoff.

## Storage preparation

Before using the official validation tool, create/use this D-drive parent:

    D:\JRA-VAN\Data Lab

In the official JV-Link settings dialog, use the documented **Data Save**
setting to point the save location to the D-drive parent above.

Do not delete the existing C-drive provider cache automatically. It is only
about 2.22 GiB and may still be useful for JV-Link state/cache consistency.

The project's own raw research archive stays separate at:

    D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025

## One manual validation action

Use the **64-bit Data Lab validation tool** on PC2.

Purpose: confirm whether the official tool can open the bounded pre-2025 RACE
setup request under the current free-trial state.

Required boundaries:

- dataspec: RACE
- setup mode / option: 4
- start: 20170101000000
- end: 20249999999999
- do not request 2025 or 2026 data
- do not change/purchase/renew a usage key
- do not switch to a paid service
- do not use final-payout data as purchase-time EV evidence

Record only these sanitized results:

- JVInit return code
- JVOpen return code
- read count
- download count
- last file timestamp
- whether the official tool completed normally

If JVOpen succeeds in the official tool, stop before any ad-hoc workaround.
Return those sanitized values to the project so the next acquisition/import
step can be designed around the official tool's supported behavior.

If JVOpen fails in the official tool as well, record the code and stop. Do not
loop retries, reinstall JV-Link, remove a 32/64-bit installation, reissue a key,
or start a paid subscription without explicit user approval.

## Research boundary

The 2025-2026 final independent holdout remains untouched by model training,
feature engineering, tuning, or evaluation. This handoff exists only to recover
a clean independent pre-2025 RACE development source.
