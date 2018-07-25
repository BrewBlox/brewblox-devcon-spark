"""
Tests brewblox_devcon_spark.api.remote_api
"""

import asyncio
from copy import deepcopy
from unittest.mock import call

import pytest
from asynctest import CoroutineMock
from brewblox_service import scheduler

from brewblox_codec_spark import codec
from brewblox_devcon_spark import commander_sim, datastore, device
from brewblox_devcon_spark.api import object_api, remote_api
from brewblox_devcon_spark.api.object_api import (API_DATA_KEY, API_ID_KEY,
                                                  API_TYPE_KEY,
                                                  OBJECT_DATA_KEY,
                                                  OBJECT_ID_KEY,
                                                  OBJECT_TYPE_KEY,
                                                  PROFILE_LIST_KEY)

TESTED = remote_api.__name__


class DummyListener():

    def subscribe(self,
                  exchange_name=None,
                  routing=None,
                  exchange_type=None,
                  on_message=None,
                  ):
        print('subscribed')
        self.exchange_name = exchange_name
        self.routing = routing
        self.exchange_type = exchange_type
        self.on_message = on_message


@pytest.fixture
def object_args():
    return {
        OBJECT_ID_KEY: 'testobj',
        PROFILE_LIST_KEY: [1, 4, 7],
        OBJECT_TYPE_KEY: 'OneWireTempSensor',
        OBJECT_DATA_KEY: {
            'settings': {
                'address': 'ff',
            },
            'state': {
                'value': 1234,
                'connected': True
            }
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

    scheduler.setup(app)
    datastore.setup(app)
    commander_sim.setup(app)
    codec.setup(app)
    device.setup(app)
    object_api.setup(app)
    remote_api.setup(app)

    return app


@pytest.fixture
async def created(app, client, object_args):
    await client.post('/objects', json={
        API_ID_KEY: object_args[OBJECT_ID_KEY],
        PROFILE_LIST_KEY: object_args[PROFILE_LIST_KEY],
        API_TYPE_KEY: object_args[OBJECT_TYPE_KEY],
        API_DATA_KEY: object_args[OBJECT_DATA_KEY],
    })


async def test_slave_translations(app, client, created, object_args, dummy_listener):
    ctrl = device.get_controller(app)
    await client.post('/remote/slave', json={
        'id': object_args[OBJECT_ID_KEY],
        'key': 'testface',
        'translations': {'settings/address': 'settings/address'}
    })

    data = object_args[OBJECT_DATA_KEY]
    # should be propagated
    data['settings']['address'] = 'aa'
    # ignored
    data['state']['connected'] = False

    await dummy_listener.on_message(None, 'testface', deepcopy(data))

    updated = await ctrl.read_object({OBJECT_ID_KEY: object_args[OBJECT_ID_KEY]})
    assert updated[OBJECT_DATA_KEY]['settings']['address'] == 'aa'
    assert updated[OBJECT_DATA_KEY]['state']['connected'] is True


async def test_slave_all(app, client, created, object_args, dummy_listener):
    ctrl = device.get_controller(app)
    await client.post('/remote/slave', json={
        'id': object_args[OBJECT_ID_KEY],
        'key': 'testface',
        'translations': {}
    })

    # No translation table: everything is used
    data = object_args[OBJECT_DATA_KEY]
    data['settings']['address'] = 'aa'
    data['state']['connected'] = False

    await dummy_listener.on_message(None, 'testface', deepcopy(data))
    updated = await ctrl.read_object({OBJECT_ID_KEY: object_args[OBJECT_ID_KEY]})
    assert updated[OBJECT_DATA_KEY]['settings']['address'] == 'aa'
    assert not updated[OBJECT_DATA_KEY]['state'].get('connected')


async def test_master(app, client, created, mock_publisher, object_args):
    key = '.'.join([
        app['config']['name'],
        object_args[OBJECT_ID_KEY]
    ])
    retv = await client.post('/remote/master', json={
        'id': object_args[OBJECT_ID_KEY],
        'interval': 0.01
    })
    assert retv.status == 200
    assert (await retv.json())['key'] == key

    read_obj = await device.get_controller(app).read_object(
        {OBJECT_ID_KEY: object_args[OBJECT_ID_KEY]})

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
