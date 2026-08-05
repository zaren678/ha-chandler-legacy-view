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


def cycle_remaining_seconds(regen_active: int, remaining_seconds: int) -> int:
    """Return the current phase countdown, or zero while the cycle is idle."""

    if not regen_active:
        return 0
    return max(0, remaining_seconds)
