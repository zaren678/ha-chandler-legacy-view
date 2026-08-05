"""Helpers for interpreting Chandler regeneration cycle state."""

from __future__ import annotations


_CYCLE_PHASES = {
    1: "Decompress (1)",
    2: "Air Release (2)",
    3: "Backwash (3)",
    5: "Air Draw (5)",
    6: "Rapid Rinse (6)",
}


def cycle_phase(regen_active: int, position: int) -> str:
    """Return the display name for the current regeneration cycle phase."""

    if not regen_active:
        return "Idle"

    return _CYCLE_PHASES.get(position, f"Position {position}")


def decode_bcd_time(value: int) -> int:
    """Decode a packed BCD time value, preserving unknown encodings."""

    normalized = value & 0xFF
    high, low = divmod(normalized, 16)
    if high < 10 and low < 10:
        return high * 10 + low
    return normalized


def cycle_remaining_seconds(
    regen_active: int, raw_time: int, seconds_mode: int
) -> int | None:
    """Return the phase countdown, excluding the motor-transition sentinel."""

    if not regen_active:
        return 0

    remaining = decode_bcd_time(raw_time)
    if remaining > 100:
        return None
    if seconds_mode:
        return remaining
    return remaining * 60
