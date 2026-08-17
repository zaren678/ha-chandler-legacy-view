"""Helpers for synchronizing the EVB019 valve clock."""

from __future__ import annotations

from datetime import datetime


_PACKET_LENGTH = 20
_DASHBOARD_FILL = 117
_COMMAND_OFFSET = 13
_SET_TIME_COMMAND = 84


def create_set_time_payload(value: datetime) -> bytes:
    """Build the EVB019 Set Time payload for a local datetime."""

    hour_24 = value.hour
    hour_12 = hour_24 % 12 or 12

    payload = bytearray([_DASHBOARD_FILL] * _PACKET_LENGTH)
    payload[_COMMAND_OFFSET] = _SET_TIME_COMMAND
    payload[_COMMAND_OFFSET + 1] = hour_12
    payload[_COMMAND_OFFSET + 2] = value.minute
    payload[_COMMAND_OFFSET + 3] = 1 if hour_24 >= 12 else 0
    payload[_COMMAND_OFFSET + 4] = value.second
    return bytes(payload)
