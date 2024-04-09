from datetime import datetime, timedelta, timezone

import pytest

from brewblox_devcon_spark.codec import time_utils
from brewblox_devcon_spark.codec.opts import DateFormatOpt


def test_parse_duration():
    assert time_utils.parse_duration('1d99m') == \
        timedelta(days=1, hours=1, minutes=39)

    assert time_utils.parse_duration(100) == \
        timedelta(seconds=100)

    assert time_utils.parse_duration(None) == \
        timedelta(seconds=0)

    assert time_utils.parse_duration({
        '__bloxtype': 'Quantity',
        'unit': 'minute',
        'value': 20
    }) == \
        timedelta(minutes=20)


def test_serialize_duration():
    assert time_utils.serialize_duration(
        timedelta(seconds=70)) == '1m10s'

    assert time_utils.serialize_duration(
        timedelta(days=2, hours=30, seconds=1)) == '3d6h1s'


def test_parse_datetime():
    expected = datetime(year=2022,
                        month=7,
                        day=21,
                        hour=2,
                        minute=11,
                        second=5,
                        tzinfo=timezone.utc)

    assert time_utils.parse_datetime(expected) == expected
    assert time_utils.parse_datetime(1658369465) == expected
    assert time_utils.parse_datetime(1658369465000) == expected
    assert time_utils.parse_datetime('2022-07-21T02:11:05Z') == expected
    assert time_utils.parse_datetime(None) is None
    assert time_utils.parse_datetime(0) is None

    with pytest.raises(ValueError):
        time_utils.parse_datetime([1])


def test_serialize_datetime():
    dt = datetime(year=2022,
                  month=7,
                  day=21,
                  hour=2,
                  minute=11,
                  second=5,
                  tzinfo=timezone.utc)

    assert time_utils.serialize_datetime(dt, DateFormatOpt.MILLISECONDS) == 1658369465000
    assert time_utils.serialize_datetime(dt, DateFormatOpt.SECONDS) == 1658369465
    assert time_utils.serialize_datetime(dt, DateFormatOpt.ISO8601) == '2022-07-21T02:11:05Z'
    assert time_utils.serialize_datetime(None, DateFormatOpt.SECONDS) == 0
    assert time_utils.serialize_datetime(None, DateFormatOpt.ISO8601) is None

    with pytest.raises(ValueError):
        time_utils.serialize_datetime(dt, None)
