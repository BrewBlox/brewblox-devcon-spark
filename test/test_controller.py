"""
Tests brewblox_devcon_spark.controller
"""

from unittest.mock import Mock

import pytest
from asynctest import CoroutineMock

from brewblox_devcon_spark import controller

TESTED = controller.__name__


@pytest.fixture
async def commander_mock(mocker):
    m = mocker.patch(TESTED + '.SparkCommander')
    return m.return_value


@pytest.fixture
async def app(app, commander_mock):
    """App + controller routes"""
    controller.setup(app)
    return app


async def test_controller_init(app, loop, commander_mock):
    c = controller.SparkController('sparky')
    assert c.name == 'sparky'

    mock_app = Mock()
    c.setup(mock_app)

    assert mock_app.on_startup.append.call_count == 1
    assert mock_app.on_cleanup.append.call_count == 1

    # We never started
    await c.close()
    assert commander_mock.close.call_count == 0

    await c.start(mock_app)
    assert commander_mock.bind.call_count == 1

    await c.close()
    await c.close()
    assert commander_mock.close.call_count == 1


async def test_all_state(app, client):
    res = await client.get('/state')
    assert res.status == 200


async def test_absent_path(app, client):
    res = await client.get('/state/country')
    assert res.status == 200
    assert (await res.json()) is None


async def test_do(app, client, commander_mock):
    retval = dict(opcode=1, retval='text')
    commander_mock.do = CoroutineMock(return_value=retval)
    args = dict(command='list_objects', kwargs=dict(profile_id=0))
    res = await client.post('/_debug/do', json=args)
    assert res.status == 200
    assert (await res.json()) == retval


async def test_write(app, client, commander_mock):
    retval = 42
    commander_mock.write = CoroutineMock(return_value=retval)

    res = await client.post('/_debug/write', json=dict(command='stuff'))
    assert res.status == 200
    assert (await res.json()) == dict(written=retval)
