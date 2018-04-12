"""
Tests brewblox_devcon_spark.device
"""

import pytest
from brewblox_devcon_spark import device, commander
from brewblox_codec_spark import codec
from asynctest import CoroutineMock
from unittest.mock import Mock


TESTED = device.__name__


@pytest.fixture
def commander_mock(mocker, loop):
    cmder = commander.SparkCommander(loop=loop)

    def echo(command):
        retval = command.decoded_request
        retval['command'] = command.name
        return retval

    cmder.write = CoroutineMock()
    cmder.do = CoroutineMock()
    cmder.bind = CoroutineMock()
    cmder.close = CoroutineMock()
    cmder.execute = CoroutineMock(side_effect=echo)
    return cmder


@pytest.fixture
def store_mock(mocker, loop):
    store = Mock().return_value

    store.start = CoroutineMock()
    store.close = CoroutineMock()
    store.find_by_id = CoroutineMock()
    store.create_by_id = CoroutineMock()
    store.update_by_id = CoroutineMock()
    return store


@pytest.fixture
async def app(app, commander_mock, store_mock, mocker):
    """App + controller routes"""
    mocker.patch(TESTED + '.SparkCommander').return_value = commander_mock
    mocker.patch(TESTED + '.DataStore').return_value = store_mock
    device.setup(app)
    return app


def test_setup(app, app_config):
    assert device.get_controller(app).name == app_config['name']


async def test_start_close(app, client, commander_mock):
    assert commander_mock.bind.call_count == 1
    assert commander_mock.close.call_count == 0

    controller = device.get_controller(app)

    await controller.close()
    await controller.close()
    assert commander_mock.close.call_count == 1

    await controller.start(app)
    assert commander_mock.bind.call_count == 2

    await controller.start(app)
    assert commander_mock.close.call_count == 2
    assert commander_mock.bind.call_count == 3

    # should not trigger errors in app cleanup
    await controller.close()


async def test_transcoding(app, client, commander_mock, store_mock):
    controller = device.get_controller(app)
    store_mock.find_by_id.return_value = dict(controller_id=[1, 2, 3])

    # OneWireTempSensor
    obj_type = 6
    obj = dict(
        settings=dict(
            address='ff',
            offset=20
        ),
        state=dict(
            value=12345,
            connected=True
        )
    )
    encoded = codec.encode(obj_type, obj)
    obj = codec.decode(obj_type, encoded)

    retval = await controller.object_update('alias', obj_type, obj)
    assert retval['data'] == obj

    # Test correct processing of lists of objects
    commander_mock.execute = CoroutineMock(return_value=dict(
        objects=[
            # Call dict twice to avoid populating the list with references to the same dict
            dict(type=obj_type, data=encoded),
            dict(type=obj_type, data=encoded),
        ]
    ))
    retval = await controller.object_update('alias', obj_type, obj)
    assert retval['objects'] == [dict(type=obj_type, data=obj)] * 2
