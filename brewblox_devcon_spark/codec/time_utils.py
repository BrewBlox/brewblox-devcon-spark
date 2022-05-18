"""
Utility functions for datetime and duration handling
"""

from datetime import timedelta

from pytimeparse.timeparse import timeparse


def parse_duration(value: str) -> timedelta:
    try:
        return timedelta(seconds=float(value))
    except ValueError:
        return timedelta(seconds=timeparse(value))


def serialize_duration(td: timedelta) -> str:
    """
    Format timedelta as d(ays)h(ours)m(inutes)s(econds)

    timedelta(seconds=70) == 1m10s
    timedelta(hours=1.5) == 1h30m
    """
    periods = [
        ('d', 60*60*24),
        ('h', 60*60),
        ('m', 60),
        ('s', 1),
    ]
    seconds = int(td.total_seconds())
    output = ''
    for period_postfix, period_s in periods:
        if seconds >= period_s:
            period_value, seconds = divmod(seconds, period_s)
            output += f'{period_value}{period_postfix}'
    return output
