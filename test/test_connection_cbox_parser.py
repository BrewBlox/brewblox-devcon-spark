from brewblox_devcon_spark.connection.cbox_parser import CboxParser


def serial_data():
    return [
        '<add>0A<id>00<OneWir<!connected:sen',
        'sor>eTem<!s',
        'paced message>pSensor>01<address>28C80E',
        '9A0300009C\n',
        '34234<!connected:mess<!interrupt>',
        'age>\n',
        '<!interrupted! ',
        'message>',
        '<invalid! event!>'
    ]


def expected_events():
    return [
        'add',
        'id',
        '!connected:sensor',
        '!spaced message',
        'OneWireTempSensor',
        'address',
        '!interrupt',
        '!connected:message',
        '!interrupted! message',
        'invalid! event!',
    ]


def expected_data():
    return [
        '0A''00''01''28C80E9A0300009C',
        '34234'
    ]


def test_parser():
    parser = CboxParser()
    actual_events = []
    actual_data = []

    # It doesn't matter much when data is available, as long as we get all of it
    for chunk in serial_data():
        parser.push(chunk)
        actual_events += [msg for msg in parser.event_messages()]
        actual_data += [msg for msg in parser.data_messages()]

    assert actual_events == expected_events()
    assert actual_data == expected_data()


def test_parser_partial():
    parser = CboxParser()
    chunks = serial_data()

    parser.push(chunks[0])
    assert [msg for msg in parser.event_messages()] == ['add', 'id']
    assert [msg for msg in parser.data_messages()] == []

    parser.push(chunks[1])
    assert [msg for msg in parser.event_messages()] == ['!connected:sensor']
    assert [msg for msg in parser.data_messages()] == []
