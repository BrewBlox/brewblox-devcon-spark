"""
Tests brewblox_devcon_spark.commander
"""

import pytest
from brewblox_service import scheduler
from brewblox_service.testing import matching

from brewblox_devcon_spark import (codec, commander, connection_sim,
                                   service_status)
from brewblox_devcon_spark.models import EncodedResponse, ErrorCode

TESTED = commander.__name__


@pytest.fixture
def app(app, mocker):
    app['config']['command_timeout'] = 1
    service_status.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    connection_sim.setup(app)
    commander.setup(app)
    return app


async def test_type_conversion():
    for (joined, split) in [
        ['Pid', ('Pid', None)],
        ['Pid.subtype', ('Pid', 'subtype')],
        ['Pid.subtype.subsubtype', ('Pid', 'subtype.subsubtype')]
    ]:
        assert commander.split_type(joined) == split
        assert commander.join_type(*split) == joined


async def test_unexpected_message(app, client, mocker):
    m_log_error = mocker.patch(TESTED + '.LOGGER.error', autospec=True)
    cmder = commander.fget(app)
    message = EncodedResponse(
        msgId=123,
        error=ErrorCode.ERR_OK,
        payload=[]
    )
    _, enc_message = await codec.fget(app).encode((codec.RESPONSE_TYPE, None), message.dict())
    await cmder._data_callback(enc_message)
    m_log_error.assert_called_with(matching(r'.*Unexpected message'))
