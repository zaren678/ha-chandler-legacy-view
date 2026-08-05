"""Helpers for decoding Chandler firmware version bytes."""

from __future__ import annotations


def decode_firmware_number(value: int) -> int:
    """Decode one BCD-like firmware component from a valve advertisement."""

    normalized = value & 0xFF
    formatted = f"{normalized:02X}"
    try:
        return int(formatted)
    except ValueError:
        return normalized


def decode_firmware_major(value: int) -> int:
    """Decode a firmware major byte that may contain a C or D prefix."""

    normalized = value & 0xFF
    formatted = f"{normalized:02X}"
    if formatted[0] in {"C", "D"} and formatted[1].isdigit():
        return int(formatted[1])
    return decode_firmware_number(normalized)


def decode_firmware_version(major_raw: int, minor_raw: int) -> tuple[int, int, int]:
    """Return decoded major, minor, and combined firmware versions."""

    major = decode_firmware_major(major_raw)
    minor_value = decode_firmware_number(minor_raw)
    minor = 99 if minor_value >= 250 else minor_value
    return major, minor, major * 100 + minor


def firmware_model(firmware_version: int) -> str:
    """Return the Chandler hardware family for a decoded firmware version."""

    return "Evb034" if firmware_version >= 600 else "Evb019"
