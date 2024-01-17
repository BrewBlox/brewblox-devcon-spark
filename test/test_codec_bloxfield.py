from brewblox_devcon_spark.codec import bloxfield


def test_link():
    assert bloxfield.is_link({
        '__bloxtype': 'Link',
        'id': 'Kettle Setpoint',
    })

    assert bloxfield.is_link({
        '__bloxtype': 'Link',
        'id': None,
        'type': 'SetpointSensorPair',
    })

    assert not bloxfield.is_defined_link({
        '__bloxtype': 'Link',
        'id': None,
        'type': 'SetpointSensorPair',
    })

    assert not bloxfield.is_link('id')
    assert not bloxfield.is_link(None)


def test_quantity():
    assert bloxfield.is_quantity({
        '__bloxtype': 'Quantity',
        'value': 40.0,
        'unit': 'degC',
    })

    assert bloxfield.is_quantity({
        '__bloxtype': 'Quantity',
        'value': None,
        'unit': 'degC',
    })

    assert not bloxfield.is_defined_quantity({
        '__bloxtype': 'Quantity',
        'value': None,
        'unit': 'degC',
    })

    assert not bloxfield.is_quantity(10)
    assert not bloxfield.is_quantity('many')
    assert not bloxfield.is_quantity(None)
