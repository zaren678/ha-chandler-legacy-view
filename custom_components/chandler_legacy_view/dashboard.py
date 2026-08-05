"""Helpers for presenting Chandler Dashboard values."""

from __future__ import annotations


def format_time_of_day(hour: int, minute: int, is_pm: bool) -> str | None:
    """Format the valve's local clock without treating it as an instant in time."""

    if hour < 0 or hour >= 24 or minute < 0 or minute >= 60:
        return None

    if hour > 12:
        return f"{hour:02d}:{minute:02d}"

    display_hour = 12 if hour == 0 else hour
    period = "PM" if is_pm else "AM"
    return f"{display_hour}:{minute:02d} {period}"
