"""
Tests brewblox_devcon_spark.codec.unit_conversion
"""

import pytest

from brewblox_devcon_spark.codec import unit_conversion
from brewblox_devcon_spark.exceptions import InvalidInput


@pytest.fixture
def unit_ids():
    return [
        ('Temp', 'degC'),
        ('DeltaTemp', 'delta_degC'),
        ('DeltaTempPerSecond', 'delta_degC / second'),
        ('Second', 'second'),
        ('InverseTemp', '1 / degC'),
        ('DeltaTempMultSecond', 'delta_degC * second'),
    ]


def test_convert_default(unit_ids):
    cv = unit_conversion.UnitConverter()
    for tup in unit_ids:
        id, unit = tup
        assert cv.to_sys_value(10, id) == 10
        assert cv.to_user_value(10, id) == 10
        assert unit == cv.to_user_unit(id)


def test_update_config(unit_ids):
    cv = unit_conversion.UnitConverter()
    cv.user_units = {'Temp': 'degF'}
    assert cv.to_user_value(10, 'Temp') == pytest.approx((10 * 9 / 5) + 32)
    assert cv.user_units['Temp'] == 'degF'
    assert cv.to_sys_value(10, 'DeltaTemp') == pytest.approx(10 * 5 / 9)

    with pytest.raises(InvalidInput):
        cv.user_units = {'Temp': 'cm'}

    assert cv.to_sys_unit('Temp') == 'degC'
    assert cv.to_user_unit('Temp') == 'degF'
