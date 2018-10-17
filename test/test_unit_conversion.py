"""
Tests brewblox_devcon_spark.codec.unit_conversion
"""

import pytest

from brewblox_devcon_spark.codec.unit_conversion import UnitConverter
from brewblox_devcon_spark.exceptions import InvalidInput


@pytest.fixture
def unit_ids():
    return [
        ('Temp', 'degC'),
        ('DeltaTemp', 'delta_degC'),
        ('DeltaTempPerTime', 'delta_degC / second'),
        ('Time', 'second'),
    ]


def test_convert_default(unit_ids):
    cv = UnitConverter()
    for tup in unit_ids:
        id, unit = tup
        assert cv.to_sys(10, id) == 10
        assert cv.to_user(10, id) == 10
        assert unit == cv.user_unit(id)


def test_update_config(unit_ids):
    cv = UnitConverter()
    cv.user_units = {'Temp': 'kelvin'}
    assert cv.to_user(10, 'Temp') == pytest.approx(10 + 273.15)
    assert cv.user_unit('Temp') == 'kelvin'
    assert cv.to_sys(10, 'DeltaTemp') == 10

    with pytest.raises(InvalidInput):
        cv.user_units = {'Temp': 'cm'}
