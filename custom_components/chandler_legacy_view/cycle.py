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


def cycle_remaining_seconds(
    regen_active: int, raw_time: int, seconds_mode: int
) -> int | None:
    """Return the phase countdown, excluding the motor-transition sentinel."""

    if not regen_active:
        return 0

    # Legacy View reads this field as a signed byte and presents its
    # nonnegative values directly; the wire value is not packed BCD.
    remaining = raw_time & 0xFF
    if remaining > 100:
        return None
    if seconds_mode:
        return remaining
    return remaining * 60
