"""Helpers for selecting Chandler protocol variants."""

from __future__ import annotations


_AUTHENTICATION_STATUS_VALUES = frozenset((0, 128))


def should_use_classic_password_decode(
    *,
    status: int,
    is_twin_valve: bool,
    firmware_version: int | None,
    has_connection_counter: bool,
) -> bool:
    """Return whether a DeviceList packet uses the classic password encoding."""

    if is_twin_valve or (status & 0xFF) in _AUTHENTICATION_STATUS_VALUES:
        return False

    if firmware_version is not None:
        return firmware_version < 420 and firmware_version != 419

    return not has_connection_counter
