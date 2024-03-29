import pytest

from brewblox_devcon_spark.codec import unit_conversion
from brewblox_devcon_spark.exceptions import InvalidInput


@pytest.fixture
def unit_ids():
    return [
        ('Celsius', 'degC'),
        ('DeltaCelsius', 'delta_degC'),
        ('DeltaCelsiusPerSecond', 'delta_degC / second'),
        ('Second', 'second'),
        ('InverseCelsius', '1 / degC'),
        ('DeltaCelsiusMultSecond', 'delta_degC * second'),
    ]


def test_convert_default(unit_ids):
    cv = unit_conversion.UnitConverter()
    for tup in unit_ids:
        id, unit = tup
        assert cv.to_sys_value(10, id) == 10
        assert cv.to_user_value(10, id) == 10
        assert unit == cv.to_user_unit(id)


def test_convert_sys():
    cv = unit_conversion.UnitConverter()
    assert cv.to_sys_value(10, 'Second', 'mins') == 600
    assert cv.to_sys_value(10, 'Second', 'minutes') == 600
    assert cv.to_sys_value(10, 'Second', 'min') == 600
    with pytest.raises(Exception):
        # m is SI 'meter'
        cv.to_sys_value(10, 'Second', 'm')


def test_update_config(unit_ids):
    cv = unit_conversion.UnitConverter()
    cv.temperature = 'degF'
    assert cv.to_user_value(10, 'Celsius') == pytest.approx((10 * 9 / 5) + 32)
    assert cv.temperature == 'degF'
    assert cv.to_sys_value(10, 'DeltaCelsius') == pytest.approx(10 * 5 / 9)

    with pytest.raises(InvalidInput):
        cv.temperature = 'cm'

    assert cv.to_sys_unit('Celsius') == 'degC'
    assert cv.to_user_unit('Celsius') == 'degF'
