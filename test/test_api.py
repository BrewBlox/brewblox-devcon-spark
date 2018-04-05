"""
Tests brewblox_devcon_spark.api
"""

import pytest
from brewblox_devcon_spark import api, device
from asynctest import CoroutineMock


TESTED = api.__name__


@pytest.fixture
def controller_mock(mocker):
    controller = device.SparkController('sparky')
    controller._execute = CoroutineMock()
    controller._execute.side_effect = lambda command: dict(command=command.name)
    mocker.patch(device.__name__ + '.get_controller').return_value = controller
    return controller


@pytest.fixture
async def app(app, controller_mock):
    """App + controller routes"""
    api.setup(app)
    return app


async def test_create(app, client):
    args = dict(
        obj_type=10,
        obj_args=dict()
    )
    res = await client.put('/object', json=args)
    assert res.status == 200
    assert (await res.json())['command'] == 'CREATE_OBJECT'
