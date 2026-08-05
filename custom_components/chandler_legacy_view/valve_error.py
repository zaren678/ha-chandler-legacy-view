"""Helpers for decoding and presenting Chandler valve errors."""

from __future__ import annotations


# CsValveError values verified against the official Legacy View Android app.
_VALVE_ERROR_DISPLAY: dict[int, str] = {
    0: "No Error",
    2: "Lost home, but looking for home",
    3: "Not seeing slots, normal motor current",
    4: "Lost home, can't find it after looking",
    5: "Not seeing slots, high motor current",
    6: "Not seeing slots, no motor current",
    192: "Regen aborted, can't start a regen while on battery",
    193: "Power debounced, if this happens frequently, check power supply",
}

# EVB019 advertisements use one-hot bits which the app converts to CsValveError.
_EVB019_VALVE_ERROR_MAP: dict[int, int] = {
    0: 0,
    1: 2,
    2: 3,
    4: 4,
    8: 5,
    16: 6,
    32: 7,
}


def decode_evb019_valve_error(raw_code: int) -> int:
    """Decode an EVB019 advertisement error using the official app mapping."""

    return _EVB019_VALVE_ERROR_MAP.get(raw_code, 0)


def valve_error_active(error_code: int | None, raw_code: int | None) -> bool | None:
    """Return whether either the decoded or raw valve state reports an error."""

    if raw_code is not None:
        return raw_code != 0
    if error_code is None:
        return None
    return error_code != 0


def valve_error_display(
    error_code: int | None,
    is_clack_valve: bool,
    raw_code: int | None = None,
) -> str | None:
    """Return the official display text, retaining unknown nonzero raw errors."""

    if raw_code not in (None, 0) and error_code in (None, 0):
        return f"Unknown valve error (raw code {raw_code})"

    if error_code == 7:
        return (
            "Drive 1 motor timeout error"
            if is_clack_valve
            else "TWEDO motor timeout error"
        )

    display = _VALVE_ERROR_DISPLAY.get(error_code) if error_code is not None else None
    if display is not None:
        return display

    if raw_code not in (None, 0):
        return f"Unknown valve error (raw code {raw_code})"
    if error_code not in (None, 0):
        return f"Unknown valve error (code {error_code})"
    return None
