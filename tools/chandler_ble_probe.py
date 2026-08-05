#!/usr/bin/env python3
"""Probe a Chandler Legacy View valve directly over Bluetooth LE on macOS."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
from random import SystemRandom
import sys
import time
from typing import Any

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print(
        "Missing dependency: bleak. Install it with:\n"
        "  python3 -m venv .venv-chandler\n"
        "  source .venv-chandler/bin/activate\n"
        "  python3 -m pip install -r tools/chandler_probe_requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(2)

DEVICE_LIST = 116
DASHBOARD = 117
RESET = 114
PACKET_LENGTH = 20
AUTHENTICATED = 128
NOT_AUTHENTICATED = 0

GATT_PROFILES = (
    (
        "00001000-0000-1000-8000-00805f9b34fb",
        "00001002-0000-1000-8000-00805f9b34fb",
        "00001001-0000-1000-8000-00805f9b34fb",
    ),
    (
        "6e400001-b5a3-f393-e0a9-e50e24dcca9e",
        "6e400003-b5a3-f393-e0a9-e50e24dcca9e",
        "6e400002-b5a3-f393-e0a9-e50e24dcca9e",
    ),
    (
        "a725458c-bee1-4d2e-9555-edf5a8082303",
        "a725458c-bee2-4d2e-9555-edf5a8082303",
        "a725458c-bee3-4d2e-9555-edf5a8082303",
    ),
)

_RANDOM = SystemRandom()
_ALLOWED_POLYNOMIALS = tuple(
    value for value in range(1, 256) if 4 <= value.bit_count() <= 5
)


class Journal:
    """Write structured diagnostics to stdout and a JSON Lines file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = path.open("a", encoding="utf-8")

    def close(self) -> None:
        self._stream.close()

    def record(self, event: str, message: str, **values: Any) -> None:
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "message": message,
            **values,
        }
        print(message, flush=True)
        self._stream.write(json.dumps(entry, sort_keys=True) + "\n")
        self._stream.flush()


class LegacyCrc8:
    """CRC implementation used by the Chandler mobile application."""

    def __init__(self, polynomial: int, seed: int) -> None:
        self.polynomial = polynomial & 0xFF
        self.seed = seed & 0xFF

    def compute(self, value: int) -> int:
        data = value & 0xFF
        seed = self.seed
        for _ in range(8):
            seed_has_high_bit = seed & 0x80
            seed = (seed << 1) & 0xFF
            if data & 0x80:
                seed = (seed | 0x01) & 0xFF
            data = (data << 1) & 0xFF
            if seed_has_high_bit:
                seed ^= self.polynomial
        self.seed = seed & 0xFF
        return self.seed


def request_payload(command: int) -> bytes:
    """Build a Chandler request packet."""

    return bytes([command & 0xFF] * PACKET_LENGTH)


def password_digits(pin: int) -> tuple[int, int, int, int]:
    """Return PIN digits in the order expected by the protocol."""

    thousands, remainder = divmod(max(0, min(9999, pin)), 1000)
    hundreds, remainder = divmod(remainder, 100)
    tens, ones = divmod(remainder, 10)
    return ones, tens, hundreds, thousands


def authentication_payload(counter: int, pin: int) -> tuple[bytes, dict[str, Any]]:
    """Build a randomized authentication packet and non-secret metadata."""

    polynomial = _RANDOM.choice(_ALLOWED_POLYNOMIALS)
    seed = _RANDOM.randint(1, 255)
    random_xor = _RANDOM.randint(1, 255) ^ seed
    crc = LegacyCrc8(polynomial, seed)
    digits = password_digits(pin)
    intermediate = (counter & 0xFF) ^ crc.compute(random_xor)
    payload = bytearray(request_payload(DEVICE_LIST))
    payload[2] = 80
    payload[3] = 65
    payload[4] = polynomial
    payload[5] = seed
    payload[6] = random_xor
    payload[7] = crc.compute(intermediate) ^ digits[3]
    payload[8] = digits[2] ^ crc.compute(payload[7])
    payload[9] = digits[1] ^ crc.compute(payload[8])
    payload[10] = digits[0] ^ crc.compute(payload[9])
    for index in range(11, PACKET_LENGTH):
        payload[index] = _RANDOM.randint(1, 255)
    return bytes(payload), {
        "counter": counter & 0xFF,
        "polynomial": polynomial,
        "seed": seed,
        "xor": random_xor,
        "intermediate": intermediate,
    }


def is_device_list(packet: bytes) -> bool:
    return len(packet) >= 3 and packet[:2] == bytes((DEVICE_LIST, DEVICE_LIST))


def device_list_details(packet: bytes) -> dict[str, Any]:
    status = packet[7] if len(packet) > 7 else None
    counter = packet[11] if len(packet) > 11 else None
    state = {
        NOT_AUTHENTICATED: "not_authenticated",
        AUTHENTICATED: "authenticated",
    }.get(status, "unknown")
    return {
        "length": len(packet),
        "status": status,
        "authentication_state": state,
        "connection_counter": counter,
        "hex": packet.hex(),
    }


def characteristic_rows(services: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for service in services:
        for characteristic in service.characteristics:
            rows.append(
                {
                    "service": service.uuid.lower(),
                    "uuid": characteristic.uuid.lower(),
                    "properties": sorted(characteristic.properties),
                }
            )
    return rows


def select_characteristics(services: Any) -> tuple[list[Any], Any]:
    characteristics = [
        characteristic
        for service in services
        for characteristic in service.characteristics
    ]
    by_uuid = {item.uuid.lower(): item for item in characteristics}
    notify: list[Any] = []
    write = None

    for _, notify_uuid, write_uuid in GATT_PROFILES:
        notify_item = by_uuid.get(notify_uuid)
        write_item = by_uuid.get(write_uuid)
        if notify_item is not None and notify_item not in notify:
            notify.append(notify_item)
        if write is None and write_item is not None:
            write = write_item

    if not notify:
        notify = [
            item
            for item in characteristics
            if {"notify", "indicate"}.intersection(item.properties)
        ]
    if write is None:
        write = next(
            (
                item
                for item in characteristics
                if {"write", "write-without-response"}.intersection(item.properties)
            ),
            None,
        )
    if write is None:
        raise RuntimeError("No writable GATT characteristic was found")
    return notify, write


async def find_valve(name: str, timeout: float, journal: Journal) -> Any:
    """Find a BLE peripheral by its advertised local name."""

    journal.record("scan", f"Scanning for {name!r} for up to {timeout:.0f}s...")
    matched_advertisement = None

    def matches(device: Any, advertisement: Any) -> bool:
        nonlocal matched_advertisement
        candidate = advertisement.local_name or device.name or ""
        matched = candidate.casefold() == name.casefold()
        if matched:
            matched_advertisement = advertisement
        return matched

    device = await BleakScanner.find_device_by_filter(matches, timeout=timeout)
    if device is None:
        raise RuntimeError(f"Valve {name!r} was not found")
    advertisement = matched_advertisement
    manufacturer_data = {
        str(key): bytes(value).hex()
        for key, value in (
            getattr(advertisement, "manufacturer_data", {}) or {}
        ).items()
    }
    service_data = {
        str(key): bytes(value).hex()
        for key, value in (getattr(advertisement, "service_data", {}) or {}).items()
    }
    journal.record(
        "device",
        f"Found {device.name or name}: {device.address}",
        name=device.name or name,
        identifier=device.address,
        rssi=getattr(advertisement, "rssi", None),
        manufacturer_data=manufacturer_data,
        service_data=service_data,
    )
    return device


async def run_probe(args: argparse.Namespace, journal: Journal) -> None:
    """Connect to the valve and execute the selected protocol probes."""

    device = await find_valve(args.name, args.scan_timeout, journal)
    if args.scan_only:
        return

    pin_text = getpass.getpass("Valve PIN (4 digits, not logged): ").strip()
    if not (len(pin_text) == 4 and pin_text.isdigit()):
        raise ValueError("PIN must contain exactly four digits")
    pin = int(pin_text)

    queue: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    subscribed: list[Any] = []

    async with BleakClient(device, timeout=args.connect_timeout) as client:
        journal.record("connect", f"Connected: {client.is_connected}")
        services = client.services
        rows = characteristic_rows(services)
        journal.record(
            "gatt",
            f"Discovered {len(rows)} GATT characteristics",
            characteristics=rows,
        )
        for row in rows:
            print(
                f"  {row['service']} / {row['uuid']} "
                f"[{', '.join(row['properties'])}]"
            )

        notify_chars, write_char = select_characteristics(services)
        journal.record(
            "selection",
            f"Write characteristic: {write_char.uuid}; notify candidates: "
            + ", ".join(item.uuid for item in notify_chars),
            write_characteristic=write_char.uuid,
            notify_characteristics=[item.uuid for item in notify_chars],
        )

        def on_notification(characteristic: Any, data: bytearray) -> None:
            packet = bytes(data)
            uuid = getattr(characteristic, "uuid", str(characteristic))
            journal.record(
                "rx",
                f"RX {uuid} ({len(packet)} bytes): {packet.hex()}",
                characteristic=uuid,
                length=len(packet),
                hex=packet.hex(),
            )
            loop.call_soon_threadsafe(queue.put_nowait, (uuid, packet))

        for characteristic in notify_chars:
            try:
                await client.start_notify(characteristic, on_notification)
            except Exception as error:
                journal.record(
                    "notify_error",
                    f"Could not subscribe to {characteristic.uuid}: {error}",
                    characteristic=characteristic.uuid,
                    error=repr(error),
                )
            else:
                subscribed.append(characteristic)

        if not subscribed:
            raise RuntimeError("No notification characteristic could be subscribed")

        async def send(label: str, payload: bytes, *, sensitive: bool = False) -> None:
            properties = set(write_char.properties)
            response = "write" in properties
            include_payload = not sensitive or args.include_auth_payload
            display = payload.hex() if include_payload else "<redacted>"
            journal.record(
                "tx",
                f"TX {label} ({len(payload)} bytes): {display}",
                label=label,
                characteristic=write_char.uuid,
                response=response,
                length=len(payload),
                hex=payload.hex() if include_payload else None,
                sensitive=sensitive,
            )
            await client.write_gatt_char(write_char, payload, response=response)

        async def wait_for_device_list(timeout: float) -> bytes:
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Timed out waiting for DeviceList response")
                _, packet = await asyncio.wait_for(queue.get(), timeout=remaining)
                if is_device_list(packet):
                    details = device_list_details(packet)
                    journal.record(
                        "device_list",
                        "DeviceList: "
                        f"state={details['authentication_state']} "
                        f"status={details['status']} "
                        f"counter={details['connection_counter']}",
                        **details,
                    )
                    return packet

        try:
            await send("DeviceList", request_payload(DEVICE_LIST))
            packet = await wait_for_device_list(args.response_timeout)
            details = device_list_details(packet)
            state = details["authentication_state"]
            counter = details["connection_counter"]

            if state == "not_authenticated":
                if counter is None:
                    raise RuntimeError(
                        "DeviceList requires authentication but has no connection counter"
                    )
                for attempt in range(1, args.auth_attempts + 1):
                    payload, metadata = authentication_payload(counter, pin)
                    journal.record(
                        "auth_attempt",
                        f"Authentication attempt {attempt}/{args.auth_attempts} "
                        f"with counter {counter}",
                        attempt=attempt,
                        **metadata,
                    )
                    await send(
                        f"Authentication attempt {attempt}", payload, sensitive=True
                    )
                    packet = await wait_for_device_list(args.response_timeout)
                    details = device_list_details(packet)
                    state = details["authentication_state"]
                    if state == "authenticated":
                        journal.record("auth_success", "Authentication succeeded")
                        break
                    if details["connection_counter"] is not None:
                        counter = details["connection_counter"]
                else:
                    journal.record("auth_failure", "Authentication did not succeed")
                    return
            elif state == "authenticated":
                journal.record("auth_success", "Valve was already authenticated")
            else:
                journal.record(
                    "auth_unknown",
                    "DeviceList did not expose a recognized authentication state; "
                    "stopping before Dashboard",
                    **details,
                )
                return

            while not queue.empty():
                queue.get_nowait()
            await send("Dashboard", request_payload(DASHBOARD))
            deadline = time.monotonic() + args.dashboard_seconds
            dashboard_packets = 0
            while time.monotonic() < deadline:
                try:
                    _, packet = await asyncio.wait_for(
                        queue.get(), timeout=deadline - time.monotonic()
                    )
                except asyncio.TimeoutError:
                    break
                dashboard_packets += 1
                journal.record(
                    "dashboard_packet",
                    f"Dashboard packet {dashboard_packets}: {packet.hex()}",
                    packet_number=dashboard_packets,
                    length=len(packet),
                    hex=packet.hex(),
                )
            journal.record(
                "dashboard_summary",
                f"Received {dashboard_packets} Dashboard notification packet(s)",
                packet_count=dashboard_packets,
            )
        finally:
            try:
                await send("Reset", request_payload(RESET))
                await asyncio.sleep(0.2)
            except Exception as error:
                journal.record(
                    "reset_error", f"Reset request failed: {error}", error=repr(error)
                )
            for characteristic in subscribed:
                try:
                    await client.stop_notify(characteristic)
                except Exception:
                    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="CS_Aeration_Fltr")
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--scan-timeout", type=float, default=30.0)
    parser.add_argument("--connect-timeout", type=float, default=20.0)
    parser.add_argument("--response-timeout", type=float, default=6.0)
    parser.add_argument("--dashboard-seconds", type=float, default=8.0)
    parser.add_argument("--auth-attempts", type=int, default=1)
    parser.add_argument(
        "--include-auth-payload",
        action="store_true",
        help="include the reversible authentication packet in the diagnostic log",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = args.output or Path("diagnostics") / f"chandler-probe-{timestamp}.jsonl"
    journal = Journal(output)
    journal.record("start", f"Diagnostic log: {output}", output=str(output))
    try:
        asyncio.run(run_probe(args, journal))
    except KeyboardInterrupt:
        journal.record("interrupted", "Probe interrupted")
        return 130
    except Exception as error:
        journal.record("error", f"Probe failed: {error}", error=repr(error))
        return 1
    finally:
        journal.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
