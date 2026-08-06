# Chandler BLE probe

`chandler_ble_probe.py` talks directly to a Chandler valve over Bluetooth LE. It
captures advertisements, GATT characteristics, DeviceList responses,
authentication results, and Dashboard notifications without Home Assistant.

## Setup on macOS

Stop or reload the Chandler Legacy View integration in Home Assistant first.
Only one client should connect to the valve while probing.

```sh
cd ~/DevTesting/ha-chandler-legacy-view
python3 -m venv .venv-chandler
source .venv-chandler/bin/activate
python3 -m pip install -r tools/chandler_probe_requirements.txt
```

The first run may trigger a macOS Bluetooth permission prompt for Terminal.
Allow it in **System Settings > Privacy & Security > Bluetooth**.

## Run

Verify that the valve is visible without connecting:

```sh
python3 tools/chandler_ble_probe.py --scan-only
```

Run one authentication attempt followed by read-only Dashboard, Advanced
Settings, and Status & History requests:

```sh
python3 tools/chandler_ble_probe.py
```

The probe prompts for the four-digit PIN. It does not store the PIN or the
authentication payload by default. Raw responses are written to a timestamped
file under `diagnostics/`; that directory is ignored by Git.

Use `--help` to change the advertised valve name or timeouts. Avoid
`--include-auth-payload` when sharing logs because the authentication packet is
sensitive.
