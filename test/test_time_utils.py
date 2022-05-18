"""
Tests brewblox_devcon_spark.codec.time_utils
"""

from datetime import timedelta

from brewblox_devcon_spark.codec import time_utils


def test_parse_duration():
    assert time_utils.parse_duration('1d99m') == \
        timedelta(days=1, hours=1, minutes=39)


def test_serialize_duration():
    assert time_utils.serialize_duration(
        timedelta(seconds=70)) == '1m10s'

    assert time_utils.serialize_duration(
        timedelta(days=2, hours=30, seconds=1)) == '3d6h1s'
