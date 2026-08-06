# Chandler Legacy View Home Assistant Integration

The Chandler Legacy View project is a Home Assistant custom integration that
focuses on water system valves such as water softeners and filtration systems.
The integration listens for Bluetooth advertisements emitted by supported
valves, recognises them by their signatures, and surfaces their presence inside
Home Assistant as entities that can participate in automations or dashboards.

## Supported devices

* **Evb019 (firmware < 600, e.g. `CS_Aeration_Fltr`) — full read-only parity:** device-list auth, dashboard, Advanced Settings, Status & History, cycle/error diagnostics. All 3 BLE requests run on separate schedules so dashboard never stalls.
* **Evb034 / 400-series (firmware ≥ 600) — basic:** device-list + dashboard only. Advanced/History/Regeneration are Evb019-only and are gated by `model in (None, "Evb019")` to avoid mis-parsing; Evb034 uses a different `CsBlePacket` UART structure.
* **Twin systems** (`is_twin_valve` / `D`-prefixed firmware) are detected and use twin-aware salt-dose (199) and flag decoding.

## Current capabilities

* Establishes a Home Assistant config entry via the UI (no YAML required).
* Watches for Bluetooth advertisements that match the expected Chandler valve signatures (name prefixes `CS_`/`Chandler` + manufacturer ID), tracks multiple valves by Bluetooth address.
* Creates `binary_sensor` availability + `Valve Error` problem sensor (official Evb019 bit map, unknown non-zero raw codes kept so automations fail-safe).
* Surfaces firmware/model/serial via device info + entity attributes (Evb019 `<600` vs Evb034 `≥600` from `firmware.py`).
* **Dashboard (117, every 15 min + optional 1-4s persistent, separate BLE connection)** — authenticated poll, read-only: `Present Flow`, `Water Hardness` (metered softeners), `Time of Day`, `Battery` (non-Clack), `Soft Water Remaining`, `Days Until Regeneration/Backwash`, `Water Usage Today`, `Peak Flow Today`, `Regeneration/Backwash State` + `Remaining` (with `cycle_remaining_seconds`/`cycle_phase`).
* **Advanced Settings (118, every 1h, separate 2-packet connection)** — Evb019 only, read-only: 8× `Regen Position 1..8` sensors (`DIAGNOSTIC`, `minutes` or `lb` for softener salt-dose pos 5, `not_adjustable` flag via high-bit, defaults snapshot as attribute). Never blocks dashboard.
* **Status & History (119, every 6h, separate ~14-packet connection, 12s timeout)** — Evb019 only, read-only: `History Total Gallons`/`Resettable` (`total_increasing`/`total`), `History Regen Count`/`Resettable`, `History Water Usage Day` (62× `gal/day` `*10`, state=today, `attributes: water_usage_day[62]`), `History Water Usage Per Regen` (42× `gal`, `attributes: water_usage_regen[42]`), `History Peak Flow` (62× `GPM` `*0.1`, `attributes: peak_flow[62]`). HA long-term statistics on `total_increasing` gives `gal/day` over years; valve's 62-day buffer is available instantly.
* **Controls (read-only except guarded regeneration):** `Refresh Now` (dashboard `117` only), `Regenerate Now` / `Next Regeneration Step` (Evb019 only, refreshes state before send so only valid action is available). Regen cycle timings are intentionally not writable.
* **Diagnostics:** polling interval + persistent-connection toggle per valve (persisted per address, survives restarts), reset-buffer `114` sent on disconnect.
* **Probe:** `tools/chandler_ble_probe.py` does read-only `116→117→118→119` captures (`--dashboard-seconds`/`--advanced-settings-seconds`/`--history-seconds`) for manual validation; `diagnostics/` is gitignored.
* **Stuck-regeneration handling (example):** `examples/automation_stuck_regeneration.yaml` — enable `persistent_connection` 60m before `Regeneration Time` (so 4s polling, separate BLE conn) and run 2 flow-immune detectors: (A) `valve_error == on` for 10s, (B) `Decompress (1)` / `Air Release (2)` stall for **120s** each (covers 10.4s/9.3s `0x7F` motors + 44.8s GATT dropout seen 2026-08-05) and `cycle_remaining_seconds` stuck `None` 120s. Shared `input_boolean` lock prevents A/B double-fire; remediation is `Next Step` → 60s wait → smart-plug `off 30s/on`. `present_flow` (~0.15 GPM during Air Release) is **not** used for remediation to avoid laundry/toilet false positives; a 10m-debounced `Idle + flow >0.08` notify is included separately.

## Installation

1. Copy the `custom_components/chandler_legacy_view` directory into your Home
   Assistant `custom_components` folder.
2. Restart Home Assistant to load the new integration.
3. In Home Assistant, navigate to **Settings → Devices & Services → Add
   Integration** and search for "Chandler Legacy View".
4. Complete the configuration flow to enable Bluetooth-based discovery of
   Chandler valves. The integration uses the factory default valve passcode
   (`1234`) automatically; per-valve overrides can be configured later from the
   integration options. Only one instance of the integration is required.

## Development

* `custom_components/chandler_legacy_view/discovery.py` implements the Bluetooth
  discovery logic.
* `custom_components/chandler_legacy_view/binary_sensor.py` defines the initial
  entity type exposed by the integration.
* Configuration flow strings are located in
  `custom_components/chandler_legacy_view/translations/en.json`.

Contributions are welcome! The goal is to expand the integration to expose the
valve state (e.g. service mode, regeneration cycles) and diagnostics as the
device protocol becomes better understood.

### Local Codex initialization prompt

> Read AGENTS.md and README.md to familiarize yourself with this repository. After performing any work which resulted in uncommitted changes to repository files, provide a commit message for the work. Commit messages should be provided in fenced code blocks for easy copy/paste.
