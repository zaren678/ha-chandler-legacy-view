"""Helpers for Chandler regeneration commands and state."""

from __future__ import annotations


_PACKET_LENGTH = 20
_DASHBOARD_FILL = 117
_COMMAND_OFFSET = 13
_REGEN_NOW_COMMAND = b"RN"


def regeneration_is_active(regen_active: int, prefill_soak_mode: bool) -> bool:
    """Return whether the valve is in any regeneration phase."""

    return bool(regen_active) or prefill_soak_mode


def create_regen_now_payload() -> bytes:
    """Build the EVB019 state-dependent Regen Now/Next Step payload."""

    payload = bytearray([_DASHBOARD_FILL] * _PACKET_LENGTH)
    payload[_COMMAND_OFFSET : _COMMAND_OFFSET + len(_REGEN_NOW_COMMAND)] = (
        _REGEN_NOW_COMMAND
    )
    return bytes(payload)
