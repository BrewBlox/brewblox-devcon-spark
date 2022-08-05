"""
Utility functions for datetime and duration handling
"""

from datetime import datetime, timedelta, timezone
from typing import Union

import ciso8601
from pytimeparse.timeparse import timeparse

from .opts import DateFormatOpt

DurationSrc_ = Union[str, int, dict, timedelta, None]
DatetimeSrc_ = Union[str, int, float, datetime, None]


def parse_duration(value: DurationSrc_) -> timedelta:
    if not value:
        return timedelta(seconds=0)

    elif isinstance(value, timedelta):
        return value

    if isinstance(value, dict):
        v = value['value'] or 0
        u = value['unit']
        return parse_duration(f'{v} {u}')

    try:
        return timedelta(seconds=float(value))
    except ValueError:
        return timedelta(seconds=timeparse(value))


def serialize_duration(value: DurationSrc_) -> str:
    """
    Format timedelta as d(ays)h(ours)m(inutes)s(econds)

    timedelta(seconds=70) == 1m10s
    timedelta(hours=1.5) == 1h30m
    """
    td = parse_duration(value)

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
    return output or '0s'


def parse_datetime(value: DatetimeSrc_) -> Union[datetime, None]:
    if not value:
        return None

    elif isinstance(value, datetime):
        return value

    elif isinstance(value, str):
        return ciso8601.parse_datetime(value)

    elif isinstance(value, (int, float)):
        # This is an educated guess
        # 10e10 falls in 1973 if the timestamp is in milliseconds,
        # and in 5138 if the timestamp is in seconds
        if value > 10e10:
            value //= 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)

    else:
        raise ValueError(str(value))


def serialize_datetime(value: DatetimeSrc_, fmt: DateFormatOpt) -> Union[int, str, None]:
    dt = parse_datetime(value)

    if dt is None:
        return None if fmt == DateFormatOpt.ISO8601 else 0
    elif fmt == DateFormatOpt.MILLISECONDS:
        return int(dt.timestamp() * 1000)
    elif fmt == DateFormatOpt.SECONDS:
        return int(dt.timestamp())
    elif fmt == DateFormatOpt.ISO8601:
        return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    else:
        raise ValueError(f'Invalid formatting requested: {fmt}')
