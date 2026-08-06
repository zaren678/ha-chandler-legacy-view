# UI paste — one file per automation (no `automation:` wrapper)

Each file is a SINGLE dict ready for **Settings → Automations → Create Automation → ⋮ → Edit in YAML → paste → Save**.

1. First create helper: **Settings → Helpers → Toggle** → Name `Treatment Valve remediation lock` (→ `input_boolean.treatment_valve_remediation_lock`)
2. Paste each file as its own automation:
   - `01_enable_persistent.yaml` — 21:00 on, 60m before your 22:00 regen
   - `02_disable_persistent.yaml` — off 5m after Idle
   - `03_stuck_remediation.yaml` — valve_error 10s OR Decompress/Air Release 120s stall (10.4s/9.3s motors + 44.8s dropout) → Next Step → plug `switch.unnamed_p316m_tapo_p316m_2` off 30s/on
   - `04_fake_idle_notify.yaml` — notify-only 10m Idle+flow>0.08

Why separate? HA UI single-automation YAML expects `alias:` at top level, not `automation:` nor `- alias:` list — pasting the combined list gives `extra keys not allowed @ data['automation']`. These 4 files avoid that.

Combined list for `automations.yaml` file is still in `../automation_treatment_valve_real_entities.yaml` (starts with `- alias:`).
