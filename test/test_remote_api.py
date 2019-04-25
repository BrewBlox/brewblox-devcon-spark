"""
Tests brewblox_devcon_spark.api.remote_api
"""

import asyncio
from copy import deepcopy
from unittest.mock import call

import pytest
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_devcon_spark import (commander_sim, datastore, device, seeder,
                                   status)
from brewblox_devcon_spark.api import object_api, remote_api
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_SID_KEY,
                                                  API_TYPE_KEY, GROUP_LIST_KEY,
                                                  OBJECT_DATA_KEY,
                                                  OBJECT_SID_KEY,
                                                  OBJECT_TYPE_KEY)
from brewblox_devcon_spark.codec import codec

TESTED = remote_api.__name__


class DummyListener():

    def subscribe(self,
                  exchange_name=None,
                  routing=None,
                  exchange_type=None,
                  on_message=None,
                  ):
        self.exchange_name = exchange_name
        self.routing = routing
        self.exchange_type = exchange_type
        self.on_message = on_message


@pytest.fixture
def object_args():
    return {
        OBJECT_SID_KEY: 'testobj',
        GROUP_LIST_KEY: [0],
        OBJECT_TYPE_KEY: 'TempSensorOneWire',
        OBJECT_DATA_KEY: {
            'value': 1234,
            'address': 'ff',
        }
    }


@pytest.fixture
def mock_publisher(mocker):
    m = mocker.patch(TESTED + '.events.get_publisher')
    m.return_value.publish = CoroutineMock()
    return m.return_value


@pytest.fixture
def dummy_listener(mocker):
    m = mocker.patch(TESTED + '.events.get_listener')
    m.return_value = DummyListener()
    return m.return_value


@pytest.fixture
async def app(app, mock_publisher, dummy_listener):
    """App + controller routes"""

    status.setup(app)
    scheduler.setup(app)
    datastore.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
    device.setup(app)
    seeder.setup(app)
    object_api.setup(app)
    remote_api.setup(app)

    return app


@pytest.fixture
async def created(app, client, object_args):
    status.get_status(app).connected.set()
    retv = await client.post('/objects', json={
        API_SID_KEY: object_args[OBJECT_SID_KEY],
        GROUP_LIST_KEY: object_args[GROUP_LIST_KEY],
        API_TYPE_KEY: object_args[OBJECT_TYPE_KEY],
        API_DATA_KEY: object_args[OBJECT_DATA_KEY],
    })
    assert retv.status < 400


async def test_slave_translations(app, client, created, object_args, dummy_listener):
    ctrl = device.get_controller(app)
    await client.post('/remote/slave', json={
        'id': object_args[OBJECT_SID_KEY],
        'key': 'testface',
        'translations': {'address': 'address'}
    })

    data = object_args[OBJECT_DATA_KEY]
    # should be propagated
    data['address'] = 'aa'.rjust(16, '0')

    await dummy_listener.on_message(None, 'testface', deepcopy(data))

    updated = await ctrl.read_object({OBJECT_SID_KEY: object_args[OBJECT_SID_KEY]})
    assert updated[OBJECT_DATA_KEY]['address'] == 'aa'.rjust(16, '0')


async def test_slave_all(app, client, created, object_args, dummy_listener):
    ctrl = device.get_controller(app)
    await client.post('/remote/slave', json={
        'id': object_args[OBJECT_SID_KEY],
        'key': 'testface',
        'translations': {}
    })

    # No translation table: everything is used
    data = object_args[OBJECT_DATA_KEY]
    data['address'] = 'aa'.rjust(16, '0')

    await dummy_listener.on_message(None, 'testface', deepcopy(data))
    updated = await ctrl.read_object({OBJECT_SID_KEY: object_args[OBJECT_SID_KEY]})
    assert updated[OBJECT_DATA_KEY]['address'] == 'aa'.rjust(16, '0')


async def test_master(app, client, created, mock_publisher, object_args):
    key = '.'.join([
        app['config']['name'],
        object_args[OBJECT_SID_KEY]
    ])
    retv = await client.post('/remote/master', json={
        'id': object_args[OBJECT_SID_KEY],
        'interval': 0.01
    })
    assert retv.status == 200
    assert (await retv.json())['key'] == key

    read_obj = await device.get_controller(app).read_object(
        {OBJECT_SID_KEY: object_args[OBJECT_SID_KEY]})

    await asyncio.sleep(0.05)
    assert mock_publisher.publish.call_args_list[-1] == call(
        exchange=app['config']['sync_exchange'],
        routing=key,
        message=read_obj[OBJECT_DATA_KEY])

    # test reconnecting
    mock_publisher.reset_mock
    mock_publisher.publish.side_effect = RuntimeError
    await asyncio.sleep(0.05)
    assert mock_publisher.publish.call_count > 0

    # resume ok
    mock_publisher.reset_mock
    mock_publisher.publish.side_effect = None
    await asyncio.sleep(0.05)
    assert mock_publisher.publish.call_count > 0
