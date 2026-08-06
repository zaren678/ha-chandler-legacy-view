# Treatment Valve — how to wire the real entities

Your export shows the filter as `Treatment Valve / Mechanical Room` with these real ids:

- **Backwash State** (cycle phase, `Idle` / `Decompress (1)` / `Air Release (2)` / `Backwash (3)` …):  
  `sensor.mechanical_room_treatment_valve_treatment_valve_backwash_state`
- **Backwash Remaining** (cycle countdown, `None` during 0x7F motor, seconds):  
  `sensor.mechanical_room_treatment_valve_treatment_valve_backwash_remaining`
- **Valve Error**: `binary_sensor.mechanical_room_treatment_valve_treatment_valve_valve_error`
- **Present Flow** (`0.15 GPM` during Air Release — not used for remediation):  
  `sensor.treatment_valve_treatment_valve_present_flow`
- **Persistent Connection**: `switch.treatment_valve_treatment_valve_persistent_connection`
- **Next Regeneration Step**: `button.mechanical_room_treatment_valve_treatment_valve_next_regeneration_step`
- **Regeneration Time**: `sensor.mechanical_room_treatment_valve_treatment_valve_regeneration_time`
- **Available**: `binary_sensor.treatment_valve_treatment_valve`

Optional `switch.filter_smart_plug` — replace with your actual plug, e.g. `switch.mechanical_room_filter_plug`.

## Files
- `automation_treatment_valve_real_entities.yaml` — ready to paste (already uses the ids above, 120s for both Decompress/Air Release per your request).
- `automation_stuck_regeneration.yaml` — generic `cs_aeration_fltr` placeholder version.

## Quick start
1. Create `input_boolean.treatment_valve_remediation_lock` (already in the yaml).
2. In the remediation automation, replace `switch.filter_smart_plug` with your plug entity.
3. Adjust the `01:00:00` time trigger to 60m before your `sensor.mechanical_room_treatment_valve_treatment_valve_regeneration_time` value.
4. Keep `Backwash State` / `Backwash Remaining` names — they are the Evb019 `Regeneration State/Remaining` for filters (vs softeners).
5. Reload automations, keep `custom_components.chandler_legacy_view: debug` and trigger a good regen via `button.mechanical_room_treatment_valve_treatment_valve_regenerate_now` to capture the 90s→1s baseline.

## 120s rationale
From your good log 2026-08-05: Decompress motor 10.4s + 84.6s countdown (89→4s) = 95s total; Air Release motor 9.3s still `0x7F` + 44.8s gap to Backwash due to GATT 133. 120s covers both + dropout.
